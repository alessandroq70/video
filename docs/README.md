# 🎬 Unisci Video — versione online (browser)

Versione dell'app che gira **interamente nel browser** grazie a
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
4. Seleziona il branch `claude/pdf-merger-app-4lnnhs` e la cartella **`/docs`**,
   poi premi **Save**.
5. Dopo 1–2 minuti l'app sarà online a un indirizzo tipo:
   `https://alessandroq70.github.io/PDF/`

## Come si usa

1. Apri il link, clicca sull'area tratteggiata (o trascina i video).
2. Riordina i file con le frecce ▲ ▼ se necessario.
3. Clicca **"Unisci e salva"** e scegli dove salvare il video unito.
   (Al primo utilizzo scarica ~30 MB del motore video: è normale.)

## Limiti (onesti)

- Adatta a **video piccoli / brevi**: l'elaborazione avviene nella memoria del
  browser, quindi file molto grandi (indicativamente oltre ~700 MB in totale)
  possono non funzionare. Per video grandi usa la versione desktop
  (cartella `../video-merger`).
- È **più lenta** della versione desktop, soprattutto quando i video hanno
  formati diversi e serve una riconversione.

## Come funziona (nota tecnica)

- Se i video hanno stesso codec/risoluzione → unione veloce senza riconversione
  (`concat` con stream copy).
- Altrimenti → riconversione in MP4 H.264/AAC, con adattamento a un formato
  comune e traccia audio silenziosa aggiunta dove manca.
- Il motore FFmpeg (`@ffmpeg/core`, build ESM) e il relativo worker vengono
  caricati da CDN come blob di pari-origine, così funziona anche pubblicato su
  un dominio diverso da quello della CDN.
