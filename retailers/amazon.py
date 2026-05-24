from .base import RetailerChecker


def _extract_seller(soup):
    """Detect Amazon marketplace seller from buy box."""
    merchant = soup.select_one('#merchant-info')
    if merchant:
        text = merchant.get_text(strip=True)
        lower = text.lower()
        for p in ['sold by ', 'ships from and sold by ']:
            idx = lower.find(p)
            if idx >= 0:
                after = text[idx + len(p):].strip()
                seller = after.split('.')[0].split(',')[0].strip()
                if seller:
                    return seller
    seller_tag = soup.select_one('#sellerName, .offer-display-feature-text-message')
    if seller_tag:
        text = seller_tag.get_text(strip=True)
        if text:
            lower = text.lower()
            for p in ['sold by ', 'by ']:
                idx = lower.find(p)
                after = text[idx + len(p):].strip() if idx >= 0 else text
                return after.split('.')[0].split(',')[0].strip()
    return None


def _is_amazon_direct(seller):
    if not seller:
        return True
    return 'amazon' in seller.lower()


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

            seller = _extract_seller(soup)
            if seller and not _is_amazon_direct(seller):
                product['_skip_reason'] = f'Marketplace: {seller}'
                return (True, f'In stock but {seller}')

            return (True, 'ATC button enabled')

        if 'currently unavailable' in body:
            return (False, 'Currently unavailable')

        if 'add to cart' in body:
            seller = _extract_seller(soup)
            if seller and not _is_amazon_direct(seller):
                product['_skip_reason'] = f'Marketplace: {seller}'
                return (True, f'In stock but {seller}')
            return (True, 'ATC text found')

        return await self._check_generic(product['url'])
