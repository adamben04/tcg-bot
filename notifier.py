from datetime import datetime, timezone

EMBED_COLOR = 0x00ff00

async def send_notifications(webhook_url, telegram, product, price, session, pushover=None):
    sent = 0
    if webhook_url:
        ok = await send_discord(webhook_url, product, price, session)
        if ok:
            sent += 1
    if telegram and telegram.get('token') and telegram.get('chat_id'):
        ok = await send_telegram(telegram['token'], telegram['chat_id'], product, price, session)
        if ok:
            sent += 1
    if pushover and pushover.get('token') and pushover.get('user'):
        ok = await send_pushover(pushover['token'], pushover['user'], product, price, session)
        if ok:
            sent += 1
    return sent

async def send_discord(webhook_url, product, price, session):
    name = product['name']
    retailer = product.get('retailer', 'unknown').replace('_', ' ').title()
    extra = product.get('extra', {})

    title = 'IN STOCK — ' + name
    if price:
        title += ' ($' + price + ')'

    desc = '**Retailer:** ' + retailer
    if extra.get('tcin'):
        desc += '\n**TCIN:** ' + extra['tcin']
    if price:
        desc += '\n**Price:** $' + price

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
    text = 'IN STOCK — ' + name
    if price:
        text += ' ($' + price + ')'
    text += '\n' + retailer
    text += '\n' + product['url']

    url = 'https://api.telegram.org/bot' + token + '/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'disable_web_page_preview': False}
    async with session.post(url, json=payload) as resp:
        return resp.status == 200

async def send_pushover(token, user, product, price, session):
    name = product['name']
    title = 'IN STOCK: ' + name
    message = name
    if price:
        message += ' — $' + price
    message += '\n' + (product.get('retailer', '') or '').replace('_', ' ').title()

    payload = {
        'token': token,
        'user': user,
        'title': title[:250],
        'message': message[:1024],
        'url': product['url'],
        'url_title': 'Buy Now',
        'priority': 1,
    }
    async with session.post('https://api.pushover.net/1/messages.json', data=payload) as resp:
        return resp.status == 200
