# Stabilità mobile — 6 ottobre 2026

## Aggiornamento: vortici dello sfondo — 7 ottobre 2026

Il sito pubblicato su GitHub Pages usa un fragment shader WebGL2 con rumore frattale a cinque ottave e un ciclo `requestAnimationFrame` continuo mentre l'hero è visibile. Su 390×844 il suo canvas interno misura 366×791 pixel, circa 290.000 frammenti per disegno; a 60 fotogrammi al secondo il limite teorico è circa 17 milioni di frammenti al secondo, oltre agli altri canvas della pagina. Lighthouse misura bene il caricamento ma non dimostra la fluidità sostenuta della GPU su un vecchio Android.

La versione locale usa un WebP statico da 72 KB su mobile e 79 KB su desktop. La versione animata usa lo stesso linguaggio visivo, tre ottave, una risoluzione interna di 148×321 pixel su 390×844, circa 12 disegni al secondo e un massimo di 30 fotogrammi. Interrompe il disegno durante lo scroll, fuori schermo e in background. Con 2 o 4 GB di RAM dichiarati, risparmio dati o movimento ridotto non crea alcun contesto WebGL. Rimangono attive le stelle legate allo scroll, già soggette al loro budget adattivo. La facciata 3D usa un'immagine mobile da 48 KB e viene caricata in anticipo; la variante occupata da 105 KB viene caricata solo al tocco.

| Lighthouse mobile, Chrome con rallentamento CPU | Sito pubblicato | Locale aggiornato |
| --- | ---: | ---: |
| CPU 4× — prestazioni | 99 | 100 |
| CPU 4× — accessibilità | 94 | 100 |
| CPU 4× — contenuto più grande (LCP) | 2,0 s | 1,8 s |
| CPU 6× — prestazioni | 99 | 99 |
| CPU 6× — LCP | 1,7 s | 1,8 s |
| CPU 6× — tempo di blocco (TBT) | 90 ms | 70 ms |
| CPU 6× — lavoro sul thread principale | 3,1 s | 0,7 s |

Il confronto riguarda pagine diverse e server diversi: GitHub Pages comprime l'HTML, mentre il server locale Python lo invia senza compressione; il sito locale include anche scuola e circolari assenti nella versione pubblicata. I punteggi non isolano il costo dello shader. Il codice e il limite di fotogrammi mostrano che il vecchio effetto è più rischioso per fluidità, calore e batteria, mentre la nuova variante lascia la stessa atmosfera ai telefoni lenti senza animazione continua.

Controllati nel browser 320×568, 390×844, 430×932, 844×390 e 1280×720: nessuno sforamento orizzontale o contatto tra testo e scuola. A 320 px la scena occupata carica il WebP mobile, mostra la gru e conserva il parallax allo scroll. Lo shader desktop si ferma a 100 fotogrammi senza errori in console; quello mobile si ferma a 30. I controlli automatici verificano il fallback statico per 2/4 GB, risparmio dati e movimento ridotto. Lighthouse con CPU rallentata non sostituisce una prova di FPS, temperatura e batteria su un Android fisico economico.

## Interventi

- Rimossi i vecchi cursori luminosi, particelle al tocco, lettere magnetiche, lente, sensori di movimento e giochi obbligatori. Le stelle formano un campo prospettico dorato a tutta pagina e accelerano quando si scorre. Nessun effetto legato al cursore o al tocco.
- Un solo ciclo Canvas 2D anima lo sfondo: 80 stelle a 15 FPS sui dispositivi a basso consumo, 180 a 24 FPS su mobile, 350 a 30 FPS su desktop. Il costo cala automaticamente se il disegno rallenta; il ciclo si ferma in background e con movimento ridotto. Reveal di 360 ms senza blur; pendolo SVG attivo solo durante il gesto e fino all’arresto, poi si ferma fuori schermo o con movimento ridotto.
- Apertura con stelle e facciata frontale simmetrica del Liceo Archimede in un blocco separato sotto i pulsanti. Scuola ridotta con render 3D WebP di circa 246 KB, prospettiva, profondità e ombra mosse solo durante lo scroll; la targa “ARCHIMEDE” separata è stata rimossa. Cielo, testo e facciata avanzano a velocità diverse, riprendendo il principio a livelli del parallax indicato dall’utente. Un tocco carica a richiesta una seconda scena 3D WebP trasparente di circa 435 KB, con gru, folla, bandiere, fumogeni e striscioni; un secondo tocco ripristina la facciata. Lo sfondo riprende la profondità di HyperspaceWarpDrive (21st, catalogo 7943), adattata al canvas esistente. Nessuna nuova dipendenza del sito.
- Budget adattivo: dopo disegni oltre 6 ms o frame oltre 90 ms ripetuti, riduce la quantità di stelle e il ritmo di disegno; se il sovraccarico continua con 48 stelle, ferma il canvas animato e lascia il cielo statico. È una protezione, non una certificazione delle prestazioni su ogni telefono.
- Lampadina nel flusso della pagina, con area riservata di 240 px. Trascinamento orizzontale nella direzione corretta, limitato a circa 13 gradi. Scroll verticale e zoom restano disponibili. Tap e tastiera accendono/spengono.
- Menu scrollabile anche in orizzontale, con chiusura interna, Escape, focus confinato, attributi ARIA e contenuto sottostante inattivo. Chiusura automatica passando al layout desktop. Navigazione alternativa senza JavaScript.
- Ripristinate ancore e posizione del browser. Navigazione diretta senza scorrimento animato attraverso le sezioni asincrone.
- Griglie con colonne che possono restringersi; statistiche in una colonna sotto 400 px; date in colonne adattive. Input almeno 16 px, comandi principali almeno 44 px, microtesti ingranditi e focus visibile.
- Collegamento Instagram sempre utilizzabile. Nessun gesto nascosto per sbloccarlo.
- Feed caricati quando la sezione si avvicina; timeout a 8 secondi, collegamenti ufficiali di fallback. Instagram in gruppi di 6 post; circolari in gruppi di 12, ricerca con debounce e messaggio per date invertite.
- 151 JPEG progressive ottimizzati, originali conservati. Manifest per le immagini già preparate; fallback agli originali per immagini nuove. Il workflow Instagram prepara le varianti alle successive esecuzioni manuali.
- Nomi e organi dei candidati con heading semantici; etichette di classe sopra le foto; iniziali decorative escluse dai lettori di schermo.

## Misure

| Elemento | Prima | Dopo |
| --- | ---: | ---: |
| HTML per pagina | 176 KB | circa 79 KB |
| Canvas nella pagina | 6 | 1 Canvas 2D leggero, condiviso per tutto lo sfondo |
| Eventi globali che seguono mouse/dito/sensori | presenti | 0 |
| 14 ritratti | 3,19 MB | 1,66 MB |
| Prime 12 immagini Instagram | 2,43 MB | 1,02 MB |
| Tutte le immagini Instagram | 19,85 MB | 9,09 MB |

Le misure delle immagini confrontano i file originali con le varianti. Il caricamento effettivo avviene su richiesta e in gruppi più piccoli.

## Verifiche effettuate

- Browser integrato: 320×568, 375×667, 390×844, 430×932, 568×320, 768×1024, 844×390, 1024×768, 1100×800 e 1366×768. Nessun elemento del contenuto oltre i bordi orizzontali rilevato.
- Test del reflow con dimensione di base del testo al 200%: 320, 375, 430 px e landscape 568×320. Nessun overflow rilevato.
- Menu: apertura/chiusura, focus, Escape, scroll in landscape e navigazione alle sezioni. Link diretto index.html#scuola conserva l’ancora e lascia il titolo sotto la barra.
- Circolari: ricerca “assemblea”, intervallo settembre 2026, PDF diretto, intervallo invertito, reset e caricamento 12→24 righe.
- Instagram: immagini ottimizzate quadrate, batch 6→12 e nessun overflow.
- Lampadina: tap/tastiera, drag, annullamento, secondo dito, movimento ridotto, background, uscita dal viewport. Test del pendolo: arresto in 116 frame iniziali e 188 frame dopo il gesto simulato, a 60 Hz.
- Budget animazioni: simulati disegni da 12 ms; verificato il passaggio al cielo statico e l’assenza di nuove animazioni dopo ulteriori scroll. Non è una misura FPS su hardware reale.
- Nuova apertura: controllata a 1280×720, 390×844, 320×568 e 844×390; nessun overflow orizzontale a 320 e 844 px, console senza errori. Review 21st: zero segnalazioni sui due HTML.
- Scena occupata con gru: controllo visivo a 1280×720 e 390×844; a metà scroll mobile la facciata si sposta di circa 36 px, il testo di 16 px e il cielo di 28 px, senza overflow orizzontale.
- Stelle: controllo visivo delle scie nel browser mobile e console senza errori; test delle coordinate finite, delle code limitate, dell’arresto a riposo, in background e al cambio della preferenza di movimento.
- Fetch: successo, HTTP 503, errore di rete, JSON malformato, timeout e pulizia del timer. Observer: una sola richiesta e disconnessione.
- Sintassi JavaScript valida; nessun errore/warning osservato nella console della versione rifatta. Asset, ID, frammenti e feed verificati offline. index.html ed eureka.html identici.

## Comandi ripetibili

```sh
python3 scripts/check-site.py
node scripts/check-runtime.mjs
python3 scripts/optimize-images.py
```

I primi due non richiedono pacchetti aggiuntivi. L’ottimizzazione usa Pillow, già disponibile localmente; il workflow lo installa sul runner. Non esiste un build del sito.

## Limiti e contenuti da validare

Non è una misura FPS su telefoni Android economici reali né un audit Lighthouse con CPU/rete rallentate. Il controllo responsive usa il browser integrato; serve una prova fisica su Android per quantificare fluidità, memoria e tempi su un dispositivo specifico. Nessuna promessa di compatibilità con ogni browser storico.

La timeline e la campagna conservano i contenuti 2025–2026. Le etichette “in corso”/“in arrivo” e i progetti proposti richiedono validazione editoriale prima di una nuova campagna; le date reali non sono state inventate. Il workflow Instagram resta manuale, come già configurato. Le circolari mantengono il loro aggiornamento programmato.

## Aggiornamento 8 ottobre 2026

- 8 ottobre: riallineata la prospettiva al componente HyperspaceWarpDrive di 21st.dev e alla versione pubblicata: 80 stelle a 15 FPS sui dispositivi che dichiarano poca memoria o risparmio dati, 180 a 24 FPS su mobile, 350 a 30 FPS su desktop. Il canvas fisso accompagna tutto lo scroll, lascia scie dorate per persistenza e rallenta tra uno scroll e l'altro. Nessuna dipendenza Three.js aggiunta; il canvas si ferma in background, con movimento ridotto e se rileva sovraccarico. Lighthouse mobile: 97/100, LCP 2,3 s, TBT 110 ms, CLS 0. Test automatici e screenshot mobile verificati; resta necessaria una prova fisica su Android economico.
- Galleria Instagram: i due post del 2026 e il dato di 2.535 follower sono stati salvati localmente da Behold. A ogni visita Behold fornisce gli ultimi sei post e il conteggio corrente; l'archivio locale copre i vecchi post e le interruzioni della rete. Le immagini nuove hanno anche una copia JPEG locale ottimizzata.
- Verifica nel browser mobile: primi due post datati 4 ottobre e 20 agosto 2026, follower 2.535, link diretti ai post, immagini visibili. `check-site.py` controlla 139 post e 162 asset; `check-runtime.mjs` passa. Due misure Lighthouse mobile simulate hanno dato 71 e 96/100; la prima include un'attività anomala di 1,94 s nello script di misurazione di Lighthouse. Il risultato non certifica la fluidità su Android fisici economici.
