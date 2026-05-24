import random

from .base import RetailerChecker


TCIN_API = (
    'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1'
    '?key=9f36aeafbe60771e321a7cc95a78140772ab3e96'
    '&tcin={tcin}'
    '&pricing_store_id={store_id}'
    '&visitor_id=tcg-bot'
)
DEFAULT_STORE_ID = '3991'


class TargetChecker(RetailerChecker):

    async def check(self, product):
        extra = product.get('extra', {})
        tcin = extra.get('tcin')
        if tcin:
            result = await self._check_api(tcin, extra.get('store_id', DEFAULT_STORE_ID))
            if result is not None:
                return result
        return await self._check_generic(product['url'])

    async def _check_api(self, tcin, store_id=DEFAULT_STORE_ID):
        url = TCIN_API.format(tcin=tcin, store_id=store_id)
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'application/json',
        }
        async with self.session.get(url, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

        try:
            avail = data['product']['item']['availability']
            status = avail.get('availability_status', '')
            if status == 'IN_STOCK':
                return (True, 'Target API: IN_STOCK')
            elif status == 'LIMITED_AVAILABILITY':
                return (True, 'Target API: LIMITED_AVAILABILITY')
            elif status == 'OUT_OF_STOCK':
                return (False, 'Target API: OUT_OF_STOCK')
            elif status == 'NOT_SOLD_ONLINE':
                return (False, 'Target API: NOT_SOLD_ONLINE')
            else:
                return (False, f'Target API: unknown status {status}')
        except (KeyError, TypeError):
            return None
