# 🎬 Unisci Video

App web per **unire due o più file video** in un unico MP4, **direttamente nel
browser**. Nessuna installazione, nessun server: i video vengono elaborati sul
tuo dispositivo grazie a **[ffmpeg.wasm](https://ffmpegwasm.netlify.app/)**.

> 🔒 **Privacy:** i video **non vengono mai caricati online** — restano sul tuo
> dispositivo e l'elaborazione avviene interamente nel browser.

## Caratteristiche

- Selezione di **2 o più video** (clic o trascinamento).
- **Riordino** dei file prima dell'unione (frecce su/giù) e rimozione singola.
- **Copertina** opzionale: un'immagine mostrata per N secondi all'inizio del
  video finale.
- **Unione intelligente:**
  - se i video hanno **stesso formato/risoluzione** vengono uniti senza
    riconversione (veloce e senza perdita di qualità);
  - se hanno **formati o risoluzioni diversi**, vengono riconvertiti in un MP4
    standard (H.264/AAC), adattando le dimensioni a un formato comune e
    aggiungendo una traccia audio silenziosa dove manca.
- **Barra di avanzamento** durante l'elaborazione.
- Salvataggio del risultato con dialogo **"Salva con nome"** su Chrome/Edge
  (sugli altri browser il file viene scaricato nella cartella Download).

## Come si usa

L'app è un **unico file HTML** (`docs/index.html`): non serve installare nulla.

### Opzione 1 — Apri il file in locale
Fai doppio clic su `docs/index.html` (o aprilo dal browser). Serve una
connessione a internet **solo al primo utilizzo**, per scaricare il motore
ffmpeg.wasm.

### Opzione 2 — Pubblicala online gratis (GitHub Pages)
1. Vai in **Settings → Pages** del repository.
2. In *Build and deployment*, scegli **Deploy from a branch**.
3. Seleziona il branch `main` e la cartella **`/docs`**, poi salva.
4. Dopo qualche istante l'app sarà raggiungibile all'URL indicato da GitHub.

Poi:
1. Clicca sull'area tratteggiata (o trascina i video) per aggiungere i file.
2. Riordina i file con le frecce ▲ ▼ se necessario; aggiungi una copertina se
   vuoi.
3. Clicca **"Unisci e salva"** e scegli dove salvare il video unito.

## Note e limiti

- L'elaborazione avviene **nel browser**: è adatta a video **piccoli/brevi**.
  File molto grandi o lunghi possono essere lenti o esaurire la memoria della
  scheda del browser.
- Formati supportati in ingresso: i più comuni (MP4, MOV, MKV, WEBM, AVI, …).
  L'uscita è sempre MP4.
- Consigliati i browser basati su Chromium (Chrome, Edge) per il dialogo di
  salvataggio "Salva con nome".

## Struttura del progetto

```
.
├── docs/
│   └── index.html   # L'intera app (HTML + CSS + JS) in un unico file
└── README.md
```
