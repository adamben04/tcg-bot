import random
import re

from .base import RetailerChecker


DEFAULT_STORE_IDS = ['1284', '1573', '1805']
API_KEY = '9f36aeafbe60771e321a7cc95a78140772ab3e96'


def _parse_fulfillment(data):
    available = []
    try:
        fulfillment = data['product']['fulfillment']
        options = fulfillment.get('options', []) if isinstance(fulfillment, dict) else fulfillment
        for opt in options:
            ftype = opt.get('fulfillment_type', '')
            status = opt.get('availability_status', '')
            ready = opt.get('is_out_of_stock_in_area', True)
            if status == 'IN_STOCK' or ready is False:
                available.append(ftype)
    except (KeyError, TypeError, AttributeError):
        pass
    return available


class TargetChecker(RetailerChecker):

    def __init__(self, session, user_agents):
        super().__init__(session, user_agents)
        self._api_key = API_KEY

    async def _refresh_api_key(self):
        try:
            headers = {'User-Agent': random.choice(self.user_agents)}
            async with self.session.get(
                'https://www.target.com/', headers=headers, timeout=10,
            ) as resp:
                text = await resp.text()
            m = re.search(r'"apiKey":"(\w+)"', text)
            if m:
                self._api_key = m.group(1)
        except Exception:
            pass

    async def check(self, product):
        extra = product.get('extra', {})
        tcin = extra.get('tcin')
        check_mode = product.get('check_mode', 'shipping')
        store_ids = extra.get('store_ids') or extra.get('store_id')
        if isinstance(store_ids, str):
            store_ids = [store_ids]
        if not store_ids:
            store_ids = DEFAULT_STORE_IDS

        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)

        if tcin:
            result = await self._check_multi_store(tcin, store_ids, check_mode)
            if result is not None:
                return result
        return await self._check_html(soup)

    def _extract_price(self, soup):
        for sel in ['[data-test="product-price"]', '.h-text-xl', '.price']:
            el = soup.select_one(sel)
            if el:
                m = re.search(r'\$?(\d+\.\d{2})', el.get_text())
                if m:
                    return m.group(1)
        return super()._extract_price(soup)

    async def _check_multi_store(self, tcin, store_ids, check_mode):
        for sid in store_ids:
            result = await self._check_api(tcin, sid, check_mode)
            if result is not None and result[0]:
                return result
        return await self._check_api(tcin, store_ids[0], check_mode)

    async def _check_api(self, tcin, store_id, check_mode):
        url = (
            'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1'
            f'?key={self._api_key}'
            f'&tcin={tcin}'
            f'&pricing_store_id={store_id}'
            '&visitor_id=tcg-bot'
        )
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'application/json',
        }
        async with self.session.get(url, headers=headers, timeout=15) as resp:
            if resp.status == 403:
                await self._refresh_api_key()
                return None
            if resp.status != 200:
                return None
            data = await resp.json()

        try:
            avail = data['product']['item']['availability']
            ship_status = avail.get('availability_status', '')
        except (KeyError, TypeError):
            return None

        ship_ok = ship_status in ('IN_STOCK', 'LIMITED_AVAILABILITY')

        avail_types = _parse_fulfillment(data)
        store_methods = [t for t in avail_types if t in ('PICKUP', 'DRIVE_UP', 'IN_STORE_PICKUP')]
        store_ok = len(store_methods) > 0

        if check_mode == 'store':
            if store_ok:
                return (True, f'Store {store_id}: {", ".join(store_methods)}')
            return (False, f'Store {store_id}: OOS')

        if check_mode == 'any':
            if ship_ok or store_ok:
                parts = []
                if ship_ok:
                    parts.append(f'Ship: {ship_status}')
                if store_ok:
                    parts.append(f'Store {store_id}: {", ".join(store_methods)}')
                return (True, ' | '.join(parts))
            return (False, f'Store {store_id}: Ship {ship_status}, store OOS')

        if ship_ok:
            return (True, f'Shipping: {ship_status}')
        return (False, f'Shipping: {ship_status}')

    async def _check_html(self, soup):
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

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
            return (False, 'OOS signal found')

        in_phrases = ['add to cart', 'add to bag', 'buy now', 'place your order']
        has_in = any(p in body for p in in_phrases)
        if has_in and not has_out:
            return (True, 'In-stock text present')
        if has_in and has_out:
            return (False, 'Mixed — defaulting to OOS')
        return (False, 'No clear signal — defaulting to OOS')
