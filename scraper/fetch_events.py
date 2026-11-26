#!/usr/bin/env python3
"""Scarica gli eventi culturali dalle fonti e scrive data/events.json.

Ogni fonte è indipendente: se una fallisce le altre vanno avanti e il
problema compare nel campo "sources" del JSON (e quindi nella pagina).

Uso:  python scraper/fetch_events.py [--out data/events.json]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from classify import CLASSICA, CONCERTI, MOSTRE, VISITE, _NON_CLASSICA_RE, classify, is_highlight  # noqa: E402
from towns import PROVINCE_NAMES, norm, province_of  # noqa: E402

TZ = ZoneInfo("Europe/Rome")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
HORIZON_DAYS = 240
PAUSE = 0.8  # secondi tra richieste alla stessa fonte

MESI = {m: i for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}
MESI_ABBR = {"GEN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAG": 5, "GIU": 6,
             "LUG": 7, "AGO": 8, "SET": 9, "OTT": 10, "NOV": 11, "DIC": 12}


@dataclass
class Event:
    title: str
    cat: str
    start: str                 # YYYY-MM-DD
    url: str
    src: str
    end: str | None = None     # YYYY-MM-DD, solo se diverso da start
    time: str | None = None    # HH:MM
    venue: str | None = None
    town: str | None = None
    prov: str | None = None
    img: str | None = None
    price: str | None = None
    hl: bool = False           # Crystal Tears
    more: int = 0              # altre date oltre a questa
    id: str = field(default="")

    def finalize(self) -> "Event":
        if self.end == self.start:
            self.end = None
        key = f"{norm(self.title)}|{self.start}|{self.src}"
        self.id = hashlib.sha1(key.encode()).hexdigest()[:10]
        return self


# ---------------------------------------------------------------- utilità

def today() -> date:
    return datetime.now(TZ).date()


def clean(s: str | None) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_it_date(text: str) -> date | None:
    """'sab 21 novembre 2026' / '21 novembre 2026' -> date."""
    m = re.search(r"(\d{1,2})\s+([a-zà]+)\s+(\d{4})", (text or "").lower())
    if not m or m.group(2) not in MESI:
        return None
    return date(int(m.group(3)), MESI[m.group(2)], int(m.group(1)))


def infer_year(day: int, month: int, ref: date) -> date:
    """Per le card con solo giorno/mese: anno corrente o prossimo."""
    d = date(ref.year, month, day)
    if d < ref - timedelta(days=60):
        d = date(ref.year + 1, month, day)
    return d


class Http:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})

    def get(self, url, **kw):
        r = self.s.get(url, timeout=30, **kw)
        r.raise_for_status()
        time.sleep(PAUSE)
        return r

    def post(self, url, **kw):
        r = self.s.post(url, timeout=30, **kw)
        r.raise_for_status()
        time.sleep(PAUSE)
        return r


# ------------------------------------------------------------------ fonti

def parse_visitdolomitibellunesi(payload: dict, ref: date) -> list[Event]:
    base = "https://www.visitdolomitibellunesi.com"
    by_id: dict[int, dict] = {}
    for d in payload.get("data", []):
        g = by_id.setdefault(d["id"], {"item": d, "dates": set()})
        ts = d.get("dateTimestamp")
        if ts:
            g["dates"].add(datetime.fromtimestamp(int(ts), TZ).date())
    out = []
    for g in by_id.values():
        d, dates = g["item"], sorted(x for x in g["dates"] if x >= ref)
        if not dates:
            continue
        tags = d.get("tags") or []
        hint = "visite_natura" if "EV_ESCURSIONI_GITE_VISITE_GUIDATE" in tags else None
        title = clean(d.get("title"))
        cat = classify(title, clean(d.get("subtitle")), hint)
        if not cat:
            continue
        place = clean(d.get("place"))
        town = clean(d.get("city")) or None
        img = (d.get("mainImage") or {}).get("url")
        common = dict(title=title, cat=cat, src="Visit Dolomiti Bellunesi",
                      venue=None if place.lower() in ("", "online") else place,
                      town=town, prov=province_of(town, "BL"),
                      img=base + img if img and img.startswith("/") else img)
        if cat == MOSTRE or len(dates) > 4:
            # mostra o evento ricorrente: un'unica voce col periodo
            out.append(Event(start=dates[0].isoformat(), end=dates[-1].isoformat(),
                             url=base + d["url"], **common))
        else:
            for i, day in enumerate(dates):
                out.append(Event(start=day.isoformat(), more=len(dates) - 1 if i == 0 else 0,
                                 url=f"{base}{d['url']}?day={day.isoformat()}", **common))
    return out


def fetch_visitdolomitibellunesi(http: Http, ref: date) -> list[Event]:
    r = http.post("https://www.visitdolomitibellunesi.com/it/getjson/list/events")
    return parse_visitdolomitibellunesi(r.json(), ref)


def parse_dolomitiprealpi(events: list[dict], ref: date) -> list[Event]:
    """Usata soprattutto per le descrizioni: trova Crystal Tears e i concerti
    classici che dal solo titolo non si riconoscono."""
    out = []
    for e in events:
        title, desc = clean(e.get("title")), clean(e.get("description"))
        start = (e.get("start_date") or "")[:10]
        end = (e.get("end_date") or "")[:10] or None
        if not start or (end or start) < ref.isoformat():
            continue
        cat = classify(title, desc)
        if cat not in (CLASSICA, MOSTRE, VISITE) and not is_highlight(desc):
            continue
        venue = e.get("venue") if isinstance(e.get("venue"), dict) else {}
        town = clean(venue.get("city")) or _town_from_text(desc, "BL")
        hhmm = None if e.get("all_day") else (e.get("start_date") or "")[11:16] or None
        out.append(Event(title=title, cat=cat, start=start, end=end, time=hhmm if hhmm != "00:00" else None,
                         venue=clean(venue.get("venue")) or None, town=town, prov=province_of(town, "BL"),
                         url=e.get("url"), src="Dolomiti Prealpi",
                         img=(e.get("image") or {}).get("url") if isinstance(e.get("image"), dict) else None,
                         price=clean(e.get("cost")) or None, hl=is_highlight(title, desc)))
    return out


def _town_from_text(text: str, prov: str) -> str | None:
    """Primo comune della provincia citato nel testo (Dolomiti Prealpi non dà il luogo)."""
    from towns import TOWN_TO_PROV
    t = norm(text)
    best = None
    for town, p in TOWN_TO_PROV.items():
        if p == prov and len(town) > 4 and re.search(rf"\b{re.escape(town)}\b", t):
            if best is None or t.index(town) < t.index(best):
                best = town
    return best.title() if best else None


def fetch_dolomitiprealpi(http: Http, ref: date) -> list[Event]:
    api = "https://www.dolomitiprealpi.it/wp-json/tribe/events/v1/events"
    events, page, pages = [], 1, 1
    while page <= min(pages, 12):
        j = http.get(api, params={"per_page": 50, "page": page,
                                  "start_date": ref.isoformat()}).json()
        events += j.get("events", [])
        pages = int(j.get("total_pages") or 1)
        page += 1
    return parse_dolomitiprealpi(events, ref)


def parse_venetosegreto(html_cards: str, ref: date) -> list[Event]:
    soup = BeautifulSoup(html_cards, "html.parser")
    out = []
    for a in soup.select("article.vs-event-card"):
        link = a.select_one("a.vs-event-card__link")
        dates = a.select_one(".vs-event-card__dates")
        if not link or not dates:
            continue
        first = dates.find("span")
        d = parse_it_date(first.get_text(" ") if first else dates.get_text(" "))
        if not d or d < ref:
            continue
        more = re.search(r"\((\d+)\s+date", dates.get_text(" "))
        metas = [p.get_text(" ", strip=True) for p in a.select("p.vs-event-card__meta")
                 if "vs-event-card__dates" not in (p.get("class") or [])]
        area = metas[0] if metas else None
        prov = PROVINCE_NAMES.get(norm(area or "")) or province_of(area)
        img = a.select_one("img")
        price = a.select_one(".vs-event-card__price")
        label = a.select_one(".vs-event-card__labels")
        out.append(Event(title=clean(link.get_text()), cat=VISITE, start=d.isoformat(),
                         url=link["href"], src="Veneto Segreto", town=None, prov=prov,
                         venue=clean(label.get_text()) if label else None,
                         img=img.get("src") if img else None,
                         price=clean(price.get_text()) if price else None,
                         more=max(int(more.group(1)) - 1, 0) if more else 0))
    return out


def fetch_venetosegreto(http: Http, ref: date) -> list[Event]:
    api = "https://venetosegreto.com/wp-json/vs/v1/events"
    out, page, pages = [], 1, 1
    while page <= min(pages, 15):
        j = http.get(api, params={"pagina": page}).json()
        out += parse_venetosegreto(j.get("html", ""), ref)
        pages = int(j.get("pages") or 1)
        page += 1
    return out


TACCO_PAGES = [
    ("veneto/classica-lirica-sinfonica", CLASSICA), ("veneto/mostre", MOSTRE),
    ("venezia/classica-lirica-sinfonica", CLASSICA), ("venezia/mostre", MOSTRE),
    ("treviso/classica-lirica-sinfonica", CLASSICA), ("treviso/mostre", MOSTRE),
    ("belluno/classica-lirica-sinfonica", CLASSICA), ("belluno/mostre", MOSTRE),
    ("pordenone/classica-lirica-sinfonica", CLASSICA), ("pordenone/mostre", MOSTRE),
]


def parse_tacco(page_html: str, hint: str, ref: date) -> list[Event]:
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for e in data if isinstance(data, list) else [data]:
            if not isinstance(e, dict) or e.get("@type") != "Event":
                continue
            name = clean(e.get("name"))
            city, _, title = name.partition(" | ") if " | " in name else ("", "", name)
            start, end = (e.get("startDate") or "")[:10], (e.get("endDate") or "")[:10] or None
            if not start or (end or start) < ref.isoformat():
                continue
            loc = e.get("location") or {}
            addr = loc.get("address") or {}
            town = clean(addr.get("addressLocality")) or city or None
            desc = clean(e.get("description"))
            cat = classify(title, desc, hint)
            if hint == CLASSICA and re.search(r"\bmusical\b|tribut|\bpop\b|\brock\b", title, re.I):
                cat = CONCERTI
            img = e.get("image")
            out.append(Event(title=title, cat=cat, start=start, end=end,
                             venue=clean(loc.get("name")) or None, town=town,
                             prov=province_of(town), url=e.get("url"), src="il Tacco di Bacco",
                             img=img if isinstance(img, str) and "img_eventi" in img else None,
                             hl=is_highlight(title, desc)))
    return out


def fetch_tacco(http: Http, ref: date) -> list[Event]:
    out, errors = [], []
    for path, hint in TACCO_PAGES:
        try:
            out += parse_tacco(http.get(f"https://iltaccodibacco.it/{path}/").text, hint, ref)
        except requests.HTTPError as ex:
            if ex.response is None or ex.response.status_code != 404:
                errors.append(f"{path}: {ex}")
    if errors and not out:
        raise RuntimeError("; ".join(errors))
    return out


FENICE_SKIP = re.compile(r"tourn|danza|balletto|visite|mostra|conferenz|incontr", re.I)


def parse_fenice(page_html: str, ref: date) -> list[Event]:
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for row in soup.select("div.sn_calendar_block_list_row"):
        m = re.match(r"(\d{2})-(\d{2})-(\d{4})", row.get("data-list-id", ""))
        if not m:
            continue
        day = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if day < ref or day > ref + timedelta(days=HORIZON_DAYS):
            continue
        for it in row.select(".sn_calendar_block_list_row_group_i"):
            cat_txt = clean(it.select_one(".category").get_text()) if it.select_one(".category") else ""
            title_el, link = it.select_one(".title"), it.select_one(".link a")
            if not title_el or not link or FENICE_SKIP.search(cat_txt):
                continue
            place = clean(it.select_one(".place").get_text()) if it.select_one(".place") else "Teatro La Fenice"
            t = it.select_one(".time")
            img = it.select_one("img")
            title = clean(title_el.get_text())
            cat = CONCERTI if classify(title) in (CONCERTI, None) and _NON_CLASSICA_RE.search(title) else CLASSICA
            out.append(Event(title=title, cat=cat, start=day.isoformat(),
                             time=clean(t.get_text()) if t else None, venue=place, town="Venezia",
                             prov="VE", url=link["href"], src="Teatro La Fenice",
                             img=img.get("src") if img else None))
    return out


def fetch_fenice(http: Http, ref: date) -> list[Event]:
    return parse_fenice(http.get("https://www.teatrolafenice.it/calendario/").text, ref)


def parse_turismofvg(page_html: str, want: str, ref: date) -> list[Event]:
    """want: 'Musica' o 'Mostre' (categoria scritta nella card)."""
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for a in soup.select("a.c-eventsResults__item"):
        cat_el = a.select_one(".info_category .col2")
        cat_name = clean(cat_el.get_text()) if cat_el else ""
        icon = a.select_one(".info_date .col3")
        if not cat_name and icon is not None:
            cat_name = icon.get("title", "")
        if want.lower() not in cat_name.lower():
            continue
        title_el = a.select_one(".item_title .title")
        if not title_el:
            continue
        title = clean(title_el.get_text())
        full = a.select_one(".item_title p")
        d = parse_it_date(full.get_text(" ")) if full else None
        if not d:
            dd, mm = a.select_one(".info_date .col1 strong"), a.select_one(".info_date .col1 p")
            if not dd or not mm or clean(mm.get_text()).upper()[:3] not in MESI_ABBR:
                continue
            d = infer_year(int(clean(dd.get_text())), MESI_ABBR[clean(mm.get_text()).upper()[:3]], ref)
        if d < ref:
            continue
        town_el = a.select_one(".info_location .col2") or a.select_one(".info_date .col2")
        town = clean(town_el.get_text()) if town_el else None
        hour = a.select_one(".info_hour .col2")
        if want == "Musica":
            cat = classify(title, "", "musica")
            if cat != CLASSICA:
                continue
        else:
            cat = MOSTRE
        out.append(Event(title=title, cat=cat, start=d.isoformat(),
                         time=clean(hour.get_text()) if hour else None, town=town,
                         prov=province_of(town, "FVG"), url="https://www.turismofvg.it" + a["href"],
                         src="Turismo FVG", hl=is_highlight(title)))
    return out


def fetch_turismofvg(http: Http, ref: date) -> list[Event]:
    out = []
    for slug, want, pages in (("musica", "Musica", 8), ("mostre", "Mostre", 4)):
        for p in range(pages):
            url = f"https://www.turismofvg.it/eventi/{slug}" + (f"?page={p}" if p else "")
            batch = parse_turismofvg(http.get(url).text, want, ref)
            out += batch
    return out


BELCIRCOLO_CATS = ("classica", "matinee-musicali", "luglio-al-borgo")


def parse_belcircolo(page_html: str, ref: date) -> list[Event]:
    """Card della stagione del Circolo Culturale Bellunese:
    'SABATO 5 DICEMBRE 2026 – ore 17:30 Belluno, Auditorium Comunale Biglietti: ...'"""
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for a in soup.select("article"):
        link = a.select_one(".entry-title a")
        body = a.select_one(".entry-content")
        if not link or not body:
            continue
        text = clean(body.get_text(" "))
        d = parse_it_date(text)
        if not d or d < ref:
            continue
        hhmm = re.search(r"ore\s+(\d{1,2})[:.](\d{2})", text)
        place = re.search(r"ore\s+\d{1,2}[:.]\d{2}\s+(.+?)(?:\s+-\s+mappa|\s+Biglietti|\s+\(altro|$)", text)
        price = re.search(r"Biglietti:\s*(.+?)(?:\s+\(altro|$)", text)
        town, venue = None, None
        if place:
            town, _, venue = place.group(1).partition(",")
        img = a.select_one("img")
        out.append(Event(title=clean(link.get_text()).title() if link.get_text().isupper() else clean(link.get_text()),
                         cat=CLASSICA, start=d.isoformat(),
                         time=f"{int(hhmm.group(1)):02d}:{hhmm.group(2)}" if hhmm else None,
                         venue=clean(venue) or None, town=clean(town) or "Belluno",
                         prov=province_of(clean(town), "BL"), url=link["href"], src="Circolo Culturale Bellunese",
                         img=img.get("src") if img else None, price=price.group(1).strip() if price else None))
    return out


def fetch_belcircolo(http: Http, ref: date) -> list[Event]:
    out = []
    for cat in BELCIRCOLO_CATS:
        out += parse_belcircolo(http.get(f"https://belcircolo.org/category/{cat}/").text, ref)
    return out


_SMALL = {"di", "del", "della", "delle", "dei", "degli", "de", "la", "le", "il", "lo", "al", "alla", "e", "tra", "fra", "a", "in", "da", "dal", "con", "per", "su"}


def _smart_case(t: str) -> str:
    """'SEBASTIÃO SALGADO. FOTOGRAFIE DELLA COLLEZIONE' -> 'Sebastião Salgado. Fotografie della Collezione'."""
    if t != t.upper():
        return t
    words = t.title().split(" ")
    return " ".join(w.lower() if i and w.lower() in _SMALL else w for i, w in enumerate(words))


def _dotted_date(s: str) -> date | None:
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})$", s.strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def parse_museibassano(page_html: str, ref: date) -> list[Event]:
    """Mostre in corso/future dei Musei Civici di Bassano del Grappa.
    Date nei formati '24.10.2026-4.4.2027', '30.10.2026―20.02.2027', 'Dal12dicembre2026'."""
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for c in soup.select(".portfolio-exhibition-item"):
        link, title_el = c.select_one("a[href]"), c.select_one(".carousel-title")
        dates = [clean(x.get_text(" ")) for x in c.select(".carousel-date-title")]
        if not link or not title_el or not dates:
            continue
        raw = dates[0]
        parts = re.split(r"\s*[-–―]\s*", raw)
        start = _dotted_date(parts[0])
        end = _dotted_date(parts[1]) if len(parts) > 1 else None
        if start is None:
            m = re.search(r"(\d{1,2})\s*([a-z]+)\s*(\d{4})", raw.lower())
            if m and m.group(2) in MESI:
                start = date(int(m.group(3)), MESI[m.group(2)], int(m.group(1)))
        if start is None:
            continue
        if end is None:
            # 'Dal 12 dicembre': nuova esposizione senza data di chiusura. La teniamo
            # visibile per tre mesi; un allestimento permanente già aperto si salta.
            if start < ref:
                continue
            end = start + timedelta(days=90)
        if end < ref:
            continue
        title = _smart_case(clean(title_el.get_text(" ")))
        img = c.select_one("img.desktop-image") or c.select_one("img")
        out.append(Event(title=title, cat=MOSTRE, start=start.isoformat(), end=end.isoformat(),
                         venue=dates[1] if len(dates) > 1 else None, town="Bassano del Grappa", prov="VI",
                         url=link["href"], src="Musei di Bassano",
                         img=img.get("src") if img else None))
    return out


def fetch_museibassano(http: Http, ref: date) -> list[Event]:
    out = []
    for path in ("in_corso", "future"):
        out += parse_museibassano(http.get(f"https://www.museibassano.it/it/mostre/{path}").text, ref)
    return out


MART_TOWNS = {"Mart Rovereto": "Rovereto", "Casa d'Arte Futurista Depero": "Rovereto",
              "Palazzo delle Albere": "Trento", "Galleria Civica Trento": "Trento"}


def parse_mart(page_html: str, ref: date) -> list[Event]:
    """Mostre del Mart (Rovereto e sedi di Trento) da /mostre-eventi. Fuori dal Veneto,
    ma richiesto a mano. Il sito è Next.js: l'elenco sta nel JSON __NEXT_DATA__
    (contentType "mostra", dataDiApertura/dataDiChiusura, sede). Workshop e "Altro"
    (campo tipologia) si saltano; le mostre permanenti senza chiusura (Le Collezioni) pure."""
    base = "https://www.mart.tn.it"
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ non trovato: struttura del sito cambiata?")
    found: dict = {}

    def walk(o):
        if isinstance(o, dict):
            if o.get("contentType") == "mostra" and o.get("url") and o.get("titolo"):
                found[o["url"]] = o
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(m.group(1)))
    out = []
    for o in found.values():
        if (o.get("tipologia") or "Mostra").lower() != "mostra":
            continue
        start, end = (o.get("dataDiApertura") or "")[:10], (o.get("dataDiChiusura") or "")[:10]
        if not start or not end or end < ref.isoformat():
            continue
        venue = clean(o.get("sede")) or None
        out.append(Event(title=clean(o["titolo"]), cat=MOSTRE, start=start, end=end, venue=venue,
                         town=MART_TOWNS.get(venue or "", "Rovereto"), prov="TN",
                         url=base + o["url"], src="Mart Rovereto", img=o.get("ogImageUrl") or None))
    out.sort(key=lambda e: (e.start, e.title))
    return out


def fetch_mart(http: Http, ref: date) -> list[Event]:
    return parse_mart(http.get("https://www.mart.tn.it/mostre-eventi/mostre-ed-eventi-118152").text, ref)


SOURCES = [
    ("Visit Dolomiti Bellunesi", "https://www.visitdolomitibellunesi.com/it/eventi/calendario-eventi", fetch_visitdolomitibellunesi),
    ("Dolomiti Prealpi", "https://www.dolomitiprealpi.it/eventi/", fetch_dolomitiprealpi),
    ("Veneto Segreto", "https://venetosegreto.com/eventi/", fetch_venetosegreto),
    ("il Tacco di Bacco", "https://iltaccodibacco.it/veneto/", fetch_tacco),
    ("Teatro La Fenice", "https://www.teatrolafenice.it/calendario/", fetch_fenice),
    ("Circolo Culturale Bellunese", "https://belcircolo.org/programma/", fetch_belcircolo),
    ("Musei di Bassano", "https://www.museibassano.it/it/mostre/in_corso", fetch_museibassano),
    ("Turismo FVG", "https://www.turismofvg.it/eventi/musica", fetch_turismofvg),
    ("Mart Rovereto", "https://www.mart.tn.it/mostre-eventi", fetch_mart),  # fuori regione (Trentino), richiesta esplicita
]

# Fonti utili senza dati scaricabili: compaiono come link nella pagina
LINKS = [
    ("TrevisoToday – eventi", "https://www.trevisotoday.it/eventi/"),
    ("Adorable Belluno – calendario", "https://adorable.belluno.it/calendar/#/eventi"),
    ("Crystal Tears – ricerca", "https://www.google.com/search?q=%22Crystal+Tears%22+coro+concerto"),
]


# ------------------------------------------------------- unione e dedup

def dedupe(events: list[Event]) -> list[Event]:
    """Stesso titolo nello stesso giorno = stesso evento; tiene la versione
    più ricca e somma l'evidenza Crystal Tears."""
    def richness(e: Event) -> int:
        return sum(bool(x) for x in (e.time, e.venue, e.town, e.img, e.price))

    best: dict[str, Event] = {}
    for e in events:
        t = norm(re.sub(r'^.*? \| ', '', e.title))
        # Le mostre cambiano sottotitolo da una fonte all'altra: bastano le prime parole
        key = f"{t[:20] if e.cat == MOSTRE else t}|{e.start}"
        cur = best.get(key)
        if cur is None:
            best[key] = e
            continue
        keep, other = (e, cur) if richness(e) > richness(cur) else (cur, e)
        keep.hl = keep.hl or other.hl
        if keep.cat == CONCERTI and other.cat == CLASSICA:
            keep.cat = CLASSICA
        keep.time = keep.time or other.time
        keep.town = keep.town or other.town
        keep.prov = keep.prov or other.prov
        best[key] = keep
    return list(best.values())


def run(out_path: Path) -> dict:
    ref = today()
    http = Http()
    all_events: list[Event] = []
    status = []
    for name, url, fn in SOURCES:
        t0 = time.time()
        try:
            evs = fn(http, ref)
            all_events += evs
            status.append({"name": name, "url": url, "ok": True, "count": len(evs)})
        except Exception as ex:  # una fonte rotta non deve fermare le altre
            traceback.print_exc()
            status.append({"name": name, "url": url, "ok": False, "count": 0,
                           "error": f"{type(ex).__name__}: {str(ex)[:160]}"})
        print(f"{name}: {status[-1]['count']} eventi ({time.time() - t0:.1f}s)"
              + ("" if status[-1]["ok"] else f"  ERRORE {status[-1]['error']}"), file=sys.stderr)

    limit = (ref + timedelta(days=HORIZON_DAYS)).isoformat()
    events = [e.finalize() for e in dedupe(all_events) if e.cat and e.start <= limit]
    events.sort(key=lambda e: (e.start, e.time or "99", e.title))
    data = {
        "generated": datetime.now(TZ).isoformat(timespec="minutes"),
        "sources": status,
        "links": [{"name": n, "url": u} for n, u in LINKS],
        "events": [{k: v for k, v in asdict(e).items() if v not in (None, "", 0, False)} for e in events],
    }
    # Se TUTTE le fonti falliscono, non sovrascrivere i dati buoni del giorno prima
    if not any(s["ok"] for s in status) and out_path.exists():
        print("Tutte le fonti in errore: mantengo il file precedente", file=sys.stderr)
        return data
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Scritti {len(events)} eventi in {out_path}", file=sys.stderr)
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "events.json"))
    run(Path(ap.parse_args().out))
