# Eventi culturali · Veneto e dintorni

Pagina personale (GitHub Pages) con concerti di musica classica e sacra, mostre e visite guidate
tra Belluno, Treviso, Venezia, il resto del Veneto e il Friuli occidentale. Gli eventi del
Gruppo Vocale **Crystal Tears** sono sempre in cima, qualunque filtro sia attivo.

## Come funziona

- `scraper/fetch_events.py` scarica le fonti, classifica gli eventi e scrive `data/events.json`.
- Il workflow `.github/workflows/aggiorna-eventi.yml` lo esegue ogni mattina e committa il JSON.
- `index.html` legge il JSON e mostra calendario e mostre in corso, con filtri salvati nel browser.

| Fonte | Cosa dà | Come |
|---|---|---|
| Visit Dolomiti Bellunesi | tutta la provincia di Belluno | JSON della pagina calendario |
| Dolomiti Prealpi | descrizioni (per trovare Crystal Tears e i concerti classici) | API REST The Events Calendar |
| Veneto Segreto | visite guidate in tutto il Veneto | API REST del sito |
| il Tacco di Bacco | classica/lirica e mostre (Veneto, Venezia, Treviso, Belluno, Pordenone) | dati strutturati schema.org |
| Teatro La Fenice | opera e concerti a Venezia | pagina calendario |
| Musei di Bassano | mostre temporanee dei Musei Civici di Bassano del Grappa | pagine mostre in corso e future |
| Circolo Culturale Bellunese | stagione concertistica di Belluno | pagine categoria (Classica, Matinée, Luglio al Borgo) |
| Turismo FVG | musica classica e mostre in Friuli | pagine elenco |
| Mart Rovereto | mostre del Mart (Rovereto e sedi di Trento): unica fonte fuori da Veneto/FVG, chip "Trentino (Mart)" | HTML di `/mostre-eventi` |

Fonti senza dati scaricabili, linkate in fondo alla pagina: TrevisoToday (blocca i client automatici),
Adorable Belluno (stessi dati di Visit Dolomiti Bellunesi), Instagram di Crystal Tears (richiede login).

## Ritocchi frequenti

- Evento nella categoria sbagliata → regole in `scraper/classify.py`.
- Comune finito in "Resto del Veneto" → aggiungilo in `scraper/towns.py`.
- Test: `python scraper/tests/test_parsers.py`.

Se una fonte inizia a bloccare GitHub (come capitato con The Space per il cinema), la pagina la
segna in rosso in fondo: in quel caso si fa girare lo script dal Mac con launchd, come per `cinema`.
