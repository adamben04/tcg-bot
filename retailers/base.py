import json
import random

from bs4 import BeautifulSoup


class RetailerChecker:

    def __init__(self, session, user_agents):
        self.session = session
        self.user_agents = user_agents

    async def check(self, product):
        return await self._check_generic(product['url'])

    async def _fetch(self, url):
        headers = {'User-Agent': random.choice(self.user_agents)}
        async with self.session.get(
            url, headers=headers, timeout=15, allow_redirects=True,
        ) as resp:
            text = await resp.text()
            return text, BeautifulSoup(text, 'html.parser')

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
        _, soup = await self._fetch(url)
        text = (soup.get_text() or '').lower()

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
            'pre-order', 'preorder', 'in stock',
        ]

        has_out = any(p in text for p in out_phrases)
        has_in = any(p in text for p in in_phrases)

        buttons = soup.select('button')
        enabled_btn = any(
            b.get('disabled') is None and b.get('aria-disabled') != 'true'
            for b in buttons
        )

        if has_out and not has_in and not enabled_btn:
            return (False, 'OOS text, no in-stock signal')

        if has_in and not has_out:
            return (True, 'In-stock text present')

        if enabled_btn and not has_out:
            return (True, 'Enabled button, no OOS text')

        if has_in and has_out:
            return (True, 'Mixed signals — assuming in stock')

        return (False, 'No clear signal — defaulting to OOS')
