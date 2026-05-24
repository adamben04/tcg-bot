from .base import RetailerChecker


class CostcoChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = (text or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'out of stock' in body or 'not available' in body:
            return (False, 'OOS text found')

        if 'sign in for price' in body or 'members only' in body:
            return (False, 'Members-only / requires login')

        add_btn = soup.select_one(
            'button[data-automation-id="add-to-cart"], '
            '.add-to-cart-button, '
            'button:has(svg[data-testid="AddShoppingCartIcon"])'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')
            return (True, 'ATC button enabled')

        return await self._check_generic(product['url'])
