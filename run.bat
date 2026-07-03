@echo off
REM ---------------------------------------------------------------
REM  Avvio rapido dell'app "Unisci Video" su Windows.
REM  Crea l'ambiente virtuale e installa le dipendenze al primo avvio
REM  (incluso FFmpeg), poi apre l'app nel browser.
REM ---------------------------------------------------------------
setlocal

cd /d "%~dp0"

if not exist ".venv" (
    echo Creazione ambiente virtuale...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installazione dipendenze (incluso FFmpeg, puo' richiedere un minuto)...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo App in esecuzione su http://127.0.0.1:5000
echo Premi CTRL+C in questa finestra per chiudere.
echo.

start "" http://127.0.0.1:5000
python app.py

endlocal
