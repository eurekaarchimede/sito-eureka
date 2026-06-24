# CLAUDE.md — eureka!

Documento di contesto per Claude Code. Stato del progetto e decisioni di design.

---

## 1. Il progetto

Sito web one-page per **eureka!**, lista di rappresentanza d'istituto del **Liceo Scientifico Archimede** di Messina (~1.500 studenti, fondata nel 2018, Instagram: [@eureka.archimede](https://instagram.com/eureka.archimede)).

**Obiettivo**: presenza online della lista durante la campagna elettorale studentesca per l'edizione **2025–2026**. Comunica progetti, eventi, candidati, storia. Indirizza verso Instagram.

**Audience**: ~1.500 studenti del liceo, età 14–19. Fruizione prevalentemente da mobile.

**Aggancio concettuale**: *Eureka* è l'esclamazione di Archimede — il nome della lista e il nome della scuola formano un loop. Sviluppato visivamente con il tema della **lampadina che si accende** (idea → lampadina → scoperta → eureka).

---

## 2. Stack tecnico

- **Single-file HTML**: `eureka.html` (~2.300 righe). Nessun build step. Zero librerie esterne (Three.js rimosso).
- **CSS**: vanilla, dentro `<style>`. CSS variables, `clamp()`, grid.
- **JS**: vanilla, dentro `<script>` classici. Canvas 2D per starfield warp + starfield globale con meteore.
- **Animazioni (giugno 2026)**: hero "neon ignition" (lettere che si accendono con flicker da insegna), scramble/decode sui titoli, tilt 3D + glare oro sulle card, bottoni magnetici, filo di corrente (scroll progress oro in cima), timeline che si illumina allo scroll con scintilla viaggiante, count-up sulle statistiche, marquee velocity-aware (accelera/skewa con lo scroll), nav glassmorphism hide/show, reveal con blur + stagger, scintille WAAPI al click sul "!" dell'hero, parallax hero al mouse. Tutto gated su `prefers-reduced-motion` e `(hover: hover)` dove serve.
- **Moduli "wow" (giugno 2026, seconda ondata)**:
  - **Shader Van Gogh** (`#hero-shader`): WebGL2 fragment shader nell'hero — fbm 5 ottave + domain warping + 3 vortici "swirl" in deriva, attratti dal mouse. Palette blu/cobalto con creste oro rare. DPR cap 1.25 × scala 0.75, IO pause, RM = frame statico, fallback canvas.remove().
  - ~~**Interruttore a cordicella**~~ — RIMOSSO (giugno 2026): la cordicella lights-out (velo scuro + torcia) è stata tolta su richiesta (poco utile). Spariti `.pull-cord`, `.dark-veil`, `.torch-glow`, `body.lights-out`, il modulo JS light-switch e l'`#lamp::after`. Conservata solo `nav { transition }` per il hide/show.
  - **Lampadina a pendolo** (`#bulb-rig` in `.illuminated`, left 68% / 76% mobile): SVG con fisica reale (g/L≈6.3, damping, spinta idle), click = on/off → la sezione si accende/spegne (`.bulb-lit`/`.bulb-dark`). Auto-on alla prima visibilità. Repulsione dal mouse vicino. **Drag RELATIVO** (`downAngle + (clientX − downX) * k`, `k = 2.2/innerWidth`, clamp ±1.1 rad): lo spostamento orizzontale dal punto di presa pilota l'angolo → oscilla **simmetrica in entrambi i versi** anche se pende vicino al bordo destro (prima usava `atan2` dalla posizione assoluta del dito: a destra lo spazio finiva → oscillava solo verso sinistra).
  - **Word illumination** (`.word-lit .w`): parole dei paragrafi `.storia .lede` e `.illuminated-content > p` splittate in span (markup inline preservato), accese progressivamente dallo scroll, frontiera con glow oro. Solo opacity (mai color). Fix background-clip per il p della illuminated.
  - **Costellazione** (`#constellation` in `.candidati`): ~28 stelle (rejection sampling) + linee tra vicine, draw-in scaglionato all'ingresso, twinkle, linee oro dal cursore alle stelle entro 160px. 30fps, IO gated.
  - **Scia di luce** (`#trail-canvas`, z49): particelle dorate dietro il mouse (cap 90, additive, auto-sospensione) + onda d'urto a 2 anelli al click sul "!" (`window.__eurekaShockwave`).
  - **Lettere magnetiche**: gli span dell'h1 hero (tranne il "!") respinti dal cursore con fisica a molla dopo `animationend` (rimozione animation + opacity inline). Loop auto-sospeso a riposo. Su touch: il dito scaccia le lettere (touchstart/move), al rilascio tornano con la molla.
- **Mobile wow pack (giugno 2026)** — su touch il dito sostituisce il cursore:
  - **Alone caldo a dito** (`#touch-glow`, z48): su touch il dito è la sorgente di luce. Un alone radiale caldo (gradient oro/cream con core acceso, `mix-blend-mode: screen`) blooma al `touchstart` e segue il dito anche durante lo scroll (solo transform+opacity → compositor, niente repaint di box-shadow). Sfuma al `touchend`. È l'equivalente mobile di `#lamp` (che è desktop-only, `hover:hover`). Sostituisce la vecchia "scia touch" di scintille al touchmove, che durante lo scroll passava inosservata: ora la scia di particelle (`#trail-canvas`) su mobile resta SOLO come burst deliberato al tap + onda d'urto, niente più spawn al touchmove.
  - **Burst al tap**: ogni touchstart spawna ~10 scintille radiali nel punto toccato (`window.__eurekaBurst(x, y, n)` — no-op con RM).
  - **Nebulosa a dito**: i vortici Van Gogh inseguono il dito; il gyro (Android) tace per 2.5s dopo l'ultimo tocco (`fingerUntil`).
  - **Shake-to-eureka**: devicemotion (Android only — iOS richiede permission → skip): energia accumulata con decadimento 0.88, soglia 55, cooldown 2.8s → flash dorato fullscreen (z120, WAAPI) + shockwave + burst + vibrazione.
  - **Scroll = iperspazio** (`#hero-starfield`): lo scroll inietta velocità nel warp starfield → le stelle si allungano in scie d'oro (iperspazio) mentre scorri, poi rientro morbido alla deriva. `warpBoost = min(22, warpBoost + |Δscroll|·0.45)`, decadimento `·0.90`/frame, `speed = SPEED + warpBoost`. Il canvas è `position:fixed` fullscreen → l'effetto si vede su tutto lo sfondo durante lo scroll, non solo nell'hero. Gated su RM. È IL gesto mobile (lo scroll) trasformato in spettacolo.
  - **Tap = accendi** (`.card.ignite`, `.member.ignite`): toccare una card progetti/candidati la accende come una lampadina — flicker da insegna (`@keyframes cardIgnite`, stessa firma di `bulbIgnite`) + 8 scintille (`__eurekaBurst`) nel punto toccato + bordo oro. Solo su `(hover:none)` (su desktop c'è già il glare oro all'hover), gated su RM. `closest('.progetti .card, .candidati .member')` in delega su `touchstart`; classe rimossa su `animationend`. Le card sono semi-trasparenti sopra il warp → l'accensione glowa bordo+interno.
- **Feature wow (giugno 2026, terza ondata — brainstorm a giudici)**: hook globali `window.__eurekaWarp(n)` (inietta warpBoost, cap 40) e `window.__eurekaWish(dir)` (stella cadente direzionale dorata nello starfield, `wish:true` → render più marcato), oltre ai preesistenti `__eurekaBurst/__eurekaShockwave`.
  - **Versa l'acqua / vasca di Archimede** (`.vasca`, tra storia e illuminated): canvas `.vasca-canvas` con un fluido d'oro che slosha (superficie = retta inclinata `tan(tilt)` + 2 seni, `slosh` decade 0.96/frame). Mobile: gyro `deviceorientation.gamma` (iOS via bottone `.vasca-tilt-btn` per `requestPermission`, Android auto) + fallback drag del dito. Desktop: il mouse x pilota il tilt (prompt cambiato in "muovi il mouse"). `|tilt|>0.36` → `.spilled` → "eureka!" flash (`@keyframes vascaEureka`) + shockwave + burst + warp + vibrazione (cooldown 2.6s). IO-pause, DPR cap 1.5, 40fps. RM → canvas nascosto, testo statico. È il mito della vasca reso gesto.
  - **Accendi la lista** (`.cta.armed`/`.cta.lit`, `#cta-switch`): nella CTA un interruttore hold-to-charge; tieni premuto (`pointerdown`, barra `--p` su rAF, `DUR 900ms`) → al pieno `light()`: `.lit` (h2 `bulbIgnite` + IG link riacceso) + `__eurekaWarp(30)` + shockwave + burst. Stato in sessionStorage (chi torna trova acceso). **Progressive**: senza JS o con RM la CTA è già accesa (`.armed` aggiunto solo da JS dim + mostra switch). Enter/Spazio = accende diretto (a11y).
  - **Hold-to-charge globale** (`#charge-ring`, `.section-charged`): tieni premuto FERMO su una sezione → anello d'energia oro (conic-gradient + mask) cresce sotto il dito; al pieno (~850ms) scarica che accende quella sezione (`@keyframes sectionCharge`) + shockwave + burst + warp. **Scroll-safe**: `pointermove > 14px` o `scroll` annullano (= sta scrollando). `SKIP` su elementi interattivi/con gesti propri (a, button, .card, .member, .cta-switch, ecc.). Gated su RM.
  - **Circuito del programma** (`.circuit`, generato in JS prima della `.progetti .grid`): i 6 punti del programma come nodi-lampadina su un circuito; si accendono uno a uno scorrendo (IO threshold 0.6) o al tap/click, i fili (`.circuit-wire.lit`, scaleX) si illuminano tra nodi accesi, accesi tutti e 6 la `.circuit-master` "!" divampa (`bulbIgnite` + burst + shockwave). Stato in `localStorage` (`eureka-circuit`). Progressive: senza JS resta l'elenco di card.
  - **Stella cadente (flick)**: su touch/Android un colpetto secco del polso (`devicemotion.acceleration.x > 13`, edge-trigger + cooldown 650ms) lancia `__eurekaWish(dir)` nella direzione dello scatto + vibrazione + hint "esprimi un desiderio". Convive con lo shake-to-eureka (quello accumula energia, questo è il singolo spike). iOS skip (requestPermission).
- **Font**: `DM Sans` variable, **self-hosted** in `fonts/` (`dmsans-latin.woff2` + `dmsans-latin-ext.woff2`, ~93KB tot). `@font-face` con `font-weight: 100 1000` + `<link rel="preload">`. Niente più dipendenza da `fonts.googleapis.com` (su mobile con rete lenta Google Fonts a volte non caricava → fallback system-ui = "font alterato"). Self-host garantisce DM Sans su ogni telefono.
- **Asset**: cartella `foto/` (ritratti candidati, **ottimizzati** giugno 2026: 720px larghi, JPEG q62, ~220KB l'uno invece di ~570KB → 7.8MB→3.1MB tot, caricano sul mobile; tutti `loading="lazy" decoding="async"`) + `assets/projects/` (locandine progetti, ora inutilizzate — la gallery è live).
- **Feed Instagram live (giugno 2026)**: la gallery in `.progetti` (`#proj-gallery-grid`) mostra **tutti** i post di @eureka.archimede, paginati a blocchi di 12 (bottone `.proj-more` "mostra altri (N)"). Card `<a>` → permalink del post, badge carosello/video, data + like, placeholder col colore dominante, caption via `textContent` (no injection). Due sorgenti con fallback a cascata nel modulo JS `load()`:
  1. **`assets/ig/feed.json`** (primaria) — generato dalla GitHub Action `.github/workflows/ig-feed.yml` (cron ogni 3h) che esegue `scripts/fetch-ig.mjs`: API Meta ufficiale (Instagram Graph), scarica TUTTI i post paginati + immagini in `assets/ig/*.jpg` (gli URL diretti IG scadono → copie locali), committa. Il token long-lived sta cifrato in `data/token.enc` (AES-256-GCM, chiave `ENC_KEY` secret) e si auto-rinnova a ogni run (`refresh_access_token`) → non scade mai. Bootstrap dal secret `IG_TOKEN`. Setup utente: `SETUP-INSTAGRAM.md`.
  2. **Behold** (`https://feeds.behold.so/LUPhA0MWLASmG03Yef0U`) — fallback se `feed.json` assente (Action non ancora girata): ultimi 6 post, immagini proxate `sizes.medium`.
  3. **Link al profilo** — fallback finale su errore.
  Schema unificato via `normalize(feed, source)`. Reveal con IO locale (le card arrivano dopo il setup dell'IO globale).

**Hosting consigliato**: GitHub Pages, Netlify o Vercel. Drag-and-drop e via.

**Browser target**: ultimi 2 anni. WebGL2 + ES modules + CSS moderno richiesti. Niente fallback.

---

## 3. Riferimento di design

**Sito sorgente**: [oryzo.ai](https://oryzo.ai) (Lusion, 2026 — Awwwards SOTD, CSSDA).

Codici visivi presi da Oryzo:

- **Palette ridotta** (qui blu notte + oro, vedi sotto).
- **Editorial/magazine**: framing tipo "ISSUE NO. 001", scheda tecnica, marquee.
- **Typography massiccia**: tipo "lancio prodotto".
- **WebGL/3D**: cerchi rotanti, oggetto centrale interattivo, cursor custom.

**Riferimento esteso**: la lampadina sostituisce concettualmente il sottobicchiere di Oryzo. Stesso pattern: oggetto fotorealistico al centro dell'hero, ruotabile, con UI editoriale a corredo (specifiche tecniche ai 4 angoli).

---

## 4. Decisioni di design

### Palette (CSS variables in `:root`)

```css
--bg:        #0a1632;   /* blu notte profondo (sfondo) */
--bg-soft:   #11204a;   /* hover/secondary background */
--gold:      #f5cd47;   /* giallo cadmio delle stelle (accent) */
--gold-dim:  #c9a52e;
--cream:     #f7eed5;   /* highlight testo / testo principale */
--cream-dim: #c9beae;
--muted:     #6b5d50;
--line:      rgba(247, 238, 213, 0.12);
```

> **Nota**: la palette è cambiata rispetto al concept iniziale (nero + arancio). Ora è **blu notte + oro/cream** — coerente con il tema "stelle / lampadina / scoperta notturna".

**Regola d'oro**: l'oro è un accento. Usato per: brand "!", labels, glow, hover, citazioni. Mai per blocchi di testo lunghi.

### Tipografia

- **`DM Sans`** (variable sans-serif, self-hosted) — unico font del sito: display, body, labels, microcopy. `--display: "DM Sans", system-ui, sans-serif`. Pesi via `font-weight` (400/500/700). Tutto in `text-transform: lowercase`. (Nota: il concept iniziale citava Fraunces serif + JetBrains Mono — mai usati nel file finale.)

### Tono editoriale (copy)

- Lingua: italiano. Tono diretto, asciutto, leggermente provocatorio ma mai cinico.
- Frasi corte. Punteggiatura come ritmo.
- Riferimenti classici gestiti con leggerezza (Archimede, Siracusa, "eureka").
- Niente buzzword da campagna elettorale.

### Layout

- Mobile-first via `clamp()` per quasi tutte le size.
- Breakpoint principali: `800px`, `1000px`, `600px`.
- Card progetti: 3 colonne desktop → 2 → 1.
- Roster candidati: 4 colonne desktop → 2 → 1 (`.cols-2` per organo da 2).

### Accessibilità

- `cursor: none` solo su `(hover: hover)`. Su touch ripristinato.
- `prefers-reduced-motion: reduce` disattiva animazioni, parallax, flicker, meteore.
- `aria-label="eureka!"` sull'h1 spannato.
- `aria-hidden="true"` su elementi decorativi (starfield, hero-shader, bulb-stage, marquee).
- Contrasto cream su bg-blu ampiamente sopra AA.

---

## 5. Struttura del file `eureka.html`

```
<head>
  Meta + preload font self-hosted + tutto il CSS in <style> (incl. @font-face DM Sans)

<body>
  .starfield#starfield        ← canvas 2D fixed, stelle + meteore globali
  .grain                      ← overlay rumore SVG
  .cursor#cursor              ← cursor custom (gestito in JS)

  <nav>                       ← brand · progetti · eventi · candidati · storia · IG

  <section.hero #top>
    canvas.hero-shader        ← shader WebGL2 (fbm clouds + glints)
    .bulb-stage#bulb-stage    ← Three.js lampadina 3D
      canvas#bulb-canvas
      .bulb-ui                ← 4 angoli con specifiche (60W · E27, 2700K · WARM, PWR ON/OFF, A19 · TUNGSTEN)
    .hero-wordmark            ← h1 "eureka!" + tagline + CTA

  <div.marquee>               ← scrolling band

  <section.progetti #progetti>     ← 01 / 6 card numerate (spazi, cultura, sport, ascolto, trasparenza, eventi)
  <section.eventi #eventi>         ← 02 / timeline 6 eventi (ott 2025 → giu 2026)
  <section.candidati #candidati>   ← 03 / 3 organi (consiglio 8, consulta 4, garanzia 2) — 14 candidati totali
  <section.storia #storia>         ← 04 / stats (1.500 studenti, 2018, ecc.)
  <section.illuminated>            ← pull quote luminosa con glow CSS animato
  <section.cta #contatti>          ← canvas#shader-canvas + "vota eureka!" + link IG
  <footer>                         ← copyright + location

  <script type="importmap">   ← three + addons da unpkg
  <script type="module">      ← Three.js bulb (LatheGeometry, transmission, bloom)
  <script>                    ← year, cursor, IO reveal, hero shader WebGL2, starfield, CTA shader
```

**Numerazione sezioni**: progetti = 01, eventi = 02, candidati = 03, storia = 04. Mantenere coerente.

### Animazioni e tecnica visuale

- **Starfield** (`#starfield`): canvas 2D con stelle pre-renderizzate offscreen + meteore animate. 30 FPS throttle, DPR cap 1.5, pausa su `visibilitychange`.
- **Hero shader** (`#hero-shader-canvas`): fragment shader WebGL2, 6 ottave fbm + 4 ottave clouds, glints dorati. Notte stellata "soffice".
- **Lampadina 3D** (`#bulb-canvas`): Three.js `LatheGeometry` (vetro lucido con `transmission`), `RectAreaLight` interno per il filamento, `RoomEnvironment` + `PMREMGenerator`, `EffectComposer` + `UnrealBloomPass`. `transmissionResolutionScale = 0.6` per perf.
  - Idle drift + parallax al cursor + drag con inerzia.
  - **Tap = toggle on/off** (`powerOn` state). `displayHeat` lerpa con velocità asimmetriche (heat 2.2/s, cool 6.5/s).
  - Flicker noise multi-ottava (somma di sinusoidi non commensurabili) modula CSS vars `--ignition` e `--flicker` per l'halo esterno.
  - Curva di colore blackbody tungsten 1500K → 2700K durante l'accensione.
  - `IntersectionObserver` mette in pausa il composer quando l'hero è offscreen.
- **CTA shader** (`#shader-canvas`): secondo fragment shader WebGL2, glow finale.
- **Reveal**: `IntersectionObserver` aggiunge `.in` su elementi `.reveal` (fade + translate up).
- **Cursor custom**: posizionato in JS, scaling al hover su `[data-hover]`.

---

## 6. TODO — personalizzazioni

### Alta priorità
- [ ] **Numero di lista** (sezione `.cta`): "Lista N° __" — riempire al sorteggio.
- [ ] **Foto candidati**: verificare che tutte le immagini in `foto/` siano caricate (fallback `onerror="this.remove()"` mostra l'iniziale se mancante).
- [ ] **Programma reale**: i 6 punti in `.progetti` (Spazi / Cultura / Sport / Ascolto / Trasparenza / Eventi) sono una proposta. Validare con la lista.

### Media priorità
- [ ] **Eventi reali**: la timeline (ott 2025 → giu 2026) ha eventi plausibili. Aggiornare con date e contenuti veri, e con i tag `passato / in corso / in arrivo`.
- [ ] **Statistiche storia**: i numeri in `.storia` (1.500 studenti, 2018, ecc.) — verificare che siano corretti.
- [ ] **Pull quote** (sezione `.illuminated`): rivedere con la lista.

### Bassa priorità
- [x] **Open Graph + meta**: `og:title`, `og:description`, `twitter:card`, `theme-color` aggiunti. Manca solo `og:image` (serve un'immagine 1200×630 da creare).
- [x] **Favicon**: SVG inline data-URI ("!" oro su blu notte).
- [ ] **Favicon**: una favicon con la lampadina o "e!".
- [ ] **Performance audit**: Lighthouse mobile. Three.js + WebGL2 + canvas 2D pesano — controllare su device entry-level.

---

## 7. Convenzioni di codice

- **Indentazione**: 2 spazi.
- **CSS**: organizzato per sezione con commenti `/* ===== NOME ===== */`. Ordine: variabili → reset → utility (grain, cursor, starfield) → nav → sezioni in ordine di apparizione → reveal/motion → media query.
- **Naming**: classi semantiche basate sulla sezione (`.progetti .card`, `.candidati .member`, `.eventi .event`). BEM-leggero.
- **CSS variables**: SEMPRE per colori. Mai colori hardcoded — `var(--cream)`, `var(--gold)`, ecc.
- **Font sizes**: `clamp(min, fluid, max)` per tutto ciò che è responsive. Niente media query di font-size.
- **JS modulare**: il modulo Three.js (`<script type="module">`) è separato dal resto. Dentro esso, top-level `await` consentito.
- **Performance**: tutto ciò che è animato deve avere un `IntersectionObserver` o un check `prefers-reduced-motion`. DPR cappato a 1.5 per i canvas pesanti.

---

## 8. Comandi utili

```bash
# Apri il sito in locale
open eureka.html                                    # macOS
xdg-open eureka.html                                # Linux
start eureka.html                                   # Windows

# Server locale (utile perché gli ES modules richiedono protocollo http://)
python3 -m http.server 8000                         # poi http://localhost:8000/eureka.html
npx serve .                                         # se hai Node

# Deploy
# Netlify: drag & drop su https://app.netlify.com/drop
# GitHub Pages: git push, Settings → Pages → main / root
# Vercel: vercel deploy
```

> **Nota importante**: il sito **richiede protocollo http(s)://** per via dell'`importmap` di Three.js. Aprirlo con `file://` può funzionare ma alcuni browser bloccano i moduli. Sempre meglio servirlo localmente.

Niente build, niente bundler, niente `npm install`.

---

## 9. Possibili estensioni

In ordine di valore percepito:

1. **Pagina dettaglio progetti** (`progetto-spazi.html`, ecc.): per ogni card un'espansione con tempistiche, responsabili, status.
2. **Form di contatto / proposte**: textarea per studenti che mandano suggerimenti. Backend: Formspree o Netlify Forms (gratis con limiti).
3. **Newsletter** (Buttondown, MailerLite gratis): per aggiornamenti.
4. **Sezione "Ci abbiamo pensato"**: archivio di idee discusse e perché non sono state portate avanti — trasparenza vera.
5. **Versione audio della lista**: speaker note sui candidati. Solo se ne hanno voglia.

**Da non fare** (a meno di motivo forte):
- Cambiare la palette blu notte + oro. È identitaria.
- Aggiungere un CMS. Per un sito che cambia 1 volta l'anno è overkill.
- Migrare a React/Next/Astro. Il single-file HTML è perfetto per questo use case.
- Aggiungere altre librerie 3D oltre Three.js. Una è già tanto.

---

## 10. Note sul mio profilo (Giacomo)

Per Claude Code: studente di 4° anno del liceo scientifico (matematica, fisica, latino, filosofia, inglese...). Lavoro in italiano, sto imparando Python (CS50P, da zero). Non aspettarti che capisca al volo build tools complessi, config webpack, ecc. — preferisco soluzioni dirette, single-file quando possibile, e spiegazioni step-by-step quando si introduce qualcosa di nuovo. Se mi consigli di installare qualcosa, dimmi anche perché vale la complessità aggiuntiva.

Sono anche candidato in lista (`giacomo warm`, classe 4E, n° 02 al consiglio d'istituto).

---

## 11. Stato attuale

- ✅ Design completo (1 file HTML, ~2.900 righe)
- ✅ Tutte le sezioni strutturate (progetti, eventi, candidati, storia, illuminated, cta)
- ✅ Responsive
- ✅ Lampadina 3D Three.js con toggle on/off, flicker, drag
- ✅ Hero shader WebGL2 (clouds + glints)
- ✅ Starfield globale con meteore (perf-optimized)
- ✅ Cursor custom + reveal animations
- ✅ Candidati reali (14 nomi su 3 organi) + foto in `foto/`
- ⏳ Numero di lista (al sorteggio)
- ⏳ Validazione contenuti (progetti, eventi, statistiche) con la lista
- ✅ Open Graph / favicon / meta social (manca solo og:image)
- ✅ Pacchetto animazioni 2026: neon ignition hero, scramble titoli, tilt 3D, magnetic buttons, filo di corrente, timeline luminosa, count-up, marquee velocity-aware, scintille click
- ✅ Moduli wow (seconda ondata): shader Van Gogh hero, lampadina a pendolo, word illumination, costellazione candidati, scia di luce + shockwave, lettere magnetiche (interruttore lights-out RIMOSSO giugno 2026)
- ⏳ Deploy

**Prossimo step naturale**: validazione contenuti con la lista, meta OG, deploy su Netlify/Vercel.
