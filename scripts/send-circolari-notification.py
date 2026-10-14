#!/usr/bin/env python3
"""Invia una notifica OneSignal solo per nuove circolari nel feed scuola."""
import hashlib
import argparse
import json
import os
import sys
import tempfile
import uuid
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='invia solo al segmento OneSignal Test Users')
    parser.add_argument('--test-subscription', help='Subscription ID del solo dispositivo di prova')
    parser.add_argument('--dry-run', action='store_true', help='mostra il messaggio senza inviare o aggiornare il registro')
    args = parser.parse_args()
    if args.test_subscription:
        if not args.test:
            raise ValueError('--test-subscription richiede --test')
        args.test_subscription = str(uuid.UUID(args.test_subscription))
    feed = json.loads(FEED_PATH.read_text(encoding='utf-8'))
    ledger = json.loads(LEDGER_PATH.read_text(encoding='utf-8'))
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    sent = set(ledger.get('urls', []))
    circulars = [item for item in feed.get('circolari', [])
                 if isinstance(item, dict) and isinstance(item.get('url'), str)
                 and item['url'].startswith('https://www.liceoarchimedeme.edu.it/circolare/')]
    pending = [item for item in circulars if digest(item['url']) not in sent]
    if not pending and not args.test:
        print('nessuna nuova circolare')
        return 0

    app_id = config.get('appId', '').strip()
    api_key = os.environ.get('ONESIGNAL_API_KEY', '').strip()
    if not app_id or (not api_key and not args.dry_run):
        raise RuntimeError('App ID o chiave OneSignal non configurati: le circolari restano in attesa')

    pending.sort(key=lambda item: (item.get('date', ''), item.get('number', '')))
    if args.test:
        title = 'eureka! · prova notifiche'
        contents = 'Le notifiche delle circolari sono attive su questo dispositivo.'
    elif len(pending) == 1:
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
        'included_segments': ['Test Users' if args.test else 'Subscribed Users'],
        # OneSignal richiede il fallback en; il testo resta italiano su ogni dispositivo.
        'headings': {'en': title[:100], 'it': title[:100]},
        'contents': {'en': contents[:200], 'it': contents[:200]},
        'url': SITE_URL,
        'chrome_web_icon': 'https://eurekaarchimede.github.io/sito-eureka/assets/notifications/icon-eureka-v2-192.png',
        'firefox_icon': 'https://eurekaarchimede.github.io/sito-eureka/assets/notifications/icon-eureka-v2-192.png',
    }
    if args.test_subscription:
        del payload['included_segments']
        payload['include_subscription_ids'] = [args.test_subscription]
    # Un retry dello stesso gruppo usa la stessa chiave: niente doppioni se il salvataggio fallisce.
    payload['idempotency_key'] = str(uuid.uuid4()) if args.test else str(uuid.uuid5(
        uuid.NAMESPACE_URL, app_id + ':push:' + '|'.join(sorted(item['url'] for item in pending))))
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
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

    if not result.get('id'):
        raise RuntimeError('OneSignal non ha creato la notifica (nessun destinatario iscritto o raggiungibile). '
                           'Il registro non viene aggiornato; riproveremo al prossimo controllo.')
    if args.test:
        destination = 'il dispositivo indicato' if args.test_subscription else 'il segmento Test Users'
        print(f'Push di prova accettata da OneSignal per {destination}; registro circolari invariato')
        return 0

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
