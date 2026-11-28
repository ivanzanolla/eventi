"""Test dei parser su estratti reali delle fonti (novembre 2026).

python -m pytest scraper/tests  oppure  python scraper/tests/test_parsers.py
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_events as fe  # noqa: E402
from classify import CLASSICA, CONCERTI, MOSTRE, VISITE, classify  # noqa: E402
from towns import province_of  # noqa: E402

FX = Path(__file__).parent / "fixtures"
REF = date(2026, 11, 21)


def test_classify():
    assert classify("37^ Rassegna di Musica Sacra \"Don Sergio Manfroi\"") == CLASSICA
    assert classify("Concerto Corale") == CLASSICA
    assert classify("Messa Solenne di  Santa Cecilia - Coro Parrocchiale San Giacomo") == CLASSICA
    assert classify("Gran concerto dell’Epifania") == CLASSICA
    assert classify("Velvet Dress – U2 Tribute Band") is None
    assert classify("Innuendo Experience – The Ultimate Queen Celebration", "", "musica") == CONCERTI
    assert classify("Chris Jones e Paolo Ercoli in Concerto") == CONCERTI
    assert classify("Rassegna Antologica") == MOSTRE
    assert classify("Scacchi: scopri e sfida") is None
    assert classify("A Ceremony of Carols") == CLASSICA
    assert classify("Concerto di Natale", "il Gruppo Vocale Crystal Tears presenta") == CLASSICA
    assert classify("Ciaspolata al chiaro di luna", "", "visite_natura") is None
    assert classify("Visita guidata al Museo Diocesano", "", "visite_natura") == VISITE
    assert classify("Laboratorio per bambini") is None
    assert classify("Saverio Tasca Vibes Trio") is None
    assert classify("Vespri in Cattedrale – Incontro musicale") == CLASSICA
    assert classify("Michelangelo Da Caravaggio - A Rebel Rock Musical") is None


def test_towns():
    assert province_of("Cortina d'Ampezzo") == "BL"
    assert province_of("Conegliano") == "TV"
    assert province_of("Mestre") == "VE"
    assert province_of("Trieste, Muggia") == "TS"
    assert province_of("Sacile") == "PN"
    assert province_of("Paesino Ignoto", "BL") == "BL"


def test_visitdolomitibellunesi():
    payload = json.loads((FX / "vdb.json").read_text())
    evs = fe.parse_visitdolomitibellunesi(payload, REF)
    titles = {e.title: e for e in evs}
    assert "Cut to Cortina!" not in titles                    # non culturale
    assert titles["Rassegna Antologica"].cat == MOSTRE
    assert titles["Rassegna Antologica"].prov == "BL"
    cc = [e for e in evs if e.title == "Concerto Corale"]
    assert len(cc) == 2 and cc[0].start == "2026-11-28" and cc[0].more == 1
    assert cc[0].url.endswith("?day=2026-11-28")


def test_dolomitiprealpi():
    events = json.loads((FX / "prealpi.json").read_text())
    evs = fe.parse_dolomitiprealpi(events, REF)
    ct = [e for e in evs if e.hl]
    assert len(ct) == 1 and ct[0].cat == CLASSICA and ct[0].prov == "BL" and ct[0].time == "20:30"
    assert not any(e.title.startswith("Scacchi") for e in evs)


def test_venetosegreto():
    evs = fe.parse_venetosegreto((FX / "venetosegreto.html").read_text(), REF)
    assert len(evs) == 2
    v = evs[0]
    assert v.cat == VISITE and v.prov == "VI" and v.start == "2026-11-22" and v.more == 1
    assert v.price == "16€" and v.venue == "Ville venete"


def test_tacco():
    evs = fe.parse_tacco((FX / "tacco.html").read_text(), CLASSICA, REF)
    assert [e.title for e in evs] == ["Concerto di Natale", "Vespri in Cattedrale con Dennis Barezzani e Su Yu"]
    assert evs[0].prov == "VE" and evs[0].venue == "Palazzetto Bru Zane"
    assert evs[1].prov == "VR"


def test_fenice():
    evs = fe.parse_fenice((FX / "fenice.html").read_text(), REF)
    assert [(e.start, e.time, e.title) for e in evs] == [
        ("2026-11-27", "19:00", "Fedora"),
        ("2027-01-01", "11:15", "Concerto di Capodanno 2027"),
    ]


def test_turismofvg():
    evs = fe.parse_turismofvg((FX / "turismofvg.html").read_text(), "Musica", REF)
    assert [(e.title, e.town, e.prov, e.time) for e in evs] == [
        ("FEMART - Festival MusicAntica e Arti - APPUNTI DI VIAGGIO Baroque Stories - Opposte traiettorie. "
         "Gli archi tra Venezia e la Mitteleuropa", "Udine", "UD", "18:00"),
    ]
    mostre = fe.parse_turismofvg((FX / "turismofvg.html").read_text(), "Mostre", REF)
    assert [(m.title, m.prov, m.start) for m in mostre] == [("Dialogo fra Linee ed Emozioni", "UD", "2026-11-21")]


def test_belcircolo():
    evs = fe.parse_belcircolo((FX / "belcircolo.html").read_text(), REF)
    assert [(e.title, e.start, e.time, e.town, e.venue, e.prov) for e in evs] == [
        ("Trio Mythos", "2026-12-05", "17:30", "Belluno", "Auditorium Comunale", "BL"),
        ("LEONARDO MABILIA pianoforte", "2027-01-10", "10:30", "Belluno", "Palazzo Crepadona", "BL"),
    ]
    assert evs[0].price.startswith("Interi € 20")


def test_museibassano():
    evs = fe.parse_museibassano((FX / "museibassano.html").read_text(), REF)
    got = [(e.title[:40], e.start, e.end, e.venue) for e in evs]
    assert got == [
        ('Il Ritorno del "Cavallo Colossale" di An', "2026-12-12", "2027-03-12", "Museo Civico di Bassano del Grappa"),
        ("Sebastião Salgado. Fotografie della Coll", "2026-10-24", "2027-04-04", "Museo Civico di Bassano del Grappa"),
        ("Oltre i ricettari. Dietetica, ittiologia", "2026-10-30", "2027-02-20", "Biblioteca Civica"),
    ], got
    assert all(e.prov == "VI" and e.cat == MOSTRE for e in evs)
    # stessa mostra dal Tacco di Bacco con sottotitolo diverso: una sola voce
    tacco = fe.Event(title="Sebastião Salgado. Fotografie della collezione della Maison Européenne",
                     cat=MOSTRE, start="2026-10-24", end="2027-04-04", url="t", src="il Tacco di Bacco")
    assert len(fe.dedupe([evs[1], tacco])) == 1


def test_mart():
    evs = fe.parse_mart((FX / "mart.html").read_text(), REF)
    got = [(e.title, e.start, e.end, e.venue, e.town, e.prov) for e in evs]
    assert got == [
        ("Water Flow. Acqua, arte, scienza, umanità", "2026-10-10", "2027-06-06", "Palazzo delle Albere", "Trento", "TN"),
        ("Il Gruppo 7 e la nascita del Razionalismo italiano", "2026-10-23", "2027-01-17", "Mart Rovereto", "Rovereto", "TN"),
        ("Gianni Berengo Gardin. Mondi da abitare", "2026-10-24", "2027-02-14", "Mart Rovereto", "Rovereto", "TN"),
        ("Fronti opposti. Arte italiana tra Guttuso e Vedova", "2026-11-28", "2027-04-04", "Mart Rovereto", "Rovereto", "TN"),
        ("Marta Spagnoli. Fotofinish", "2026-12-05", "2027-03-29", "Galleria Civica Trento", "Trento", "TN"),
        ("Walter Moroder. Presënza", "2026-12-05", "2027-03-29", "Galleria Civica Trento", "Trento", "TN"),
    ], got
    assert all(e.cat == MOSTRE and e.url.startswith("https://www.mart.tn.it/mostre/") for e in evs)


def test_dedupe_merges_highlight():
    a = fe.Event(title="A Ceremony of Carols", cat=CLASSICA, start="2026-12-21", url="u1", src="VDB",
                 town="Belluno", venue="Chiesa di Sargnano")
    b = fe.Event(title="A Ceremony of Carols", cat=CLASSICA, start="2026-12-21", url="u2", src="Prealpi", hl=True)
    out = fe.dedupe([a, b])
    assert len(out) == 1 and out[0].hl and out[0].venue == "Chiesa di Sargnano"
    c = fe.Event(title="Voci Spezzate, Voci Salvate: l'opera lirica", cat=CLASSICA, start="2026-11-21", url="a", src="x")
    d = fe.Event(title="Voci Spezzate, Voci Salvate: l’opera lirica", cat=CLASSICA, start="2026-11-21", url="b", src="y")
    assert len(fe.dedupe([c, d])) == 1


def test_fonte_in_errore_riusa_eventi_precedenti(tmp_path=None):
    import tempfile
    from datetime import timedelta
    d = Path(tempfile.mkdtemp())
    out = d / "events.json"
    ref = fe.today()
    fut = (ref + timedelta(days=10)).isoformat()
    past = (ref - timedelta(days=10)).isoformat()
    old = [{"title": "Viva", "start": past, "end": fut, "src": "Rotta", "cat": "mostre"},
           {"title": "Finita", "start": past, "end": past, "src": "Rotta", "cat": "mostre"},
           {"title": "Altra", "start": fut, "src": "Sana", "cat": "mostre"}]
    out.write_text(json.dumps({"events": old}))
    def rotta(http, r):
        raise RuntimeError("giu")
    def sana(http, r):
        return [fe.Event(title="Nuova", cat=MOSTRE, start=fut, url="u", src="Sana")]
    saved = fe.SOURCES
    fe.SOURCES = [("Rotta", "x", rotta), ("Sana", "y", sana)]
    try:
        data = fe.run(out)
    finally:
        fe.SOURCES = saved
    titles = [e["title"] for e in data["events"]]
    assert titles == ["Viva", "Nuova"], titles  # niente 'Finita' (scaduta) né 'Altra' (fonte sana, non più presente)
    assert data["sources"][0]["stale"] == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
