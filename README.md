# 🎬 Unisci Video

App web per **unire due o più file video** in un unico MP4, **direttamente nel
browser**. Nessuna installazione, nessun server: i video vengono elaborati sul
tuo dispositivo grazie a **[ffmpeg.wasm](https://ffmpegwasm.netlify.app/)**.

> 🔒 **Privacy:** i video **non vengono mai caricati online** — restano sul tuo
> dispositivo e l'elaborazione avviene interamente nel browser.

## Caratteristiche

- Selezione di **2 o più video** (clic o trascinamento).
- **Miniature e durata** di ogni clip, con totale complessivo dell'elenco.
- **Riordino** dei file prima dell'unione: **trascinali** nella posizione
  desiderata oppure usa le frecce su/giù; rimozione singola o svuota tutto.
- **Copertina** opzionale: un'immagine mostrata per N secondi all'inizio del
  video finale.
- **Unione intelligente:**
  - se i video hanno **stesso formato/risoluzione** vengono uniti senza
    riconversione (veloce e senza perdita di qualità);
  - se hanno **formati o risoluzioni diversi**, vengono riconvertiti in un MP4
    standard (H.264/AAC), adattando le dimensioni a un formato comune e
    aggiungendo una traccia audio silenziosa dove manca.
- **Barra di avanzamento** con percentuale durante l'elaborazione.
- **Anteprima del risultato** direttamente nella pagina: guarda il video unito
  prima di decidere se salvarlo o scartarlo.
- **Nome del file personalizzabile** al salvataggio, con dialogo
  **"Salva con nome"** su Chrome/Edge (sugli altri browser il file viene
  scaricato nella cartella Download).
- **Tema chiaro/scuro** automatico in base alle preferenze di sistema.

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
2. Riordina i file trascinandoli (o con le frecce ▲ ▼); aggiungi una copertina
   se vuoi.
3. Clicca **"Unisci"**, guarda l'anteprima del risultato, scegli il nome del
   file e premi **"Salva"**.

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
