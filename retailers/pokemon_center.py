from .base import RetailerChecker


class PokemonCenterChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        text = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        negative = [
            'temporarily out of stock',
            'notify me when available',
            'sorry, this product is not available',
        ]
        for phrase in negative:
            if phrase in text:
                return (False, f"Hit negative signal: '{phrase}'")

        add_btn = soup.select_one(
            '.product-add-to-cart button, '
            '.add-to-cart button, '
            'button[data-testid="add-to-cart"]'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            aria_disabled = add_btn.get('aria-disabled') == 'true'
            if disabled or aria_disabled:
                return (False, 'Add-to-cart button is disabled')
            return (True, 'Add-to-cart button enabled')

        return await self._check_generic(product['url'])
