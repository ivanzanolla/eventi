"""Classificazione per parole chiave: musica classica/sacra, mostre, visite guidate.

Le regole sono volutamente esplicite: se un evento finisce nella categoria
sbagliata si corregge qui aggiungendo o togliendo un termine.
"""
import re

CLASSICA = "classica"   # musica classica, sacra, corale, lirica
CONCERTI = "concerti"   # altri concerti non chiaramente classici (nascosti di default)
MOSTRE = "mostre"
VISITE = "visite"

HIGHLIGHT_RE = re.compile(r"crystal\s*tears|\bgvct\b", re.I)

_CLASSICA_RE = re.compile(
    r"musica\s+(sacra|classica|antica|barocca|da\s+camera|corale|lirica|sinfonica)"
    r"|\bcor[oi]\b|\bcorale\b|\bcorali\b|vocal\s+group|gruppo\s+vocale|ensemble\s+vocale|voci\s+bianche"
    r"|\bcappella\s+(musicale|marciana)|\borchestra|\bsinfoni|filarmonic|\borgan[oi]\b|organistic"
    r"|requiem|\bmessa\s+(solenne|cantata|in\s)|\bvespri\b|\boratorio\b|\bcantata\b|stabat\s+mater|magnificat"
    r"|\bliric[ao]\b|\bopera\s+(lirica|buffa|seria)\b|quartetto|quintetto|\btrio\b|\bduo\b|pianofort|pianist|violin|violoncell"
    r"|clavicembal|\barpa\b|musica\s*antica|barocc|baroque|\barchi\b|madrigal|rinasciment|polifoni"
    r"|clarinett|\bflaut|\boboe|cornamus|\bviol[ae]\s+da\s+gamba|liuto"
    r"|chitarra\s+classica|recital|conservatorio|cameristic|concerto\s+di\s+santa\s+cecilia"
    r"|gran\s+concerto|concerto\s+dell.epifania|ceremony\s+of\s+carols|\bcarols?\b"
    r"|\bbach\b|mozart|beethoven|vivaldi|haydn|brahms|schubert|h[aä]e?ndel|puccini|rossini|monteverdi"
    r"|chopin|[cč]iajkovskij|tchaikovsky|ciaikovski|mahler|dvo[rř][aá]k|palestrina|pergolesi|britten",
    re.I,
)

# Segnali di musica non classica: prevalgono sui generici "concerto"/"musica"
_NON_CLASSICA_RE = re.compile(
    r"tribut|tribute|\bband\b|\brock\b|\bpop\b|jazz|blues|\bdj\b|\brap\b|metal|swing|\bmusical\b|\bcover|\bvibes\b"
    r"|bluegrass|country|reggae|karaoke|cugini\s+di\s+campagna|disco|gospel|folk|cantautor|hip\s*hop"
    r"|elettronic|techno|liscio|tango|sanremo|queen|vasco|pink\s+floyd|u2\b|morricone|film\s+history"
    r"|hollywood|buena\s+vista|beatles|candlelight",
    re.I,
)
_CONCERTO_RE = re.compile(r"concert|\bmusic|\bnote\b|\bsuon", re.I)

_MOSTRE_RE = re.compile(
    r"\bmostr[ae]\b|esposizion|\bpersonale\s+di\b|collettiva|retrospettiva|exhibition|\bin\s+mostra"
    r"|fotografi[ae]\b.*(di|tra|della)|rassegna\s+antologica|biennale\s+arte",
    re.I,
)
_VISITE_RE = re.compile(
    r"visit[ae]\s+guidat|visita\s+(a|al|alla|allo|ai|alle|in)\b|tour\s+guidato|percorso\s+guidato"
    r"|alla\s+scoperta|passeggiata\s+(storica|culturale|guidata)|apertura\s+straordinaria|itinerario\s+(storico|artistico)",
    re.I,
)
# Per i tag "escursioni/visite" di Visit Dolomiti Bellunesi: tieni solo le visite culturali
_VISITA_CULTURALE_RE = re.compile(
    r"visit|museo|musei|chies|villa|palazz|castell|storia|stori|scoperta|centro\s+storico|borgo|arte|abbazi|santuar",
    re.I,
)


def is_highlight(*texts: str) -> bool:
    return any(t and HIGHLIGHT_RE.search(t) for t in texts)


def classify(title: str, text: str = "", hint: str | None = None) -> str | None:
    """Ritorna la categoria o None se l'evento non interessa.

    hint: categoria già nota dalla fonte (es. 'classica' per la pagina
    'Classica e lirica' di una fonte, 'mostre', 'visite', 'musica' generica).
    """
    title = title or ""
    blob = f"{title} {text or ''}"

    if is_highlight(blob):
        return CLASSICA

    if hint in (CLASSICA, MOSTRE):
        return hint
    if hint == VISITE:
        return VISITE

    # Il titolo pesa più della descrizione: un "coro" citato di sfuggita in
    # una sagra non la rende un concerto.
    if re.search(r"\bmusical\b|karaoke|\bdj\b", title, re.I):
        return None
    if _NON_CLASSICA_RE.search(title):
        return CONCERTI if (hint == "musica" or _CONCERTO_RE.search(title)) else None
    if _CLASSICA_RE.search(title):
        return CLASSICA
    if _MOSTRE_RE.search(title):
        return MOSTRE
    if _VISITE_RE.search(title):
        return VISITE

    if hint == "visite_natura":  # tag escursioni/visite: solo se culturale
        return VISITE if _VISITA_CULTURALE_RE.search(title) else None

    if hint == "musica" or _CONCERTO_RE.search(title):
        # Decidi con la descrizione, se c'è
        if text and _CLASSICA_RE.search(text) and not _NON_CLASSICA_RE.search(text):
            return CLASSICA
        return CONCERTI
    return None
