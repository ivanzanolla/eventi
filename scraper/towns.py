"""Mappa comune -> sigla provincia per Veneto e Friuli Venezia Giulia.

Non è l'elenco ISTAT completo: copre i centri che compaiono davvero nelle fonti.
Un comune che manca finisce nella provincia di fallback della fonte
(o in "VEN"/"FVG" generico). Per aggiungerne uno basta una riga.
"""
import re
import unicodedata

_RAW = {
    "BL": """Belluno, Feltre, Sedico, Ponte nelle Alpi, Limana, Borgo Valbelluna, Mel, Trichiana,
        Lentiai, Santa Giustina, Cesiomaggiore, Pedavena, Fonzaso, Arsiè, Lamon, Sovramonte,
        Seren del Grappa, Quero Vas, Quero, Alano di Piave, San Gregorio nelle Alpi, Sospirolo,
        Alpago, Tambre, Chies d'Alpago, Farra d'Alpago, Puos d'Alpago, Pieve d'Alpago, Longarone,
        Soverzene, Castellavazzo, Val di Zoldo, Zoldo Alto, Forno di Zoldo, Zoppè di Cadore, Agordo,
        Alleghe, Falcade, Canale d'Agordo, Cencenighe Agordino, Rocca Pietore, Livinallongo del Col di Lana,
        Arabba, Selva di Cadore, Colle Santa Lucia, La Valle Agordina, Taibon Agordino, Voltago Agordino,
        Gosaldo, Rivamonte Agordino, Vallada Agordina, San Tomaso Agordino, Cortina d'Ampezzo,
        San Vito di Cadore, Borca di Cadore, Vodo di Cadore, Valle di Cadore, Pieve di Cadore,
        Calalzo di Cadore, Domegge di Cadore, Lozzo di Cadore, Auronzo di Cadore, Vigo di Cadore,
        Lorenzago di Cadore, Santo Stefano di Cadore, San Pietro di Cadore, Comelico Superiore,
        Danta di Cadore, San Nicolò di Comelico, Perarolo di Cadore, Ospitale di Cadore,
        Cibiana di Cadore, Sargnano, Nevegal, Misurina""",
    "TV": """Treviso, Conegliano, Castelfranco Veneto, Montebelluna, Vittorio Veneto, Oderzo,
        Mogliano Veneto, Asolo, Valdobbiadene, Pieve di Soligo, Follina, Cison di Valmarino, Susegana,
        San Vendemiano, Silea, Villorba, Paese, Preganziol, Casier, Roncade, Quinto di Treviso,
        Ponzano Veneto, Carbonera, Spresiano, Nervesa della Battaglia, Volpago del Montello,
        Crocetta del Montello, Cornuda, Maser, Possagno, Crespano del Grappa, Pieve del Grappa,
        Castelcucco, Monfumo, Fonte, Riese Pio X, Vedelago, Trevignano, Istrana, Morgano, Zero Branco,
        Resana, Loria, Castello di Godego, Altivole, Caerano di San Marco, Giavera del Montello, Arcade,
        Povegliano, Maserada sul Piave, Breda di Piave, San Biagio di Callalta, Monastier di Treviso,
        Zenson di Piave, Ponte di Piave, Salgareda, Chiarano, Gorgo al Monticano, Mansuè, Portobuffolè,
        Gaiarine, Codognè, Fontanelle, Mareno di Piave, Santa Lucia di Piave, Vazzola, San Polo di Piave,
        Ormelle, Cimadolmo, Motta di Livenza, Meduna di Livenza, Cessalto, Sarmede, Cordignano,
        Colle Umberto, Cappella Maggiore, Fregona, Tarzo, Revine Lago, Refrontolo, San Pietro di Feletto,
        Farra di Soligo, Moriago della Battaglia, Sernaglia della Battaglia, Vidor, Segusino, Miane,
        Orsago, Godega di Sant'Urbano, San Fior, Pederobba, Borso del Grappa, Cavaso del Tomba,
        Casale sul Sile, Cison, Solighetto, Lancenigo""",
    "VE": """Venezia, Mestre, Marghera, Lido di Venezia, Lido, Murano, Burano, Torcello, Chioggia,
        Sottomarina, San Donà di Piave, Portogruaro, Jesolo, Caorle, Eraclea, Mirano, Spinea, Mira,
        Dolo, Stra, Noale, Martellago, Scorzè, Salzano, Santa Maria di Sala, Marcon, Quarto d'Altino,
        Meolo, Musile di Piave, Fossalta di Piave, Noventa di Piave, Ceggia, Torre di Mosto,
        San Stino di Livenza, Annone Veneto, Pramaggiore, Gruaro, Cinto Caomaggiore, Teglio Veneto,
        Fossalta di Portogruaro, Concordia Sagittaria, San Michele al Tagliamento, Bibione,
        Cavallino-Treporti, Campagna Lupia, Camponogara, Fiesso d'Artico, Fossò, Vigonovo, Pianiga,
        Campolongo Maggiore, Cona, Cavarzere, Zelarino, Chirignago, Favaro Veneto""",
    "PD": """Padova, Abano Terme, Montegrotto Terme, Este, Monselice, Montagnana, Cittadella,
        Piove di Sacco, Arquà Petrarca, Camposampiero, Galzignano Terme, Teolo, Vigonza""",
    "VI": """Vicenza, Bassano del Grappa, Schio, Thiene, Valdagno, Asiago, Marostica, Nove,
        Noventa Vicentina, Arzignano, Lonigo, Montecchio Maggiore, Romano d'Ezzelino""",
    "VR": """Verona, Bardolino, Garda, Peschiera del Garda, Valeggio sul Mincio, Soave, Lazise,
        Bussolengo, San Bonifacio, Legnago, Malcesine, Villafranca di Verona""",
    "RO": """Rovigo, Adria, Porto Viro, Badia Polesine, Lendinara, Fratta Polesine, Porto Tolle""",
    "PN": """Pordenone, Sacile, Aviano, Piancavallo, Maniago, Spilimbergo, San Vito al Tagliamento,
        Azzano Decimo, Fiume Veneto, Porcia, Cordenons, Prata di Pordenone, Brugnera, Caneva,
        Polcenigo, Budoia, Fontanafredda, Roveredo in Piano, San Quirino, Zoppola,
        Casarsa della Delizia, Pasiano di Pordenone, Pravisdomini, Chions, Sesto al Reghena,
        Cordovado, Valvasone Arzene, Pinzano al Tagliamento, Montereale Valcellina""",
    "UD": """Udine, Cividale del Friuli, Palmanova, Aquileia, Lignano Sabbiadoro, Gemona del Friuli,
        Tolmezzo, Codroipo, San Daniele del Friuli, Tarvisio, Sappada, Majano, Latisana,
        Cervignano del Friuli, Trivignano Udinese, Tricesimo, Raveo, Muzzana del Turgnano,
        Passariano, Villa Manin""",
    "GO": """Gorizia, Monfalcone, Grado, Gradisca d'Isonzo, Staranzano, Cormons""",
    "TS": """Trieste, Muggia, Duino Aurisina, Duino""",
}

VENETO = {"BL", "TV", "VE", "PD", "VI", "VR", "RO"}
FVG = {"PN", "UD", "GO", "TS"}

# Nomi di provincia per esteso, usati da alcune fonti (es. Veneto Segreto)
PROVINCE_NAMES = {
    "belluno": "BL", "treviso": "TV", "venezia": "VE", "padova": "PD", "vicenza": "VI",
    "verona": "VR", "rovigo": "RO", "pordenone": "PN", "udine": "UD", "gorizia": "GO",
    "trieste": "TS",
}


def norm(s: str) -> str:
    s = (s or "").replace("’", "'").replace("‘", "'")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9' -]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


TOWN_TO_PROV: dict[str, str] = {}
for prov, block in _RAW.items():
    for name in block.split(","):
        name = name.strip()
        if name:
            TOWN_TO_PROV[norm(name)] = prov


def province_of(town: str | None, fallback: str | None = None) -> str | None:
    """Sigla della provincia di un comune; prova anche il primo pezzo di 'A, B' e '(XX)'."""
    if not town:
        return fallback
    m = re.search(r"\((BL|TV|VE|PD|VI|VR|RO|PN|UD|GO|TS)\)", town)
    if m:
        return m.group(1)
    for cand in [town] + re.split(r"[,/;-]", town):
        key = norm(cand)
        if key in TOWN_TO_PROV:
            return TOWN_TO_PROV[key]
    return fallback
