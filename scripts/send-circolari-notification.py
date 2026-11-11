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
SITE_URL = 'https://eurekaarchimede.it/#scuola'
ICON_URL = 'https://eurekaarchimede.it/assets/notifications/icon-eureka-v2-192.png'
TEST_SEGMENT_NAME = 'Test users'


def digest(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='invia solo al segmento OneSignal Test Users')
    parser.add_argument('--test-subscription', help='Subscription ID del solo dispositivo di prova')
    parser.add_argument('--test-url', help='URL di una circolare da aprire nella push di prova mirata')
    parser.add_argument('--only-url', help='invia una sola circolare, anche se era stata marcata come saltata')
    parser.add_argument('--inspect-user', help='legge le sole iscrizioni push di un OneSignal ID, senza inviare')
    parser.add_argument('--dry-run', action='store_true', help='mostra il messaggio senza inviare o aggiornare il registro')
    args = parser.parse_args()
    if args.test_subscription:
        if not args.test:
            raise ValueError('--test-subscription richiede --test')
        args.test_subscription = str(uuid.UUID(args.test_subscription))
    if args.test_url and (not args.test or not args.test_subscription):
        raise ValueError('--test-url richiede --test e --test-subscription')
    if args.inspect_user:
        args.inspect_user = str(uuid.UUID(args.inspect_user))
    feed = json.loads(FEED_PATH.read_text(encoding='utf-8'))
    ledger = json.loads(LEDGER_PATH.read_text(encoding='utf-8'))
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    sent = set(ledger.get('urls', []))
    skipped_no_subscribers = set(ledger.get('skipped_no_subscribers', []))
    circulars = [item for item in feed.get('circolari', [])
                 if isinstance(item, dict) and isinstance(item.get('url'), str)
                 and item['url'].startswith('https://www.liceoarchimedeme.edu.it/circolare/')]
    test_circular = None
    if args.test_url:
        test_circular = next((item for item in circulars if item['url'] == args.test_url), None)
        if not test_circular:
            raise ValueError('La circolare di prova non è presente nel feed corrente')
    if args.only_url:
        if args.test or args.inspect_user:
            raise ValueError('--only-url non può essere combinato con --test o --inspect-user')
        pending = [item for item in circulars if item['url'] == args.only_url]
        if not pending:
            raise ValueError('La circolare richiesta non è presente nel feed corrente')
    else:
        pending = [item for item in circulars
                   if digest(item['url']) not in sent
                   and digest(item['url']) not in skipped_no_subscribers]
    if not pending and not args.test and not args.inspect_user:
        print('nessuna nuova circolare')
        return 0

    app_id = config.get('appId', '').strip()
    api_key = os.environ.get('ONESIGNAL_API_KEY', '').strip()
    if not app_id or (not api_key and not args.dry_run):
        raise RuntimeError('App ID o chiave OneSignal non configurati: le circolari restano in attesa')

    if args.inspect_user:
        request = Request(
            f'https://api.onesignal.com/apps/{app_id}/users/by/onesignal_id/{args.inspect_user}',
            headers={'Authorization': f'Key {api_key}', 'Accept': 'application/json'},
        )
        try:
            with urlopen(request, timeout=20) as response:
                user = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Ispezione utente OneSignal: HTTP {error.code}') from error
        # Non pubblicare email, token push, chiavi di cifratura o altri dati del profilo nei log.
        subscriptions = [
            {key: sub.get(key) for key in ('id', 'type', 'enabled', 'notification_types', 'device_model', 'device_os')}
            for sub in user.get('subscriptions', []) if 'Push' in sub.get('type', '')
        ]
        print(json.dumps({'push_subscriptions': subscriptions}, ensure_ascii=False))
        return 0

    pending.sort(key=lambda item: (item.get('date', ''), item.get('number', '')))
    def save_ledger():
        ledger['version'] = 1
        ledger['urls'] = sorted(sent)
        ledger['skipped_no_subscribers'] = sorted(skipped_no_subscribers)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=LEDGER_PATH.parent,
                                         delete=False) as temp:
            json.dump(ledger, temp, ensure_ascii=False, separators=(',', ':'))
            temp.write('\n')
            temp_path = Path(temp.name)
        temp_path.replace(LEDGER_PATH)

    def send_one(item=None):
        if args.test:
            if item:
                number = item.get('number')
                title = item.get('title') or 'Prova apertura circolare'
                heading = f'Prova link · {number}' if number else 'Prova apertura circolare'
                contents = title
                circular_url = item['url']
            else:
                heading = 'eureka! · prova notifiche'
                contents = 'Le notifiche delle circolari sono attive su questo dispositivo.'
                circular_url = None
            segment = TEST_SEGMENT_NAME
        else:
            number = item.get('number')
            heading = number or 'Nuova circolare'
            contents = item.get('title') or 'Apri la nuova circolare.'
            circular_url = item['url']
            segment = 'All'

        # Ogni circolare ha il proprio titolo, messaggio e URL di destinazione.
        payload = {
            'app_id': app_id,
            'target_channel': 'push',
            # "All" è lo shorthand OneSignal per tutti gli iscritti alle push.
            'included_segments': [segment],
            'headings': {'en': heading[:100], 'it': heading[:100]},
            'contents': {'en': contents[:200], 'it': contents[:200]},
            'url': circular_url or SITE_URL,
            'chrome_web_icon': ICON_URL,
            'firefox_icon': ICON_URL,
        }
        if circular_url:
            payload['data'] = {'eureka_circular_url': circular_url}
        if args.test_subscription:
            del payload['included_segments']
            payload['include_subscription_ids'] = [args.test_subscription]
        # Le notifiche automatiche sono idempotenti per singola circolare.
        # Un reinvio esplicito o una prova deve invece poter essere ripetuto.
        if args.test or args.only_url:
            payload['idempotency_key'] = str(uuid.uuid4())
        else:
            payload['idempotency_key'] = str(uuid.uuid5(
                uuid.NAMESPACE_URL, app_id + ':push:' + item['url']))
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return {'id': 'dry-run'}

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
                               f"Dettagli API: {json.dumps(result.get('errors', []), ensure_ascii=False)[:500]}")
        return result

    if args.test:
        destination = 'il dispositivo indicato' if args.test_subscription else 'il segmento Test Users'
        target = test_circular['url'] if test_circular else SITE_URL
        if args.dry_run:
            send_one(test_circular)
            return 0
        send_one(test_circular)
        print(f'Push di prova accettata da OneSignal per {destination}; destinazione: {target}; registro circolari invariato')
        return 0

    failures = []
    sent_count = 0
    for item in pending:
        try:
            result = send_one(item)
        except Exception as error:
            failures.append(item)
            print(f"push non inviata per {item.get('number', 'circolare')}: {error}", file=sys.stderr)
            continue

        if args.dry_run:
            sent_count += 1
            continue
        sent.add(digest(item['url']))
        skipped_no_subscribers.discard(digest(item['url']))
        save_ledger()
        sent_count += 1
        print(f"push inviata per {item.get('number', 'circolare')} · {item.get('title', 'Nuova circolare')} (id: {result.get('id', 'n/d')})")

    if failures:
        raise RuntimeError(f'{len(failures)} push non riuscite; le circolari restano in coda per il prossimo controllo')
    if args.dry_run:
        print(f'anteprima: {sent_count} notifiche separate, senza invio né aggiornamento del registro')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Errore invio notifiche: {error}', file=sys.stderr)
        sys.exit(1)
