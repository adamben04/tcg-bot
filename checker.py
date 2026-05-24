#!/usr/bin/env python3
import os
import sys
import json
import yaml
import asyncio
import random

import aiohttp
from datetime import datetime, timezone

GREEN = '\033[92m'
RED = '\033[91m'
AMBER = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'

def c(text, color=''):
    if not sys.stdout.isatty() and not os.environ.get('CI'):
        return text
    return color + text + RESET if color else text

from retailers.base import RetailerChecker
from retailers.pokemon_center import PokemonCenterChecker
from retailers.target import TargetChecker
from retailers.best_buy import BestBuyChecker
from retailers.gamestop import GameStopChecker
from retailers.walmart import WalmartChecker
from retailers.tcgplayer import TCGPlayerChecker
from retailers.costco import CostcoChecker
from retailers.sams_club import SamsClubChecker
from retailers.barnes_noble import BarnesNobleChecker
from retailers.amazon import AmazonChecker
from retailers.box_lunch import BoxLunchChecker
from retailers.premium_bandai import PremiumBandaiChecker
from notifier import send_notifications

CONFIG_PATH = 'config.yaml'
STATE_PATH = 'state.json'

RETAILER_MAP = {
    'pokemon_center': PokemonCenterChecker,
    'target': TargetChecker,
    'best_buy': BestBuyChecker,
    'gamestop': GameStopChecker,
    'walmart': WalmartChecker,
    'tcgplayer': TCGPlayerChecker,
    'costco': CostcoChecker,
    'sams_club': SamsClubChecker,
    'barnes_noble': BarnesNobleChecker,
    'amazon': AmazonChecker,
    'box_lunch': BoxLunchChecker,
    'hottopic': BoxLunchChecker,
    'premium_bandai': PremiumBandaiChecker,
}


def load_config():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {'products': {}, 'stats': {'total_checks': 0, 'notifications_sent': 0}}


def save_state(state):
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


async def check_product(product, session, user_agents, state, settings, webhook_url, telegram, pushover=None):
    name = product['name']
    url = product['url']
    retailer = product.get('retailer', 'generic')

    prod_state = state['products'].setdefault(url, {
        'name': name,
        'url': url,
        'retailer': retailer,
        'last_status': 'unknown',
        'last_notified': None,
        'last_checked': None,
        'history': [],
    })
    prod_state['retailer'] = retailer

    # Reset any previous price from the product dict before checking
    product.pop('_price', None)

    await asyncio.sleep(random.uniform(0.5, 3.0))

    checker_cls = RETAILER_MAP.get(retailer, RetailerChecker)
    checker = checker_cls(session, user_agents)

    try:
        in_stock, debug = await checker.check(product)
    except Exception as exc:
        print(f'[ERROR] {name}: {exc}')
        return

    price = product.get('_price')
    skip_reason = product.pop('_skip_reason', None)

    state['stats']['total_checks'] += 1
    prod_state['last_checked'] = datetime.now(timezone.utc).isoformat()

    prev_status = prod_state['last_status']

    price_ok_for_status = True
    if in_stock and not skip_reason and price:
        target = product.get('target_price')
        if target:
            try:
                if float(price) > target:
                    price_ok_for_status = False
            except ValueError:
                pass

    effective_in_stock = in_stock and not skip_reason and price_ok_for_status
    new_status = 'in_stock' if effective_in_stock else 'out_of_stock'
    changed = prev_status != new_status
    prod_state['last_status'] = new_status

    prod_state['history'].append({
        'at': datetime.now(timezone.utc).isoformat(),
        'status': new_status,
        'price': price,
        'reason': debug[:100],
    })
    prod_state['history'] = prod_state['history'][-100:]

    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
    label = 'IN STOCK' if effective_in_stock else 'OUT OF STOCK'
    changed = prev_status != prod_state['last_status']
    price_str = f' ${price}' if price else ''
    reason = ''
    if in_stock and not effective_in_stock:
        if skip_reason:
            reason = f' — skip: {skip_reason}'
        else:
            reason = f' — price ${price} > MSRP'
    color = GREEN if effective_in_stock else (AMBER if changed and not effective_in_stock else RED)
    icon = '⚡' if changed else (' ✓' if effective_in_stock else '')
    print(f'[{ts}] {c(name, BOLD)}: {c(label, color)}{price_str} ({debug}){icon}{reason}')

    if in_stock and not effective_in_stock:
        tp = product.get('target_price', 0)
        print(f'  → Skipping (not at MSRP): {skip_reason or f"${price} > ${tp}"}')

    if effective_in_stock:
        target = product.get('target_price')
        price_ok = True
        if target and price:
            try:
                price_ok = float(price) <= target
            except ValueError:
                pass
            if not price_ok:
                print(f'  → Price ${price} > target ${target:.2f} — skipping notification')

        last_notified = prod_state.get('last_notified')
        cooldown_m = settings.get('cooldown_minutes', 60)
        should_notify = False

        if not price_ok:
            should_notify = False
        elif last_notified is None:
            should_notify = True
        else:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last_notified)).total_seconds() / 60
            should_notify = elapsed >= cooldown_m

        if should_notify:
            try:
                sent = await send_notifications(webhook_url, telegram, product, price, session, pushover)
                if sent:
                    state['stats']['notifications_sent'] += sent
                    prod_state['last_notified'] = datetime.now(timezone.utc).isoformat()
                    print(f'  → Notifications sent ({sent} channel(s))')
                else:
                    print('  → Notifications failed')
            except Exception as exc:
                print(f'  → Notification error: {exc}')


async def main():
    config = load_config()
    state = load_state()

    settings = config.get('settings', {})
    user_agents = settings.get('user_agents', [])
    products = config.get('products', [])
    webhook_url = os.environ.get('DISCORD_WEBHOOK', '')
    telegram = config.get('telegram', {})
    pushover = config.get('pushover', {})

    if not products:
        print('No products in config.yaml — nothing to check')
        sys.exit(0)

    configured_urls = {p['url'] for p in products}
    stale = [k for k in state['products'] if k not in configured_urls]
    for key in stale:
        del state['products'][key]
        print(f'  Pruned stale state entry: {key}')

    pushtoken = pushover.get('token') if pushover else None
    print(f'{c("TCG Stock Checker", BOLD)} — {len(products)} product(s) across {len(set(p["retailer"] for p in products))} retailers')
    print(f'  {c("Discord", BLUE)}: {c("✅", GREEN) if webhook_url else c("not set", DIM)}')
    print(f'  {c("Telegram", BLUE)}: {c("✅", GREEN) if telegram.get("token") else c("not set", DIM)}')
    print(f'  {c("Pushover", BLUE)}: {c("✅", GREEN) if pushtoken else c("not set", DIM)}')
    print(f'  {c(f"{state["stats"]["total_checks"]} total checks, {state["stats"]["notifications_sent"]} notifications", DIM)}')
    print('─' * 50)

    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            check_product(p, session, user_agents, state, settings, webhook_url, telegram, pushover)
            for p in products
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            for e in errors:
                print(f'  [UNCAUGHT] {e}')

    save_state(state)

    in_stock_count = sum(
        1 for p in products
        if state['products'].get(p['url'], {}).get('last_status') == 'in_stock'
    )
    pct = round(100 * in_stock_count / len(products)) if products else 0
    bar_len = 20
    filled = round(bar_len * in_stock_count / len(products)) if products else 0
    bar = c('█' * filled, GREEN) + c('░' * (bar_len - filled), DIM)
    print(f'\n{c("Summary", BOLD)}')
    print(f'  {bar} {in_stock_count}/{len(products)} in stock ({pct}%)')
    print(f'  {c("Total checks", DIM)}: {state["stats"]["total_checks"]}')
    if state["stats"].get("notifications_sent"):
        print(f'  {c("Notifications sent", DIM)}: {state["stats"]["notifications_sent"]}')


if __name__ == '__main__':
    asyncio.run(main())
