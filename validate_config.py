#!/usr/bin/env python3
import os
import sys
import yaml
import json
import re
import asyncio
import aiohttp
import random

CONFIG_PATH = 'config.yaml'
STATE_PATH = 'state.json'

RETAILER_PATTERNS = {
    'pokemon_center': [r'pokemoncenter\.com/product/'],
    'target': [r'target\.com/.*/A-\d{6,}'],
    'amazon': [r'amazon\.com/.*/dp/', r'amazon\.com/dp/'],
    'best_buy': [r'bestbuy\.com/product/'],
    'gamestop': [r'gamestop\.com/'],
    'walmart': [r'walmart\.com/ip/'],
    'costco': [r'costco\.com/'],
    'sams_club': [r'samsclub\.com/'],
    'barnes_noble': [r'barnesandnoble\.com/'],
    'tcgplayer': [r'tcgplayer\.com/'],
    'box_lunch': [r'boxlunch\.com/'],
    'hottopic': [r'hottopic\.com/'],
    'premium_bandai': [r'p-bandai\.com/'],
}

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

def check_url_pattern(url, patterns):
    return any(re.search(p, url) for p in patterns)

async def check_url_reachable(session, url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            return resp.status
    except Exception as e:
        return str(e)

async def validate():
    print(f'{c("Config Validator", BOLD)}')
    print()

    if not os.path.exists(CONFIG_PATH):
        print(f'  {c("✗", RED)} Config not found: {CONFIG_PATH}')
        sys.exit(1)

    with open(CONFIG_PATH, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    products = config.get('products', [])
    print(f'  {len(products)} product(s) defined\n')

    errors = []
    warnings = []
    url_checks = []

    for i, p in enumerate(products):
        pid = i + 1
        name = p.get('name', 'UNNAMED')
        url = p.get('url', '')
        retailer = p.get('retailer', '')
        target_price = p.get('target_price')

        # Check name
        if not name or name == 'UNNAMED':
            errors.append(f'  #{pid}: Missing name')

        # Check URL
        if not url:
            errors.append(f'  #{pid} {name}: Missing URL')
        elif not url.startswith('http'):
            errors.append(f'  #{pid} {name}: URL does not start with http')

        # Check retailer
        if not retailer:
            errors.append(f'  #{pid} {name}: Missing retailer')
        elif retailer not in RETAILER_PATTERNS:
            warnings.append(f'  #{pid} {name}: Unknown retailer "{retailer}" (checker may not exist)')
        elif not check_url_pattern(url, RETAILER_PATTERNS[retailer]):
            warnings.append(f'  #{pid} {name}: URL pattern doesn\'t match retailer "{retailer}"')

        # Check target_price
        if not target_price:
            warnings.append(f'  #{pid} {name}: Missing target_price')

        # Check TCIN for target products
        if retailer == 'target':
            extra = p.get('extra', {})
            tcin = extra.get('tcin') if extra else None
            url_tcin = re.search(r'A-(\d{6,})', url)
            if tcin:
                if url_tcin and tcin != url_tcin.group(1):
                    warnings.append(f'  #{pid} {name}: TCIN in extra ({tcin}) doesn\'t match URL ({url_tcin.group(1)})')
            else:
                if url_tcin:
                    warnings.append(f'  #{pid} {name}: TCIN {url_tcin.group(1)} found in URL but not in extra field')
                else:
                    warnings.append(f'  #{pid} {name}: No TCIN found for Target product')

        # Check ASIN for amazon products
        if retailer == 'amazon':
            asin_m = re.search(r'/dp/([A-Z0-9]{10})', url)
            if not asin_m:
                warnings.append(f'  #{pid} {name}: No ASIN found in Amazon URL')

        # Collect URLs for reachability check
        if url:
            url_checks.append((pid, name, url))

    print(f'  {c("Structure Validation", BOLD)}')
    for e in errors:
        print(f'  {c("✗", RED)} {e}')
    for w in warnings:
        print(f'  {c("!", AMBER)} {w}')
    if not errors and not warnings:
        print(f'  {c("All structure checks passed", GREEN)}')

    print(f'\n  {c("URL Reachability", BOLD)} (checking first 20 URLs...)')
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for pid, name, url in url_checks[:20]:
            tasks.append(check_url_reachable(session, url))
        results = await asyncio.gather(*tasks)
        for (pid, name, url), status in zip(url_checks[:20], results):
            if isinstance(status, int):
                if status < 400:
                    print(f'  {c(f"#{pid}", DIM)} {c(status, GREEN) if status < 300 else c(status, AMBER)} {c(name, BOLD)}')
                else:
                    print(f'  {c(f"#{pid}", DIM)} {c(status, RED)} {c(name, BOLD)}')
            else:
                print(f'  {c(f"#{pid}", DIM)} {c("ERR", RED)} {c(name, BOLD)} — {status}')

    # Check state.json health
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            state = json.load(f)
        prod_state = state.get('products', {})
        configured_urls = {p['url'] for p in products}
        stale = [k for k in prod_state if k not in configured_urls]
        missing = [p['url'] for p in products if p.get('url') not in prod_state]
        if stale:
            print(f'\n  {c("State Cleanup", AMBER)}: {len(stale)} stale entry(s) in state.json (URLs not in config)')
        if missing:
            print(f'\n  {c("Missing State", AMBER)}: {len(missing)} product(s) haven\'t been checked yet')
        if not stale and not missing:
            print(f'\n  {c("State is clean", GREEN)} — {len(prod_state)} entries match config')

    print(f'\n  {c("Summary", BOLD)}')
    print(f'    {len(errors)} errors, {len(warnings)} warnings')
    if errors:
        print(f'  {c("Fix errors before deploying", RED)}')
        sys.exit(1)
    else:
        print(f'  {c("Config is valid", GREEN)}')

if __name__ == '__main__':
    asyncio.run(validate())
