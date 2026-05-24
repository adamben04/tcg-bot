import re
import json

from .base import RetailerChecker


class BestBuyChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'window\.__PHOENIX_STATE__\s*=\s*({.*?});',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    state = json.loads(match.group(1))
                    avail = self._parse_state(state)
                    if avail is not None:
                        return (avail, f'Preloaded state: {"in stock" if avail else "out of stock"}')
                except json.JSONDecodeError:
                    continue

        body = text.lower()
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
