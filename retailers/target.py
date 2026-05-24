import random

from .base import RetailerChecker


TCIN_API = (
    'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1'
    '?key=9f36aeafbe60771e321a7cc95a78140772ab3e96'
    '&tcin={tcin}'
    '&pricing_store_id={store_id}'
    '&visitor_id=tcg-bot'
)
DEFAULT_STORE_ID = '3991'


class TargetChecker(RetailerChecker):

    async def check(self, product):
        extra = product.get('extra', {})
        tcin = extra.get('tcin')
        if tcin:
            result = await self._check_api(tcin, extra.get('store_id', DEFAULT_STORE_ID))
            if result is not None:
                return result
        return await self._check_html(product['url'])

    async def _check_api(self, tcin, store_id=DEFAULT_STORE_ID):
        url = TCIN_API.format(tcin=tcin, store_id=store_id)
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'application/json',
        }
        async with self.session.get(url, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

        try:
            avail = data['product']['item']['availability']
            status = avail.get('availability_status', '')
            if status == 'IN_STOCK':
                return (True, 'Target API: IN_STOCK')
            elif status == 'LIMITED_AVAILABILITY':
                return (True, 'Target API: LIMITED_AVAILABILITY')
            elif status == 'OUT_OF_STOCK':
                return (False, 'Target API: OUT_OF_STOCK')
            elif status == 'NOT_SOLD_ONLINE':
                return (False, 'Target API: NOT_SOLD_ONLINE')
            else:
                return (False, f'Target API: unknown status {status}')
        except (KeyError, TypeError):
            return None

    async def _check_html(self, url):
        _, soup = await self._fetch(url)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        # Find "Add to Cart" buttons and check if they are disabled
        for btn in soup.select('button'):
            txt = (btn.get_text(strip=True) or '').lower()
            if 'add to cart' in txt or 'add to bag' in txt:
                disabled = btn.get('disabled') is not None
                if disabled:
                    return (False, 'ATC button is disabled')
                return (True, 'ATC button enabled')

        out_phrases = [
            'out of stock', 'sold out', 'not available',
            'temporarily unavailable', 'currently unavailable',
            'notify me when available', 'coming soon',
        ]
        has_out = any(p in body for p in out_phrases)
        if has_out:
            return (False, f'OOS signal found')

        in_phrases = ['add to cart', 'add to bag', 'buy now', 'place your order']
        has_in = any(p in body for p in in_phrases)
        if has_in and not has_out:
            return (True, 'In-stock text present')
        if has_in and has_out:
            return (False, 'Mixed — defaulting to OOS')

        return (False, 'No clear signal — defaulting to OOS')
