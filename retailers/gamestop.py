from .base import RetailerChecker


OUT_PATTERNS = [
    'sold out', 'not available', 'notify when available',
    'coming soon', 'unavailable', 'out of stock',
]


class GameStopChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        for phrase in OUT_PATTERNS:
            if phrase in body:
                return (False, f"Hit: '{phrase}'")

        add_btn = soup.select_one(
            '.add-to-cart button, '
            '.add-to-cart:not([disabled]), '
            'button[data-add-to-cart]:not([disabled])'
        )
        if add_btn:
            return (True, 'ATC button found')

        buttons = soup.find_all('button', string=lambda t: t and (
            'add to cart' in t.lower()
            or 'buy now' in t.lower()
            or 'pre-order' in t.lower()
            or 'place your order' in t.lower()
        ))
        for btn in buttons:
            if btn.get('disabled') is None and btn.get('aria-disabled') != 'true':
                return (True, f"Button text: '{btn.get_text(strip=True)[:30]}'")

        return (False, 'No ATC button or OOS signal found')
