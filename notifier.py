from datetime import datetime, timezone


EMBED_COLORS = {
    'in_stock': 0x00ff00,
    'out_of_stock': 0xff0000,
}


async def send_discord_notification(webhook_url, product, session):
    name = product['name']
    retailer = product.get('retailer', 'unknown').replace('_', ' ').title()
    sku = ''
    extra = product.get('extra', {})
    if extra.get('tcin'):
        sku = f"TCIN: {extra['tcin']}"
    elif extra.get('sku'):
        sku = f"SKU: {extra['sku']}"

    embed = {
        'title': f'🃏 {name} — IN STOCK',
        'url': product['url'],
        'color': EMBED_COLORS['in_stock'],
        'description': f'**Retailer:** {retailer}\n{sku}' if sku else f'**Retailer:** {retailer}',
        'footer': {'text': 'TCG Stock Bot'},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    if product.get('image'):
        embed['thumbnail'] = {'url': product['image']}

    payload = {'embeds': [embed]}

    async with session.post(webhook_url, json=payload) as resp:
        return resp.status == 204
