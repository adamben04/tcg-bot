from .base import RetailerChecker


class BarnesNobleChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'temporarily out of stock online' in body:
            return (False, 'OOS online')

        if 'out of stock' in body:
            return (False, 'OOS text found')

        add_btn = soup.select_one(
            'button[data-track="add-to-cart"], '
            '.add-to-cart-button, '
            '[data-testid="add-to-cart"], '
            'button:has(span:contains("Add to Cart"))'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')
            return (True, 'ATC button enabled')

        if 'check store availability' in body:
            return (False, 'Store pickup only')

        return await self._check_generic(product['url'])
