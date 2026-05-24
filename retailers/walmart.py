from .base import RetailerChecker


def _extract_seller(text):
    patterns = ['sold by ', 'from seller ', 'sold & shipped by ', 'sold and shipped by ']
    for p in patterns:
        idx = text.lower().find(p)
        if idx >= 0:
            after = text[idx + len(p):].strip()
            return after.split('.')[0].split(',')[0].strip()
    return None


class WalmartChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        text = (soup.get_text() or '').lower()
        seller = _extract_seller(text)

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'out of stock' in text:
            return (False, 'OOS text found')

        add_btn = soup.select_one(
            'button[aria-label="Add to cart"], '
            '.prod-ProductCTA--primary button, '
            '[data-automation-id="add-to-cart"]'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')

            if seller and 'walmart' not in seller.lower():
                product['_skip_reason'] = f'Marketplace: {seller}'
                return (True, f'In stock but {seller}')

            return (True, 'ATC button enabled')

        return await self._check_generic(product['url'])
