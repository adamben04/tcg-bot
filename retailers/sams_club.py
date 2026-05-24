from .base import RetailerChecker


class SamsClubChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'out of stock' in body or 'temporarily unavailable' in body:
            return (False, 'OOS text found')

        if 'members-only' in body or 'members only' in body:
            pass

        add_btn = soup.select_one(
            'button[data-automation-id="add-to-cart"], '
            '.sc-button-add-to-cart, '
            '[data-testid="add-to-cart-button"]'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')
            return (True, 'ATC button enabled')

        if 'restocking soon' in body:
            return (False, 'Restocking soon — not available')

        return await self._check_generic(product['url'])
