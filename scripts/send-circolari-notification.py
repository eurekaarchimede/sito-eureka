#!/usr/bin/env python3
"""Invia una notifica OneSignal solo per nuove circolari nel feed scuola."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / 'assets/scuola/feed.json'
LEDGER_PATH = ROOT / 'assets/scuola/notifiche-inviate.json'
CONFIG_PATH = ROOT / 'assets/notifications/config.json'
SITE_URL = 'https://eurekaarchimede.github.io/sito-eureka/#scuola'


def digest(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def main():
    feed = json.loads(FEED_PATH.read_text(encoding='utf-8'))
    ledger = json.loads(LEDGER_PATH.read_text(encoding='utf-8'))
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    sent = set(ledger.get('urls', []))
    circulars = [item for item in feed.get('circolari', [])
                 if isinstance(item, dict) and isinstance(item.get('url'), str)
                 and item['url'].startswith('https://www.liceoarchimedeme.edu.it/circolare/')]
    pending = [item for item in circulars if digest(item['url']) not in sent]
    if not pending:
        print('nessuna nuova circolare')
        return 0

    app_id = config.get('appId', '').strip()
    api_key = os.environ.get('ONESIGNAL_API_KEY', '').strip()
    if not app_id or not api_key:
        print(f'{len(pending)} nuova/e circolare/i in attesa: configura appId e ONESIGNAL_API_KEY')
        return 0

    pending.sort(key=lambda item: (item.get('date', ''), item.get('number', '')))
    if len(pending) == 1:
        item = pending[0]
        title = item.get('title') or 'Nuova circolare'
        number = item.get('number')
        contents = f"{number}: {title}" if number else title
    else:
        title = 'eureka! · nuove circolari'
        contents = f'Sono state pubblicate {len(pending)} nuove circolari. Apri la bacheca eureka!.'

    payload = {
        'app_id': app_id,
        'target_channel': 'push',
        'included_segments': ['Subscribed Users'],
        'headings': {'it': title[:100]},
        'contents': {'it': contents[:200]},
        'url': SITE_URL,
    }
    request = Request(
        'https://api.onesignal.com/notifications',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={
            'Authorization': f'Key {api_key}',
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode('utf-8', errors='replace')
            if not 200 <= response.status < 300:
                raise RuntimeError(f'OneSignal ha risposto HTTP {response.status}: {body[:500]}')
            result = json.loads(body) if body else {}
    except HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'OneSignal ha risposto HTTP {error.code}: {detail[:500]}') from error
    except URLError as error:
        raise RuntimeError(f'Connessione a OneSignal non riuscita: {error.reason}') from error

    # Il registro si aggiorna solo dopo la conferma API: un errore lascia le notifiche in coda.
    sent.update(digest(item['url']) for item in pending)
    ledger['version'] = 1
    ledger['urls'] = sorted(sent)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=LEDGER_PATH.parent,
                                     delete=False) as temp:
        json.dump(ledger, temp, ensure_ascii=False, separators=(',', ':'))
        temp.write('\n')
        temp_path = Path(temp.name)
    temp_path.replace(LEDGER_PATH)
    print(f"notifica inviata per {len(pending)} circolare/i (id: {result.get('id', 'n/d')})")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Errore invio notifiche: {error}', file=sys.stderr)
        sys.exit(1)
