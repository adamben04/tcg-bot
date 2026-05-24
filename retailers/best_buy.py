import os
import re
from urllib.parse import urlparse

from .base import RetailerChecker

API_BASE = 'https://api.bestbuy.com/v1'


class BestBuyChecker(RetailerChecker):

    def __init__(self, session, user_agents):
        super().__init__(session, user_agents)
        self.api_key = os.environ.get('BESTBUY_API_KEY', '')

    async def check(self, product):
        if not self.api_key:
            return await self._fallback_html(product)

        sku = await self._resolve_sku(product)
        if not sku:
            return await self._fallback_html(product)

        return await self._check_api(sku, product)

    async def _resolve_sku(self, product):
        url = product['url']
        last = url.rstrip('/').rsplit('/', 1)[-1]
        if last.isdigit():
            return last

        extra = product.get('extra', {})
        if extra and 'sku' in extra:
            return str(extra['sku'])

        try:
            text, soup = await self._fetch(url)
            meta = soup.select_one('meta[itemprop="sku"]')
            if meta and meta.get('content', '').isdigit():
                return meta['content']
            m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', text, re.DOTALL)
            if m:
                import json
                state = json.loads(m.group(1))
                skus = list(state.get('sku', {}).get('skus', {}).keys())
                if skus and skus[0].isdigit():
                    return skus[0]
        except Exception:
            pass
        return None

    async def _check_api(self, sku, product):
        fields = 'sku,name,salePrice,onlineAvailability,onlineAvailabilityText,inStoreAvailability,inStorePickup,orderable'
        url = f'{API_BASE}/products/{sku}.json?apiKey={self.api_key}&show={fields}'
        try:
            async with self.session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return (False, f'API error {resp.status}')
                data = await resp.json()
        except Exception as exc:
            return (False, f'API request failed: {exc}')

        p = data if isinstance(data, dict) and 'sku' in data else data.get('product', {})

        price = p.get('salePrice')
        if price:
            product['_price'] = price

        online = p.get('onlineAvailability')
        orderable = p.get('orderable', '')
        instore = p.get('inStoreAvailability')
        pickup = p.get('inStorePickup')

        if online is True:
            return (True, f'API: online (orderable: {orderable})')
        if isinstance(orderable, str) and orderable.lower() == 'available':
            return (True, f'API: orderable ({orderable})')
        if instore or pickup:
            return (True, 'API: in-store pickup available')
        return (False, f'API: OOS (online={online}, orderable={orderable})')

    async def _fallback_html(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = text.lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'window\.__PHOENIX_STATE__\s*=\s*({.*?});',
        ]
        for p in patterns:
            m = re.search(p, text, re.DOTALL)
            if m:
                try:
                    import json
                    state = json.loads(m.group(1))
                    avail = self._parse_state(state)
                    if avail is not None:
                        return (avail, f'Preloaded state: {"in stock" if avail else "out of stock"}')
                except json.JSONDecodeError:
                    continue

        if 'sold out' in body or 'coming soon' in body:
            return (False, 'Sold out label found')

        btn = soup.select_one(
            '.add-to-cart-button, '
            '.fulfillment-add-to-cart-button, '
            'button[data-button-state="ADD_TO_CART"], '
            '.c-button[data-track="Add to Cart"]'
        )
        if btn:
            disabled = btn.get('disabled') is not None
            aria = btn.get('aria-disabled') == 'true'
            if disabled or aria:
                return (False, 'ATC button disabled')
            return (True, 'ATC button present')

        return await self._check_generic(product['url'])

    def _parse_state(self, state):
        try:
            sku = list(state.get('sku', {}).get('skus', {}).keys())[0]
            sku_data = state['sku']['skus'][sku]
            purchasable = sku_data.get('purchasable')
            if purchasable is True:
                return True
            if purchasable is False:
                return False
        except (KeyError, IndexError, TypeError):
            pass
        return None
