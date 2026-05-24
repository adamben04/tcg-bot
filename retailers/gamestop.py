from .base import RetailerChecker


class GameStopChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        text = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'sold out' in text or 'not available' in text or 'notify when available' in text:
            return (False, 'OOS text found')

        add_btn = soup.select_one(
            '.add-to-cart, '
            '.buy-now, '
            'button[data-pid], '
            'button[data-add-to-cart]'
        )
        if add_btn:
            disabled = add_btn.get('disabled') is not None
            if disabled:
                return (False, 'ATC button disabled')
            return (True, 'ATC button enabled')

        preorder_btn = soup.select_one('button:not([disabled])')
        if preorder_btn and ('pre-order' in text or 'preorder' in text):
            return (True, 'Pre-order button available')

        return await self._check_generic(product['url'])
