from .base import RetailerChecker

OUT_PATTERNS = [
    'sold out', 'not available', 'unavailable',
    'coming soon', 'notify when available', 'closed',
    'soldout', '品切れ',
]

class PremiumBandaiChecker(RetailerChecker):
    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = text.lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, "JSON-LD: " + ("in stock" if json_ld else "out of stock"))

        if 'window.__PRELOADED_STATE__' in text:
            import re, json
            m = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    if 'product' in data:
                        p = data['product']
                        purchasable = p.get('purchasable', p.get('available'))
                        if purchasable is True:
                            return (True, "Preloaded state: purchasable")
                        if purchasable is False:
                            return (False, "Preloaded state: not purchasable")
                    if 'sku' in data:
                        skus = data.get('sku', {}).get('skus', {})
                        for sku_id, sku_data in skus.items():
                            if sku_data.get('purchasable') is True:
                                return (True, "SKU purchasable")
                            elif sku_data.get('purchasable') is False:
                                return (False, "SKU not purchasable")
                    entries = data.get('entries', {})
                    for eid, entry in entries.items():
                        if entry.get('purchasable') is True:
                            return (True, "Entry purchasable")
                except (json.JSONDecodeError, AttributeError):
                    pass

        for phrase in OUT_PATTERNS:
            if phrase in body:
                return (False, "Hit: " + phrase)

        add_btn = soup.select_one(
            'button:not([disabled])[type="submit"], '
            '.add-to-cart:not([disabled]), '
            '.purchase-button:not([disabled]), '
            '[data-add-to-cart]:not([disabled]), '
            'form[action*="cart"] button:not([disabled])'
        )
        if add_btn:
            return (True, "ATC button found")

        return await self._check_generic(product['url'])
