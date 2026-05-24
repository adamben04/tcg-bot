#!/usr/bin/env python3
import os
import sys
import json
import yaml
import asyncio
import random

import aiohttp
from datetime import datetime, timezone

from retailers.base import RetailerChecker
from retailers.pokemon_center import PokemonCenterChecker
from retailers.target import TargetChecker
from retailers.best_buy import BestBuyChecker
from retailers.gamestop import GameStopChecker
from retailers.walmart import WalmartChecker
from retailers.tcgplayer import TCGPlayerChecker
from notifier import send_discord_notification

CONFIG_PATH = 'config.yaml'
STATE_PATH = 'state.json'

RETAILER_MAP = {
    'pokemon_center': PokemonCenterChecker,
    'target': TargetChecker,
    'best_buy': BestBuyChecker,
    'gamestop': GameStopChecker,
    'walmart': WalmartChecker,
    'tcgplayer': TCGPlayerChecker,
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


async def check_product(product, session, user_agents, state, settings, webhook_url):
    name = product['name']
    url = product['url']
    retailer = product.get('retailer', 'generic')

    prod_state = state['products'].setdefault(url, {
        'name': name,
        'url': url,
        'last_status': 'unknown',
        'last_notified': None,
        'last_checked': None,
    })

    await asyncio.sleep(random.uniform(0.5, 3.0))

    checker_cls = RETAILER_MAP.get(retailer, RetailerChecker)
    checker = checker_cls(session, user_agents)

    try:
        in_stock, debug = await checker.check(product)
    except Exception as exc:
        print(f'[ERROR] {name}: {exc}')
        return

    state['stats']['total_checks'] += 1
    prod_state['last_checked'] = datetime.now(timezone.utc).isoformat()

    prev_status = prod_state['last_status']
    prod_state['last_status'] = 'in_stock' if in_stock else 'out_of_stock'

    ts = datetime.now().strftime('%H:%M:%S')
    label = 'IN STOCK' if in_stock else 'OUT OF STOCK'
    changed = prev_status != prod_state['last_status']
    print(f'[{ts}] {name}: {label} ({debug}){" ⚡" if changed else ""}')

    if in_stock and webhook_url:
        last_notified = prod_state.get('last_notified')
        cooldown_m = settings.get('cooldown_minutes', 60)
        should_notify = False

        if last_notified is None:
            should_notify = True
        else:
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last_notified)).total_seconds() / 60
            should_notify = elapsed >= cooldown_m

        if should_notify:
            try:
                ok = await send_discord_notification(webhook_url, product, session)
                if ok:
                    state['stats']['notifications_sent'] += 1
                    prod_state['last_notified'] = datetime.now(timezone.utc).isoformat()
                    print('  → Discord notification sent')
                else:
                    print('  → Discord notification FAILED')
            except Exception as exc:
                print(f'  → Discord notification error: {exc}')


async def main():
    config = load_config()
    state = load_state()

    settings = config.get('settings', {})
    user_agents = settings.get('user_agents', [])
    products = config.get('products', [])
    webhook_url = os.environ.get('DISCORD_WEBHOOK', '')

    if not products:
        print('No products in config.yaml — nothing to check')
        sys.exit(0)

    configured_urls = {p['url'] for p in products}
    stale = [k for k in state['products'] if k not in configured_urls]
    for key in stale:
        del state['products'][key]
        print(f'  Pruned stale state entry: {key}')

    print(f'TCG Stock Checker — {len(products)} product(s)')
    print(f'Webhook: {"✅ set" if webhook_url else "⚠️  not set (notifications disabled)"}')
    print(f'Stats: {state["stats"]["total_checks"]} checks, {state["stats"]["notifications_sent"]} sent')
    print('-' * 50)

    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            check_product(p, session, user_agents, state, settings, webhook_url)
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
    print(f'\nDone — {in_stock_count}/{len(products)} in stock')
    print(f'Total checks: {state["stats"]["total_checks"]}')


if __name__ == '__main__':
    asyncio.run(main())
