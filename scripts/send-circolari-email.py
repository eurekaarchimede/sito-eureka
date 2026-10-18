#!/usr/bin/env python3
"""Invia via OneSignal le nuove circolari agli iscritti email."""
import hashlib
import html
import json
import os
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / 'assets/scuola/feed.json'
EMAIL_LEDGER_PATH = ROOT / 'assets/scuola/email-inviate.json'
CONFIG_PATH = ROOT / 'assets/notifications/config.json'
SITE_URL = 'https://eurekaarchimede.it/#scuola'


def digest(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def render_email(items):
    rows = []
    for item in items:
        number = html.escape(str(item.get('number') or 'Nuova circolare'))
        title = html.escape(str(item.get('title') or 'Consulta la circolare'))
        url = html.escape(item['url'], quote=True)
        try:
            published = date.fromisoformat(item.get('date', '')).strftime('%d/%m/%Y')
        except (TypeError, ValueError):
            published = ''
        date_line = f'<p style="margin:4px 0;color:#aeb8cc">{html.escape(published)}</p>' if published else ''
        rows.append(
            '<li style="margin:0 0 20px;padding:0 0 16px;border-bottom:1px solid #263552">'
            f'<strong>{number}</strong> · {title}{date_line}'
            f'<p style="margin:8px 0 0"><a href="{url}" style="color:#f5cd47">Apri la circolare</a></p></li>'
        )
    intro = 'È stata pubblicata una nuova circolare.' if len(items) == 1 else f'Sono state pubblicate {len(items)} nuove circolari.'
    return (
        '<!doctype html><html lang="it"><body style="margin:0;background:#0a1632;color:#f7eed5;'
        'font:16px Arial,sans-serif"><main style="max-width:640px;margin:auto;padding:32px 22px">'
        '<p style="margin:0 0 8px;color:#f5cd47;font-weight:bold">eureka! · archimede</p>'
        '<h1 style="font-size:25px">Nuove circolari</h1>'
        f'<p>{intro}</p><ul style="padding-left:20px">{"".join(rows)}</ul>'
        f'<p><a href="{SITE_URL}" style="color:#f5cd47">Apri la bacheca eureka!</a></p>'
        '<hr style="border:0;border-top:1px solid #263552;margin:28px 0">'
        '<p style="font-size:13px;color:#aeb8cc">Ricevi questo messaggio perché hai chiesto di ricevere gli avvisi via email. '
        'Per non riceverne più, <a href="[unsubscribe_url]" style="color:#f5cd47">disiscriviti qui</a>.</p>'
        '</main></body></html>'
    )


def save_ledger(sent):
    ledger = {'version': 1, 'urls': sorted(sent)}
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=EMAIL_LEDGER_PATH.parent,
                                     delete=False) as temp:
        json.dump(ledger, temp, ensure_ascii=False, separators=(',', ':'))
        temp.write('\n')
        temp_path = Path(temp.name)
    temp_path.replace(EMAIL_LEDGER_PATH)


def main():
    feed = json.loads(FEED_PATH.read_text(encoding='utf-8'))
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    circulars = [item for item in feed.get('circolari', [])
                 if isinstance(item, dict) and isinstance(item.get('url'), str)
                 and item['url'].startswith('https://www.liceoarchimedeme.edu.it/circolare/')]
    # Bootstrap esplicito: fotografa una volta il catalogo attuale, senza inviare
    # arretrati. I giri successivi usano solo questo registro, indipendente dal push.
    if not EMAIL_LEDGER_PATH.exists():
        baseline = {digest(item['url']) for item in circulars}
        if os.environ.get('DRY_RUN') == 'true':
            print(f'Simulazione: inizializzazione registro email con {len(baseline)} circolari; nessun invio o salvataggio')
        else:
            save_ledger(baseline)
            print(f'Registro email inizializzato con {len(baseline)} circolari; nessun arretrato inviato')
        return 0
    email_ledger = json.loads(EMAIL_LEDGER_PATH.read_text(encoding='utf-8'))
    sent = set(email_ledger.get('urls', []))
    pending = [item for item in circulars if digest(item['url']) not in sent]
    if not pending:
        print('nessuna nuova circolare da inviare via email')
        return 0

    app_id = config.get('appId', '').strip()
    api_key = os.environ.get('ONESIGNAL_API_KEY', '').strip()
    if not app_id or not api_key:
        raise RuntimeError('App ID o chiave OneSignal non configurati')

    pending.sort(key=lambda item: (item.get('date', ''), item.get('number', '')))
    if len(pending) == 1:
        item = pending[0]
        subject = f"{item.get('number', 'Nuova circolare')} · {item.get('title') or 'Liceo Archimede'}"
    else:
        subject = f'eureka! · {len(pending)} nuove circolari'
    payload = {
        'app_id': app_id,
        'target_channel': 'email',
        'included_segments': ['Subscribed Users'],
        'email_subject': subject[:150],
        'email_preheader': 'Nuovi avvisi pubblicati dal Liceo Archimede.',
        'email_body': render_email(pending),
        'email_from_name': 'eureka! · circolari',
        'url': SITE_URL,
        'idempotency_key': str(uuid.uuid5(
            uuid.NAMESPACE_URL, app_id + ':email:' + '|'.join(sorted(item['url'] for item in pending))))
    }

    if os.environ.get('DRY_RUN') == 'true':
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
            result = json.loads(body) if body else {}
    except HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'OneSignal email ha risposto HTTP {error.code}: {detail[:500]}') from error
    except URLError as error:
        raise RuntimeError(f'Connessione OneSignal email non riuscita: {error.reason}') from error

    if not result.get('id'):
        errors = json.dumps(result.get('errors', []), ensure_ascii=False)[:500]
        print('OneSignal non ha trovato iscritti email raggiungibili; riproverà al prossimo controllo. '
              f'Dettagli: {errors}')
        return 0

    sent.update(digest(item['url']) for item in pending)
    save_ledger(sent)
    print(f"email inviata per {len(pending)} nuova/e circolare/i (id: {result['id']})")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'Errore invio email: {error}', file=sys.stderr)
        sys.exit(1)
