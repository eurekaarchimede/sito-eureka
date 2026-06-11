# AGENTS.md — eureka!

Documento di contesto per Codex. Stato del progetto e decisioni di design.

---

## 1. Il progetto

Sito web one-page per **eureka!**, lista di rappresentanza d'istituto del **Liceo Scientifico Archimede** di Messina (~1.500 studenti, fondata nel 2018, Instagram: [@eureka.archimede](https://instagram.com/eureka.archimede)).

**Obiettivo**: presenza online della lista durante la campagna elettorale studentesca per l'edizione **2025–2026**. Comunica progetti, eventi, candidati, storia. Indirizza verso Instagram.

**Audience**: ~1.500 studenti del liceo, età 14–19. Fruizione prevalentemente da mobile.

**Aggancio concettuale**: *Eureka* è l'esclamazione di Archimede — il nome della lista e il nome della scuola formano un loop. Sviluppato visivamente con il tema della **lampadina che si accende** (idea → lampadina → scoperta → eureka).

---

## 2. Stack tecnico

- **Single-file HTML**: `eureka.html` (~2.900 righe). Nessun build step.
- **CSS**: vanilla, dentro `<style>`. Usa CSS variables, `clamp()`, grid, `font-variation-settings`.
- **JS**: vanilla + Three.js. Dentro `<script>` (modulo + classico).
- **Three.js**: caricato via `importmap` da `unpkg.com/three@0.170.0`. Solo per la lampadina 3D nell'hero.
- **WebGL2**: fragment shader scritto a mano per lo sfondo dell'hero e per il blocco CTA. Niente librerie.
- **Canvas 2D**: starfield globale con meteore (offscreen pre-render + 30 FPS throttle).
- **Font**: Google Fonts (`Fraunces` variable + `JetBrains Mono`).
- **Asset**: cartella `foto/` con i ritratti dei candidati (`christian-bucalo.jpg`, `giacomo-warm.jpg`, ecc.).

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

- **`Fraunces`** (variable serif) — display + body. Asse `SOFT` (0=wedge, 100=soft) per dare carattere unico. `font-variation-settings: "SOFT" 100, "opsz" 144` sui display, `"opsz" 14` sul body.
- **`JetBrains Mono`** — solo per editorial labels ("01 / progetti"), tag piccoli, footer, microcopy. Mai per body o display.

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
  Meta + Google Fonts + tutto il CSS in <style>

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
- [ ] **Open Graph + meta**: aggiungere `og:image`, `og:title`, `og:description`, `twitter:card` per condivisione su WhatsApp/Instagram.
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

Per Codex: studente di 4° anno del liceo scientifico (matematica, fisica, latino, filosofia, inglese...). Lavoro in italiano, sto imparando Python (CS50P, da zero). Non aspettarti che capisca al volo build tools complessi, config webpack, ecc. — preferisco soluzioni dirette, single-file quando possibile, e spiegazioni step-by-step quando si introduce qualcosa di nuovo. Se mi consigli di installare qualcosa, dimmi anche perché vale la complessità aggiuntiva.

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
- ⏳ Open Graph / favicon / meta social
- ⏳ Deploy

**Prossimo step naturale**: validazione contenuti con la lista, meta OG, deploy su Netlify/Vercel.
