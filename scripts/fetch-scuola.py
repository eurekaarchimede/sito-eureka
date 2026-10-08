#!/usr/bin/env python3
"""Aggiorna il catalogo locale delle circolari e gli ultimi orari pubblicati.

La prima esecuzione legge tutto l'archivio; quelle successive rileggono le
prime due pagine. --full forza una nuova scansione completa.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import time
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "scuola" / "feed.json"
BASE = "https://www.liceoarchimedeme.edu.it"
MONTHS = {"Gen": "01", "Feb": "02", "Mar": "03", "Apr": "04", "Mag": "05", "Giu": "06",
          "Lug": "07", "Ago": "08", "Set": "09", "Ott": "10", "Nov": "11", "Dic": "12"}
MAC_CERT = Path("/etc/ssl/cert.pem")
SSL_CONTEXT = ssl.create_default_context(
    cafile=str(MAC_CERT) if not ssl.get_default_verify_paths().cafile and MAC_CERT.exists() else None
)


def get(url):
    if not url.startswith(BASE + "/"):
        raise ValueError(f"URL inatteso: {url}")
    request = Request(url, headers={"User-Agent": "eureka-school-feed/1.0 (+public school pages)"})
    with urlopen(request, timeout=25, context=SSL_CONTEXT) as response:
        return response.read().decode("utf-8", "replace")


class ArchiveParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.card = None
        self.field = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "presentation-card-link" in classes and "/circolare/" in attrs.get("href", ""):
            self.card = {"url": attrs["href"], "title": "", "number": "", "year": "", "day": "", "month": ""}
            self.depth = 1
            return
        if self.card is None:
            return
        if tag == "a":
            self.depth += 1
        if tag == "h2":
            self.field = "title"
        elif tag == "small":
            self.field = "number"
        elif tag == "span":
            self.field = next((key for key in ("year", "day", "month") if key in classes), None)

    def handle_data(self, data):
        if self.card is not None and self.field:
            self.card[self.field] += data

    def handle_endtag(self, tag):
        if self.card is None:
            return
        if tag in ("h2", "small", "span"):
            self.field = None
        if tag == "a":
            self.depth -= 1
            if self.depth == 0:
                item = self.card
                self.card = None
                if item["year"] and item["day"] and item["month"] in MONTHS:
                    date = f'{item["year"].strip()}-{MONTHS[item["month"].strip()]}-{item["day"].strip().zfill(2)}'
                    self.items.append({"date": date, "number": " ".join(item["number"].split()),
                                       "title": " ".join(item["title"].split()), "url": item["url"]})


def get_archive_page(page):
    url = BASE + ("/circolare/" if page == 1 else f"/circolare/page/{page}/")
    source = get(url)
    parser = ArchiveParser()
    parser.feed(source)
    if not parser.items:
        raise RuntimeError(f"Nessuna circolare trovata nella pagina {page}: {url}")
    return parser.items, source


class PdfParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        parsed = urlsplit(href)
        if (parsed.scheme == "https" and parsed.netloc == "www.liceoarchimedeme.edu.it"
                and parsed.path.lower().endswith(".pdf")
                and (parsed.path.startswith("/download/") or parsed.path.startswith("/wp-content/uploads/"))
                and href not in self.links):
            self.links.append(href)


def attachments(item):
    parser = PdfParser()
    parser.feed(get(item["url"]))
    return parser.links


def primary_pdf(item):
    pdfs = item.get("pdfs", [])
    if len(pdfs) == 1:
        return pdfs[0]
    number = re.search(r"\d+", item["number"])
    if not number:
        return None
    n = int(number.group())
    exact = re.compile(rf"(?:crc|circ|circolare)[-_. ]*0*{n}(?=[^0-9]|$)", re.I)
    for pdf in pdfs:
        if exact.search(unquote(urlsplit(pdf).path.rsplit("/", 1)[-1])):
            return pdf
    # Alcune circolari ministeriali usano il protocollo come numero nel nome.
    if n >= 1000:
        protocol = re.compile(rf"(?<!\d)0*{n}(?!\d)")
        for pdf in pdfs:
            if protocol.search(unquote(urlsplit(pdf).path.rsplit("/", 1)[-1])):
                return pdf
    return None


def schedule():
    url = BASE + "/wp-json/wp/v2/posts?search=orario&per_page=100&orderby=date&order=desc&_fields=date,link,title,content"
    posts = json.loads(get(url))
    if not isinstance(posts, list):
        raise RuntimeError("L'API degli orari non ha restituito un elenco")
    result = {}
    for post in posts:
        title = html.unescape(post["title"]["rendered"])
        lower = title.lower()
        content = html.unescape(post.get("content", {}).get("rendered", ""))
        pdfs = re.findall(r'href=["\'](https://www\.liceoarchimedeme\.edu\.it/download/[^"\']+\.pdf)["\']', content, re.I)
        for kind, words in (("classi", ("classi", "alunni")), ("docenti", ("docenti",))):
            if kind in result or not any(word in lower for word in words):
                continue
            matching = next((link for link in pdfs if any(word in link.lower() for word in words)), None)
            if not matching and len(pdfs) == 1 and not ("classi" in lower and "docenti" in lower):
                matching = pdfs[0]
            if matching:
                result[kind] = {"title": title, "date": post["date"][:10], "url": post["link"], "pdf": matching}
        if len(result) == 2:
            break
    if len(result) != 2:
        raise RuntimeError("Non ho trovato entrambi i PDF degli orari")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="rileggi tutte le pagine dell'archivio")
    args = parser.parse_args()
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    first, source = get_archive_page(1)
    pages = max([1] + [int(n) for n in re.findall(r"/circolare/page/(\d+)/", source)])
    full = args.full or not previous.get("circolari")
    limit = pages if full else min(2, pages)
    current = list(first)
    for page in range(2, limit + 1):
        time.sleep(0.15)
        items, _ = get_archive_page(page)
        current.extend(items)
    if full:
        circolari = current
    else:
        known = {item["url"] for item in current}
        circolari = current + [item for item in previous["circolari"] if item["url"] not in known]
    previous_items = {item["url"]: item for item in previous.get("circolari", [])}
    changed_urls = {
        item["url"] for item in current
        if item["url"] not in previous_items
        or any(previous_items[item["url"]].get(key) != item.get(key)
               for key in ("date", "number", "title"))
    }
    for item in circolari:
        old = previous_items.get(item["url"], {})
        if "pdfs" in old:
            item["pdfs"] = old["pdfs"]
    # Nei controlli frequenti basta leggere i dettagli nuovi o modificati.
    # Evita decine di richieste ripetute alle stesse pagine e ai PDF.
    to_fetch = [item for item in circolari if item["url"] in changed_urls or "pdfs" not in item]
    failures = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(attachments, item): item for item in to_fetch}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                item["pdfs"] = future.result()
            except Exception as error:
                failures += 1
                print(f"PDF non letto: {item['url']} ({error})")
            if index % 100 == 0:
                print(f"PDF controllati: {index}/{len(to_fetch)}", flush=True)
    for item in circolari:
        item["pdf"] = primary_pdf(item)
    # L'ordine dell'archivio ufficiale prevale a parità di giorno.
    circolari.sort(key=lambda item: item["date"], reverse=True)
    data = {"source": BASE, "orari": schedule(), "circolari": circolari}
    if {key: previous.get(key) for key in data} == data:
        print(f"Nessuna novità ({len(circolari)} circolari)")
        return
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Aggiornati orari e {len(circolari)} circolari ({limit} pagine lette, {failures} PDF non letti)")


if __name__ == "__main__":
    main()
