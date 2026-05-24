import re
import json

from .base import RetailerChecker

class GameStopChecker(RetailerChecker):

    async def check(self, product):
        text, soup = await self._fetch(product['url'])
        product['_price'] = self._extract_price(soup)
        body = text.lower()

        json_ld = self._check_json_ld(soup)
        if json_ld is not None:
            return (json_ld, "JSON-LD: " + ("in stock" if json_ld else "out of stock"))

        stock_data = self._check_preloaded_state(text)
        if stock_data is not None:
            return stock_data

        if self._check_meta_tags(soup):
            return (True, "Meta: in-stock")

        if 'sold out online' in body or 'sold-out' in body:
            return (False, "Sold out online label")

        if 'not available for shipping' in body and 'not available for pickup' in body:
            return (False, "Not available for shipping or pickup")

        add_btn = soup.select_one(
            '.add-to-cart button, '
            '.add-to-cart:not([disabled]), '
            'button[data-add-to-cart]:not([disabled]), '
            'button[data-stock-status="instock"], '
            'button:not([disabled])[data-button-type="add-to-cart"], '
            'button.atc:not([disabled]), '
            'button.add-to-cart-btn:not([disabled]), '
            '.primary-button:not([disabled])[data-tracking*="add"], '
            '.btn-primary:not([disabled])[data-tracking*="Add to Cart"]'
        )
        if add_btn:
            return (True, "ATC button found")

        disabled_btn = soup.select_one(
            'button.add-to-cart[disabled], '
            'button[data-add-to-cart][disabled], '
            'button[data-stock-status="outofstock"], '
            'button[aria-disabled="true"]'
        )
        if disabled_btn:
            return (False, "ATC button disabled")

        out_signals = [
            'out of stock', 'sold out', 'not available',
            'notify when available', 'coming soon',
            'find store availability', 'check store availability',
            'unavailable', 'temporarily unavailable',
        ]
        in_signals = [
            'add to cart', 'buy now', 'pre-order now',
            'preorder now', 'place your order', 'ship it',
        ]

        has_out = any(p in body for p in out_signals)
        has_in = any(p in body for p in in_signals)

        if has_out and not has_in:
            return (False, "OOS signal found")
        if has_in and not has_out:
            return (True, "In-stock signal found")

        if has_out and has_in:
            for signal in out_signals:
                if signal in body and 'not' not in body[max(0, body.index(signal)-50):body.index(signal)+50]:
                    return (False, "Mixed: OOS signal dominant")

        return (False, "No clear signal - defaulting to OOS")

    def _check_preloaded_state(self, text):
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
            r'window\.__DATA__\s*=\s*({.*?});',
            r'"product":\s*({[^}]+"stock"[^}]+})',
        ]
        for p in patterns:
            m = re.search(p, text, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    product_data = data.get('product', data)
                    if isinstance(product_data, dict):
                        stock = product_data.get('stock', product_data.get('stockLevel', product_data.get('availability')))
                        if stock is not None:
                            if isinstance(stock, (int, float)) and stock > 0:
                                return (True, "Preloaded: stock=" + str(stock))
                            if isinstance(stock, str):
                                sl = stock.lower()
                                if sl in ('instock', 'in stock', 'available', 'true'):
                                    return (True, "Preloaded: " + sl)
                                if sl in ('outofstock', 'out of stock', 'soldout', 'false'):
                                    return (False, "Preloaded: " + sl)
                except (json.JSONDecodeError, AttributeError):
                    continue
        return None

    def _check_meta_tags(self, soup):
        meta = soup.select_one('meta[property="product:availability"]')
        if meta:
            content = (meta.get('content') or '').lower()
            if 'instock' in content:
                return True
        return False
