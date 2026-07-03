# 🎬 Unisci Video

App web semplice per **unire due o più file video** in un unico documento MP4.
Selezioni i video, li ordini come vuoi, e al salvataggio l'app ti **chiede dove
salvare** il risultato.

Usa **FFmpeg** dietro le quinte, incluso automaticamente tramite il pacchetto
`imageio-ffmpeg`: **non devi installare FFmpeg a mano**.

## Caratteristiche

- Selezione di **2 o più video** (clic o trascinamento).
- **Riordino** dei file prima dell'unione (frecce su/giù).
- Rimozione dei singoli file e pulsante per svuotare l'elenco.
- **Unione intelligente:**
  - se i video hanno **stesso formato/risoluzione** vengono uniti senza
    riconversione (veloce e senza perdita di qualità — ideale per unire spezzoni
    dello stesso filmato);
  - se hanno **formati o risoluzioni diversi**, vengono riconvertiti in un MP4
    standard (H.264/AAC), adattando le dimensioni a un formato comune e
    aggiungendo una traccia audio silenziosa dove manca.
- **Barra di avanzamento** in tempo reale durante la riconversione, così sai
  sempre a che punto è l'unione (l'elaborazione avviene in background).
- Al salvataggio apre un vero dialogo **"Salva con nome"** su Chrome ed Edge
  (i browser predefiniti su Windows). Sugli altri browser il file viene
  scaricato nella cartella Download.

## Requisiti

- [Python 3.9+](https://www.python.org/downloads/) installato
  (durante l'installazione su Windows spunta *"Add Python to PATH"*).

## Avvio rapido (Windows)

1. Scarica/clona questa cartella.
2. Fai **doppio clic su `run.bat`**.
   - Al primo avvio crea l'ambiente e scarica le dipendenze, **incluso FFmpeg**
     (ci vuole un minuto).
   - Si apre automaticamente il browser su <http://127.0.0.1:5000>.
3. Per chiudere l'app, premi `CTRL+C` nella finestra del terminale.

## Avvio manuale (qualsiasi sistema)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Poi apri <http://127.0.0.1:5000> nel browser.

## Come si usa

1. Clicca sull'area tratteggiata (o trascina i video) per aggiungere i file.
2. Riordina i file con le frecce ▲ ▼ se necessario.
3. Clicca **"Unisci e salva"** e scegli dove salvare il video unito.

> ⏳ Se i video hanno formati diversi serve una riconversione: per file lunghi o
> in alta risoluzione può richiedere qualche minuto. Non chiudere la pagina nel
> frattempo.

## Struttura del progetto

```
.
├── app.py              # Server web Flask (route / e /merge)
├── video_merger.py     # Logica di unione video con FFmpeg (testabile)
├── templates/
│   └── index.html      # Interfaccia
├── static/
│   ├── app.js          # Logica lato browser (selezione, ordine, salvataggio)
│   └── style.css       # Stile
├── tests/
│   └── test_merge.py   # Test della logica di unione
├── requirements.txt    # Dipendenze Python
└── run.bat             # Avvio rapido su Windows
```

## Test

```bash
pip install pytest
pytest
```

## Note

- I video vengono elaborati **in locale**, sul tuo computer: nulla viene
  inviato a internet.
- Le informazioni sui video vengono lette con **`ffprobe`** se è disponibile sul
  sistema (dati più affidabili); in caso contrario si usa un'analisi di riserva
  basata su `ffmpeg`, quindi **non serve installare nulla in più**.
- Limite di caricamento predefinito: 4 GB totali (modificabile in `app.py`).
- Formati supportati in ingresso: MP4, MOV, M4V, AVI, MKV, WEBM, WMV, FLV,
  MPEG, 3GP. L'uscita è sempre MP4.
