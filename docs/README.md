# 🎬 Video Studio — l'app (browser)

L'app gira **interamente nel browser** grazie a
[ffmpeg.wasm](https://ffmpegwasm.netlify.app/): nessun server, nessuna
installazione. I video **non vengono caricati online** — restano sul tuo
dispositivo.

È pensata per essere pubblicata gratuitamente con **GitHub Pages**.

## Come pubblicarla su GitHub Pages

1. Assicurati che il repository sia **pubblico**
   (Settings → in fondo, *Change repository visibility* → *Public*).
   GitHub Pages gratuito funziona solo sui repository pubblici.
2. Vai su **Settings → Pages**.
3. In *Source* scegli **Deploy from a branch**.
4. Seleziona il branch `main` e la cartella **`/docs`**, poi premi **Save**.
5. Dopo 1–2 minuti l'app sarà online a un indirizzo tipo:
   `https://alessandroq70.github.io/video/`

## Come si usa

1. Apri il link, clicca sull'area tratteggiata (o trascina i video).
2. Riordina i file trascinandoli (o con le frecce ▲ ▼); taglia un video con ✂️
   indicando minuto e secondo del taglio; salva una singola parte con 💾.
3. Clicca **"Unisci"**, guarda l'anteprima, scegli il nome del file e premi
   **"Salva"**. (Al primo utilizzo scarica ~30 MB del motore video: è normale.)

## Limiti (onesti)

- Adatta a **video piccoli / brevi**: l'elaborazione avviene nella memoria del
  browser, quindi file molto grandi (indicativamente oltre ~700 MB in totale)
  possono non funzionare.
- La riconversione (formati diversi, tagli, copertina) richiede più tempo dei
  semplici video uniformi uniti senza riconversione.

## Come funziona (nota tecnica)

- Se i video hanno stesso codec/risoluzione (e nessun taglio) → unione veloce
  senza riconversione (`concat` con stream copy).
- Altrimenti → riconversione in MP4 H.264/AAC, con adattamento a un formato
  comune e traccia audio silenziosa aggiunta dove manca; i tagli usano
  `-ss`/`-t` sull'input, precisi al fotogramma col re-encode.
- Il motore FFmpeg (`@ffmpeg/core`, build ESM) e il relativo worker vengono
  caricati da CDN come blob di pari-origine, così funziona anche pubblicato su
  un dominio diverso da quello della CDN.
