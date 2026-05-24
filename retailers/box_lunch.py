from .base import RetailerChecker

class BoxLunchChecker(RetailerChecker):
    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = text.lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, "JSON-LD: " + ("in stock" if json_ld else "out of stock"))

        if 'sold out' in body or 'sold-out' in body:
            return (False, "Sold out label found")

        if '"availability": "outofstock"' in body or '"availability":"outofstock"' in body:
            return (False, "JSON availability: outofstock")

        if '"availability": "instock"' in body or '"availability":"instock"' in body:
            return (True, "JSON availability: instock")

        add_btn = soup.select_one(
            'button[data-testid="add-to-cart"], '
            'button.AddToCart, '
            '[data-add-to-cart]:not([disabled]), '
            '.product-form__cart-submit:not([disabled]), '
            'form[action*="cart/add"] button[type="submit"]:not([disabled])'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, "ATC disabled")
            return (True, "ATC button enabled")

        out_btn = soup.select_one(
            'button[disabled], '
            '.sold-out, '
            '[data-sold-out], '
            '.product-form__cart-submit[disabled], '
            '.btn--sold-out'
        )
        if out_btn:
            return (False, "Sold out button")

        return await self._check_generic(product['url'])
