from datetime import datetime, timezone


EMBED_COLOR = 0x00ff00


async def send_notifications(webhook_url, telegram, product, price, session):
    sent = 0
    if webhook_url:
        ok = await send_discord(webhook_url, product, price, session)
        if ok:
            sent += 1
    if telegram and telegram.get('token') and telegram.get('chat_id'):
        ok = await send_telegram(telegram['token'], telegram['chat_id'], product, price, session)
        if ok:
            sent += 1
    return sent


async def send_discord(webhook_url, product, price, session):
    name = product['name']
    retailer = product.get('retailer', 'unknown').replace('_', ' ').title()
    extra = product.get('extra', {})

    title = f'🃏 {name} — IN STOCK'
    if price:
        title += f' — ${price}'

    desc = f'**Retailer:** {retailer}'
    if extra.get('tcin'):
        desc += f'\n**TCIN:** {extra["tcin"]}'
    if price:
        desc += f'\n**Price:** ${price}'

    embed = {
        'title': title,
        'url': product['url'],
        'color': EMBED_COLOR,
        'description': desc,
        'footer': {'text': 'TCG Stock Bot'},
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    async with session.post(webhook_url, json={'embeds': [embed]}) as resp:
        return resp.status == 204


async def send_telegram(token, chat_id, product, price, session):
    name = product['name']
    retailer = product.get('retailer', 'unknown').replace('_', ' ').title()

    text = f'🃏 {name} — IN STOCK'
    if price:
        text += f' (${price})'
    text += f'\n📍 {retailer}'
    text += f'\n🔗 {product["url"]}'

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': False,
    }
    async with session.post(url, json=payload) as resp:
        return resp.status == 200
