from .base import RetailerChecker


class WalmartChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        text = (soup.get_text() or '').lower()

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
            return (True, 'ATC button enabled')

        return await self._check_generic(product['url'])
