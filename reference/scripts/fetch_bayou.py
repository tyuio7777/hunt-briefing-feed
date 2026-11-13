"""Opt-in, bounded research fetch. Never imported by the briefing pipeline.

HTML is an intermediate research cache, not a redistributable asset.
Only current roster links are followed; no removed/unreleased item discovery.
"""
import argparse, hashlib, json, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from lxml import html

ORIGIN = 'https://bayouindex.com'
AGENT = 'HuntBriefingReferenceResearch/1.0'
LIMIT = 8 * 1024 * 1024

def cache_name(path):
    return path.strip('/').replace('/', '__') + '.html'

def roster_links(document, domain):
    root = html.fromstring(document)
    links = []
    for a in root.xpath('//tbody/tr//a[@href]'):
        path = a.get('href')
        bits = path.strip('/').split('/')
        if len(bits) == 2 and bits[0] == domain and path not in links:
            links.append(path)
    if not 1 <= len(links) <= 250:
        raise ValueError('Unexpected roster size: ' + domain)
    return links

def run(cache):
    cache.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    last = [0.0]
    def get(path, filename=None):
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:
            raise ValueError('Non-local source URL')
        file = cache / (filename or cache_name(path))
        if file.exists():
            return file.read_bytes()
        with lock:
            time.sleep(max(0, .7 - (time.monotonic() - last[0])))
            last[0] = time.monotonic()
        with urlopen(Request(ORIGIN + path, headers={'User-Agent': AGENT}), timeout=30) as response:
            if urlsplit(response.url).netloc != 'bayouindex.com':
                raise ValueError('Unexpected source redirect')
            data = response.read(LIMIT + 1)
            if len(data) > LIMIT:
                raise ValueError('Source response too large')
        file.write_bytes(data)
        return data
    robots = get('/robots.txt', 'robots.txt').decode()
    policy = RobotFileParser()
    policy.parse(robots.splitlines())
    paths = []
    for domain in ('weapons', 'gear', 'traits'):
        path = '/' + domain + '/'
        if not policy.can_fetch(AGENT, ORIGIN + path):
            raise ValueError('robots.txt disallows roster')
        paths.extend(roster_links(get(path), domain))
    # Fetch only the data module explicitly observed and reviewed in this snapshot.
    snapshot=json.loads((Path(__file__).resolve().parents[1]/'config/bayou-source-snapshot.json').read_text())
    gear_path=next(p for p in paths if p.startswith('/gear/'))
    gear_document=get(gear_path).decode()
    module=snapshot['gearPageModuleUrl'].removeprefix(ORIGIN)
    if module not in gear_document: raise ValueError('Gear page module changed; review source imports')
    module_text=get(module,'gear-page.js').decode()
    data_path=snapshot['gearDataUrl'].removeprefix(ORIGIN)
    if '../chunks/'+data_path.rsplit('/',1)[-1] not in module_text:
        raise ValueError('Gear data import changed; review source imports')
    get(data_path,'gear-data.js')
    def one(path):
        try:
            if not policy.can_fetch(AGENT, ORIGIN + path):
                raise ValueError('robots.txt disallows detail')
            data = get(path)
            return {'url': ORIGIN + path, 'file': cache_name(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        except Exception as error:
            return {'url': ORIGIN + path, 'error': str(error)}
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for row in pool.map(one, paths):
            rows.append(row)
            if len(rows) % 25 == 0:
                print(f'{len(rows)}/{len(paths)} details; failures={sum("error" in x for x in rows)}', flush=True)
    (cache / 'fetch-manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    failures = [x for x in rows if 'error' in x]
    print(json.dumps({'pages': len(rows), 'failures': failures}, ensure_ascii=False), flush=True)
    if failures:
        raise SystemExit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='Explicitly authorize this one-off fetch')
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    if not args.fetch:
        parser.error('Network is disabled without --fetch')
    run(args.cache)
