#!/usr/bin/env python3
"""Controlli locali del sito, senza rete o dipendenze esterne.

Eseguire dalla directory del progetto: python3 scripts/check-site.py
Non sostituisce i controlli di layout, JavaScript e prestazioni nel browser.
"""

import argparse
import json
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SCHOOL_HOSTS = {"liceoarchimedeme.edu.it", "www.liceoarchimedeme.edu.it"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
CSS_URL = re.compile(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)]*))\s*\)", re.I)
CSS_IMPORT = re.compile(r"@import\s+(?:\"([^\"]+)\"|'([^']+)')", re.I)
CSS_COMMENTS = re.compile(r"/\*.*?\*/", re.S)


def css_urls(value):
    value = CSS_COMMENTS.sub("", value)
    for match in CSS_URL.finditer(value):
        yield next(part for part in match.groups() if part is not None).strip()
    for match in CSS_IMPORT.finditer(value):
        yield next(part for part in match.groups() if part is not None)


def srcset_urls(value):
    """Extract URL tokens without splitting the commas inside data URLs."""
    position = 0
    length = len(value)
    while position < length:
        while position < length and (value[position].isspace() or value[position] == ","):
            position += 1
        start = position
        while position < length and not value[position].isspace():
            position += 1
        candidate = value[start:position]
        if not candidate:
            return
        yield candidate.rstrip(",")
        if candidate.endswith(","):
            continue
        depth = 0
        while position < length:
            char = value[position]
            position += 1
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                break


class SiteHTML(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids = {}
        self.references = []
        self.duplicates = []
        self.in_style = False
        self.base = None

    def add_reference(self, value, kind):
        if value:
            self.references.append((value, kind, self.getpos()[0]))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        identifier = values.get("id")
        if identifier is not None:
            line = self.getpos()[0]
            if identifier in self.ids:
                self.duplicates.append((identifier, self.ids[identifier], line))
            self.ids[identifier] = line
        if tag == "base" and values.get("href") and self.base is None:
            self.base = values["href"]
        for key, value in attrs:
            if key in {"src", "href", "xlink:href", "poster"}:
                if tag != "base":
                    self.add_reference(value, "%s[%s]" % (tag, key))
            elif key in {"srcset", "imagesrcset"} and value:
                for candidate in srcset_urls(value):
                    self.add_reference(candidate, "%s[%s]" % (tag, key))
            if (key in {"style", "fill", "stroke", "filter", "clip-path", "mask",
                        "marker-start", "marker-mid", "marker-end", "cursor"}
                    and value and "url(" in value.lower()):
                for url in css_urls(value):
                    self.add_reference(url, "%s[%s] url()" % (tag, key))
        if tag == "style":
            self.in_style = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "style":
            self.in_style = False

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, value):
        if self.in_style:
            for url in css_urls(value):
                self.add_reference(url, "CSS url/import")


class Checker:
    def __init__(self, root):
        self.root = root.resolve()
        self.errors = []
        self.html_cache = {}
        self.css_seen = set()
        self.assets = set()
        self.fragments = 0
        self.circular_count = 0
        self.post_count = 0

    def fail(self, context, message):
        self.errors.append("%s: %s" % (context, message))

    def label(self, path):
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def html(self, path):
        if path in self.html_cache:
            return self.html_cache[path]
        parser = SiteHTML(path)
        self.html_cache[path] = parser
        try:
            parser.feed(path.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as error:
            self.fail(self.label(path), "HTML non leggibile: %s" % error)
        for identifier, first, second in parser.duplicates:
            self.fail(self.label(path), "ID duplicato %r alle righe %d e %d" % (identifier, first, second))
        return parser

    def reference(self, value, source, context, base=None):
        try:
            url = urlsplit(value.strip())
        except ValueError as error:
            self.fail(context, "URL non valido %r: %s" % (value, error))
            return
        # Risorse di rete, data:, mailto:, tel: e altri protocolli non sono file locali.
        if url.scheme or url.netloc:
            return
        if base:
            try:
                base_url = urlsplit(base)
            except ValueError:
                self.fail(context, "base URL non valida: %r" % base)
                return
            if base_url.scheme or base_url.netloc:
                return
            base_path = unquote(base_url.path).replace("\\", "/")
            base_target = self.root / base_path.lstrip("/") if base_path.startswith("/") else source.parent / base_path
            directory = base_target if base_path.endswith("/") else base_target.parent
        else:
            directory = source.parent
        raw_path = unquote(url.path).replace("\\", "/")
        if not raw_path:
            target = base_target if base else source
        elif raw_path.startswith("/"):
            target = self.root / raw_path.lstrip("/")
        else:
            target = directory / raw_path
        try:
            target = target.resolve()
            target.relative_to(self.root)
        except (ValueError, OSError):
            self.fail(context, "percorso fuori dal sito: %r" % value)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.fail(context, "file locale mancante: %s" % self.label(target))
            return
        self.assets.add(target)
        if target.suffix.lower() == ".css" and target not in self.css_seen:
            self.css_seen.add(target)
            try:
                for child in css_urls(target.read_text(encoding="utf-8")):
                    self.reference(child, target, self.label(target))
            except (OSError, UnicodeError) as error:
                self.fail(self.label(target), "CSS non leggibile: %s" % error)
        fragment = unquote(url.fragment).split(":~:", 1)[0]
        if fragment and target.suffix.lower() in {".html", ".htm", ".svg"}:
            self.fragments += 1
            if fragment not in self.html(target).ids:
                self.fail(context, "fragment #%s non trovato in %s" % (fragment, self.label(target)))

    def load_json(self, relative):
        try:
            data = json.loads((self.root / relative).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self.fail(relative, "JSON non leggibile: %s" % error)
            return None
        if not isinstance(data, dict):
            self.fail(relative, "la radice deve essere un oggetto")
            return None
        return data

    def date_value(self, value, context):
        try:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("richiesto formato YYYY-MM-DD")
            return date.fromisoformat(value)
        except ValueError as error:
            self.fail(context, "data non valida %r: %s" % (value, error))
            return None

    def timestamp(self, value, context):
        try:
            if not isinstance(value, str):
                raise ValueError("timestamp assente")
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if result.tzinfo is None:
                raise ValueError("fuso orario assente")
            return result.astimezone(timezone.utc)
        except ValueError as error:
            self.fail(context, "timestamp non valido %r: %s" % (value, error))
            return None

    def trusted_url(self, value, hosts, context, pdf=False):
        try:
            if not isinstance(value, str) or any(ord(char) < 32 for char in value):
                raise ValueError("URL assente o con caratteri di controllo")
            url = urlsplit(value)
            if (url.scheme != "https" or url.hostname not in hosts or url.username is not None
                    or url.password is not None or url.port not in {None, 443}):
                raise ValueError("richiesto HTTPS sul dominio ufficiale")
            if pdf and not unquote(url.path).lower().endswith(".pdf"):
                raise ValueError("il percorso dell'allegato non termina con .pdf")
            return True
        except ValueError as error:
            self.fail(context, "URL non valido %r: %s" % (value, error))
            return False

    def school_feed(self):
        name = "assets/scuola/feed.json"
        data = self.load_json(name)
        if data is None:
            return
        self.trusted_url(data.get("source"), SCHOOL_HOSTS, name + " source")
        self.timestamp(data.get("updated_at"), name + " updated_at")
        schedules = data.get("orari")
        if not isinstance(schedules, dict):
            self.fail(name, "orari deve essere un oggetto")
        else:
            for kind in ("classi", "docenti"):
                item = schedules.get(kind)
                context = name + " orari." + kind
                if not isinstance(item, dict):
                    self.fail(context, "orario mancante")
                    continue
                self.date_value(item.get("date"), context)
                self.trusted_url(item.get("url"), SCHOOL_HOSTS, context)
                self.trusted_url(item.get("pdf"), SCHOOL_HOSTS, context, pdf=True)
        items = data.get("circolari")
        if not isinstance(items, list) or not items:
            self.fail(name, "circolari deve essere un elenco non vuoto")
            return
        self.circular_count = len(items)
        previous = None
        urls = set()
        for number, item in enumerate(items, 1):
            context = "%s circolare %d" % (name, number)
            if not isinstance(item, dict):
                self.fail(context, "la voce deve essere un oggetto")
                continue
            day = self.date_value(item.get("date"), context)
            if day is not None:
                if previous is not None and day > previous:
                    self.fail(context, "ordine errato: una circolare più recente segue una precedente")
                previous = day
            if not isinstance(item.get("title"), str) or not item["title"].strip():
                self.fail(context, "titolo assente")
            url = item.get("url")
            if self.trusted_url(url, SCHOOL_HOSTS, context):
                if url in urls:
                    self.fail(context, "scheda duplicata: %s" % url)
                urls.add(url)
            pdfs = item.get("pdfs", [])
            if not isinstance(pdfs, list):
                self.fail(context, "pdfs deve essere un elenco")
                pdfs = []
            for pdf in pdfs:
                self.trusted_url(pdf, SCHOOL_HOSTS, context + " allegato", pdf=True)
            primary = item.get("pdf")
            if primary:
                self.trusted_url(primary, SCHOOL_HOSTS, context + " PDF principale", pdf=True)
                if primary not in pdfs:
                    self.fail(context, "PDF principale assente dall'elenco pdfs")

    def instagram_feed(self):
        name = "assets/ig/feed.json"
        data = self.load_json(name)
        if data is None:
            return
        self.timestamp(data.get("updatedAt"), name + " updatedAt")
        posts = data.get("posts")
        if not isinstance(posts, list) or not posts:
            self.fail(name, "posts deve essere un elenco non vuoto")
            return
        self.post_count = len(posts)
        ids = set()
        previous = None
        for number, post in enumerate(posts, 1):
            context = "%s post %d" % (name, number)
            if not isinstance(post, dict):
                self.fail(context, "la voce deve essere un oggetto")
                continue
            identifier = post.get("id")
            if not isinstance(identifier, str) or not identifier:
                self.fail(context, "ID assente")
            elif identifier in ids:
                self.fail(context, "ID duplicato: %s" % identifier)
            else:
                ids.add(identifier)
            stamp = self.timestamp(post.get("timestamp"), context)
            if stamp is not None:
                if previous is not None and stamp > previous:
                    self.fail(context, "ordine errato: un post più recente segue uno precedente")
                previous = stamp
            self.trusted_url(post.get("permalink"), INSTAGRAM_HOSTS, context)
            image = post.get("image")
            if not isinstance(image, str) or not image:
                self.fail(context, "immagine assente")
                continue
            try:
                image_url = urlsplit(image)
            except ValueError:
                self.fail(context, "immagine con URL non valida")
                continue
            if image_url.scheme or image_url.netloc:
                self.fail(context, "l'immagine deve essere un asset locale")
            else:
                self.reference(image, self.root / "index.html", context)

    def run(self):
        index = self.root / "index.html"
        alias = self.root / "eureka.html"
        try:
            if index.read_bytes() != alias.read_bytes():
                self.fail("HTML", "index.html ed eureka.html non sono identici")
        except OSError as error:
            self.fail("HTML", "impossibile confrontare i due file: %s" % error)
        for path in (index, alias):
            parser = self.html(path)
            for value, kind, line in parser.references:
                self.reference(value, path, "%s:%d %s" % (self.label(path), line, kind), parser.base)
        self.school_feed()
        self.instagram_feed()
        if self.errors:
            print("FALLITO: %d problemi" % len(self.errors))
            for error in self.errors[:40]:
                print("- " + error)
            if len(self.errors) > 40:
                print("... altri %d problemi" % (len(self.errors) - 40))
            return 1
        print("OK: HTML identici; ID e %d fragment validi; %d asset locali presenti; "
              "%d circolari e %d post verificati." %
              (self.fragments, len(self.assets), self.circular_count, self.post_count))
        print("Controlli locali: nessuna richiesta di rete. Layout e prestazioni richiedono il browser.")
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="directory del sito (default: directory sopra scripts)")
    args = parser.parse_args()
    return Checker(args.root).run()


if __name__ == "__main__":
    raise SystemExit(main())
