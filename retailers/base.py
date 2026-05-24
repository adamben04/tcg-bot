import json
import random
import re

from bs4 import BeautifulSoup

try:
    from curl_cffi.requests import AsyncSession as CurlSession
    HAS_CURL = True
except ImportError:
    HAS_CURL = False

BLOCK_MARKERS = [
    'incapsula', 'just a moment', 'cf-ray', 'cf-challenge',
    'attention required', 'cloudflare', '403 forbidden',
]


class RetailerChecker:

    def __init__(self, session, user_agents):
        self.session = session
        self.user_agents = user_agents

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        return await self._check_generic(product['url'])

    async def _fetch(self, url):
        headers = {'User-Agent': random.choice(self.user_agents)}
        async with self.session.get(
            url, headers=headers, timeout=15, allow_redirects=True,
        ) as resp:
            text = await resp.text()

        if self._is_blocked(text):
            bypass = await self._fetch_bypass(url)
            if bypass:
                text = bypass

        return text, BeautifulSoup(text, 'html.parser')

    def _is_blocked(self, text):
        if not text or len(text) < 2000:
            return True
        lower = text.lower()
        return any(m in lower for m in BLOCK_MARKERS)

    async def _fetch_bypass(self, url):
        if not HAS_CURL:
            return None
        try:
            headers = {'User-Agent': random.choice(self.user_agents)}
            async with CurlSession() as s:
                resp = await s.get(url, headers=headers, impersonate='chrome', timeout=15)
                return resp.text
        except Exception:
            return None

    def _extract_price(self, soup):
        body = soup.get_text() or ''
        matches = re.findall(r'\$(\d+\.\d{2})', body)
        valid = [m for m in matches if 1 < float(m) < 10000]
        return valid[0] if valid else None

    def _check_json_ld(self, soup):
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string
            if not raw:
                continue
            try:
                data = json.loads(raw)
                items = [data] if isinstance(data, dict) else data
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    offers = item.get('offers', {})
                    if isinstance(offers, dict):
                        avail = offers.get('availability', '')
                        if 'InStock' in avail:
                            return True
                        if 'OutOfStock' in avail or 'SoldOut' in avail:
                            return False
                    if isinstance(offers, list):
                        for offer in offers:
                            if isinstance(offer, dict):
                                avail = offer.get('availability', '')
                                if 'InStock' in avail:
                                    return True
            except (json.JSONDecodeError, AttributeError):
                continue
        return None

    async def _check_generic(self, url):
        text, soup = await self._fetch(url)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        out_phrases = [
            'out of stock', 'sold out', 'not available',
            'temporarily unavailable', 'discontinued',
            'currently unavailable', 'notify me when available',
        ]
        in_phrases = [
            'add to cart', 'add to bag', 'buy now',
            'pre-order now', 'preorder now',
            'place your order',
        ]

        has_out = any(p in body for p in out_phrases)
        has_in = any(p in body for p in in_phrases)

        if has_out and not has_in:
            return (False, 'OOS signal found')
        if has_in and not has_out:
            return (True, 'In-stock text present')
        if has_in and has_out:
            return (False, 'Mixed signals — defaulting to OOS')
        return (False, 'No clear signal — defaulting to OOS')
