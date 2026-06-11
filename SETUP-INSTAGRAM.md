# Feed Instagram — setup (una volta sola)

Il sito mostra **tutti** i post di @eureka.archimede e si aggiorna da solo ogni 3 ore.
Funziona così: un robot gratuito di GitHub (una "Action") scarica i post dall'API
ufficiale di Meta, salva immagini + dati dentro il sito, e li committa. I visitatori
leggono solo un file statico — nessun limite di traffico, nessun servizio a pagamento.

Devi fare questo setup **una volta**. Dopo, zero manutenzione: il token si rinnova
da solo, i post si aggiornano da soli.

Tempo: ~45 minuti. Fai con calma, è la parte più noiosa. Una volta finita, è per sempre.

---

## Cosa ti serve prima di iniziare

1. L'account Instagram **@eureka.archimede** deve essere **Professionale**
   (Creator o Business). Si fa dall'app: Impostazioni → Account → *Passa a un account
   professionale*. Gratis, reversibile, non cambia niente di visibile.
2. Un account **Facebook** che amministra una **Pagina Facebook** collegata a quell'IG.
   Se non c'è, creane una pagina vuota e collegala (Instagram → Impostazioni →
   *Account collegati* → Facebook). Meta lo richiede anche se non usi Facebook.
3. Un account **GitHub** (gratis, github.com) dove caricherai il sito.

---

## Parte A — ottieni il token Instagram

Serve un "token": una password lunga che permette al robot di leggere i post.
Lo generi dal sito sviluppatori di Meta.

1. Vai su **developers.facebook.com** → in alto *Accedi*, poi *I miei prodotti* /
   *Crea apertura app*.
2. **Crea un'app**: tipo **Business**. Dai un nome qualsiasi (es. "eureka feed").
3. Nella dashboard dell'app, aggiungi il prodotto **Instagram** (riquadro
   "Instagram" → *Configura*). Cerca la sezione **API con accesso Instagram**.
4. Lì trovi un pulsante per **generare un token di accesso** per il tuo account
   @eureka.archimede. Autorizza quando l'app chiede i permessi (servono almeno
   `instagram_basic` / `instagram_business_basic`).
5. Ti viene dato un **token breve** (dura 1 ora). Va trasformato in **token lungo**
   (dura 60 giorni). Nella stessa pagina di solito c'è un pulsante *"Genera token a
   lunga durata"*. Copialo: è una stringa lunghissima tipo `IGQVJ...` o `EAAG...`.

   > Questa è la parte fragile dell'interfaccia Meta: cambia spesso nome ai pulsanti.
   > Se ti perdi, cerca su YouTube "Instagram Graph API long lived token 2026" —
   > il concetto resta: app Business → prodotto Instagram → genera token lungo.

6. **Tieni questo token da parte** (incollalo in una nota temporanea). Lo userai
   nella Parte C. Non condividerlo con nessuno: è come una password.

Il robot rinnova questo token automaticamente a ogni esecuzione, quindi **non
scadrà mai** finché il sito gira almeno una volta ogni 60 giorni.

---

## Parte B — genera la chiave di cifratura

Il token viene salvato dentro il repository, ma **cifrato** (illeggibile senza chiave).
Genera la chiave: apri il Terminale (su Mac: cmd+spazio → "Terminale") e incolla:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Esce una stringa di 64 caratteri (lettere a–f e numeri). **Copiala e tienila da
parte** insieme al token. La userai nella Parte C come `ENC_KEY`.

---

## Parte C — carica il sito su GitHub e inserisci i segreti

1. Crea un repository su GitHub (es. `eureka-sito`). Carica **tutta la cartella**
   del sito (trascina i file nella pagina "uploading files", oppure usa GitHub
   Desktop se preferisci il drag-and-drop).
2. Nel repository: **Settings** (in alto) → menu a sinistra **Secrets and variables**
   → **Actions** → pulsante verde **New repository secret**. Crea **due** segreti:

   | Name (esatto) | Secret (valore) |
   |---------------|-----------------|
   | `IG_TOKEN`    | il token lungo della Parte A |
   | `ENC_KEY`     | la chiave da 64 caratteri della Parte B |

   Scrivi i nomi **esattamente** così, maiuscoli.

3. Vai sul tab **Actions** del repository. Se chiede di abilitare i workflow,
   conferma. Apri **"aggiorna feed instagram"** nella lista a sinistra →
   pulsante **Run workflow** → **Run workflow**.
4. Aspetta ~1 minuto. Se diventa **verde** ✅: fatto. Il robot ha scaricato i post,
   creato la cartella `assets/ig/` con le immagini e il file `feed.json`, e li ha
   committati. Da ora gira **da solo ogni 3 ore**.

   Se diventa **rosso** ❌: clicca sul run, leggi l'ultima riga rossa. Quasi sempre è
   il token (Parte A) sbagliato o scaduto — rigeneralo e aggiorna il secret `IG_TOKEN`.

---

## Parte D — pubblica il sito

Due strade, entrambe gratis:

- **GitHub Pages**: nel repo → Settings → Pages → Source: *Deploy from a branch* →
  branch `main`, cartella `/root` → Save. Dopo 1 minuto il sito è online su
  `https://<tuo-utente>.github.io/eureka-sito/`. **Vantaggio**: tutto su GitHub,
  le immagini del feed si aggiornano insieme al sito.
- **Netlify**: collega il repo GitHub (non il drag-and-drop stavolta) così Netlify
  ripubblica da solo a ogni aggiornamento del robot.

> Importante: il file da aprire è `index.html` (già pronto, copia di `eureka.html`).

---

## Domande

**Devo fare manutenzione?** No. Il token si rinnova da solo. I post si scaricano da
soli. Pubblichi su Instagram → entro 3 ore appaiono sul sito.

**E se non faccio in tempo a fare il setup Meta?** Il sito intanto funziona lo stesso:
mostra gli ultimi 6 post tramite il servizio Behold (fallback automatico già attivo).
Il setup Meta serve solo per averli **tutti**.

**Quanto costa?** Zero. GitHub Actions è gratis per i repository pubblici. L'API Meta
è gratis. Nessun servizio a pagamento.

**Il token è al sicuro?** Sì: nel repo è cifrato (AES-256) e i due segreti stanno nei
"Secrets" di GitHub, che non sono mai visibili né nel codice né nei log.

**Voglio cambiare frequenza** (es. ogni ora): apri `.github/workflows/ig-feed.yml`,
riga `cron: '17 */3 * * *'` → cambia `*/3` in `*/1`. Non scendere sotto l'ora: inutile.
