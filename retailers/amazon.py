from .base import RetailerChecker


class AmazonChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        def _find(tag, **attrs):
            return soup.find(tag, attrs=attrs)

        out_of_stock = (
            _find('span', id='outOfStock') or
            _find('span', id='availability') and 'unavailable' in body
        )
        if out_of_stock:
            return (False, 'OOS element found')

        add_btn = soup.select_one(
            'input[name="submit.add-to-cart"], '
            '#add-to-cart-button, '
            'input[data-testid="add-to-cart"]'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')
            return (True, 'ATC button enabled')

        if 'currently unavailable' in body:
            return (False, 'Currently unavailable')

        if 'add to cart' in body:
            return (True, 'ATC text found')

        return await self._check_generic(product['url'])
