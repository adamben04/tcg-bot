from .base import RetailerChecker


class TCGPlayerChecker(RetailerChecker):

    async def check(self, product):
        _, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        text = (soup.get_text() or '').lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, f"JSON-LD: {'in stock' if json_ld else 'out of stock'}")

        if 'no listings available' in text:
            return (False, 'No listings available')

        if 'lowest price' in text or 'market price' in text:
            return (True, 'Listings exist (price found)')

        listing_count = soup.select_one('[data-listing-count], .listing-count')
        if listing_count:
            count_text = listing_count.get_text(strip=True)
            try:
                count = int(''.join(c for c in count_text if c.isdigit()))
                return (count > 0, f'Listing count: {count}')
            except ValueError:
                pass

        return await self._check_generic(product['url'])
