import re
import json

from .base import RetailerChecker

class BarnesNobleChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = text.lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, "JSON-LD: " + ("in stock" if json_ld else "out of stock"))

        state_data = self._check_state(text)
        if state_data is not None:
            return state_data

        add_btn = soup.select_one(
            'button[data-track="add-to-cart"], '
            '.add-to-cart-button, '
            '[data-testid="add-to-cart"], '
            'button:not([disabled])[data-tracking-id*="add-to-cart"], '
            'button.btn--add-to-cart:not([disabled]), '
            '.product-details__add-to-cart:not([disabled]), '
            '.addToCartBtn:not([disabled]), '
            '[data-add-to-cart]:not([disabled])'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, "ATC disabled")
            return (True, "ATC enabled")

        if 'temporarily out of stock online' in body:
            return (False, "OOS online")
        if 'out of stock' in body and 'add to cart' not in body:
            return (False, "OOS text found")
        if 'check store availability' in body:
            return (False, "Store pickup only")

        disabled_btn = soup.select_one(
            'button[disabled][data-track="add-to-cart"], '
            'button.add-to-cart-button[disabled], '
            '.btn--add-to-cart[disabled]'
        )
        if disabled_btn:
            return (False, "ATC button disabled")

        return await self._check_generic(product['url'])

    def _check_state(self, text):
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'"productData":\s*({[^}]+"availability"[^}]+})',
            r'"availability":\s*"([^"]+)"',
        ]
        for p in patterns:
            m = re.search(p, text, re.DOTALL)
            if m:
                try:
                    if '"availability":' in p and '"' not in p.split('"availability"')[0]:
                        avail_str = m.group(1).lower()
                        if avail_str in ('instock', 'in stock', 'available'):
                            return (True, "State: " + avail_str)
                        if avail_str in ('outofstock', 'out of stock', 'soldout'):
                            return (False, "State: " + avail_str)
                        continue
                    data = json.loads(m.group(1))
                    avail = None
                    for key in ('availability', 'availabilityStatus', 'stock', 'stockLevel', 'inStock'):
                        if key in data:
                            avail = data[key]
                            break
                    if avail is not None:
                        if isinstance(avail, bool):
                            return (avail, "State: " + str(avail))
                        if isinstance(avail, str):
                            al = avail.lower()
                            if al in ('instock', 'in stock', 'available', 'true'):
                                return (True, "State: " + al)
                            if al in ('outofstock', 'out of stock', 'soldout', 'false'):
                                return (False, "State: " + al)
                        if isinstance(avail, (int, float)) and avail > 0:
                            return (True, "State: stock=" + str(avail))
                except (json.JSONDecodeError, AttributeError, IndexError):
                    continue
        return None
