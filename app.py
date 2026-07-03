"""Flask web application that merges 2+ video files into one.

Run with:  python app.py
Then open http://127.0.0.1:5000 in your browser.

Uploaded videos are streamed to temporary files on disk (never held whole in
memory), so large videos are handled gracefully.
"""
from __future__ import annotations

import os
import shutil
import tempfile

from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from video_merger import MergeError, merge_videos

app = Flask(__name__)

# Allow large uploads (4 GB total). Videos are big; adjust if you need more.
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".mpeg", ".mpg", ".3gp",
}

CHUNK_SIZE = 1024 * 1024  # 1 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/merge", methods=["POST"])
def merge():
    """Merge the uploaded videos, in the order received, into one MP4."""
    uploads = request.files.getlist("files")

    if len(uploads) < 2:
        return jsonify(error="Seleziona almeno 2 file video."), 400

    for upload in uploads:
        ext = os.path.splitext(upload.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify(
                error=f"'{upload.filename}' non sembra un file video supportato."
            ), 400

    tmpdir = tempfile.mkdtemp(prefix="video-merge-")
    input_paths = []
    try:
        for index, upload in enumerate(uploads):
            safe = secure_filename(upload.filename) or f"input_{index}"
            dest = os.path.join(tmpdir, f"{index:03d}_{safe}")
            upload.save(dest)  # streams to disk, no full in-memory copy
            input_paths.append(dest)

        output_path = os.path.join(tmpdir, "video-unito.mp4")
        merge_videos(input_paths, output_path)
    except MergeError as exc:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return jsonify(error=str(exc)), 400
    except Exception:  # noqa: BLE001 - surface a friendly message, log the rest
        shutil.rmtree(tmpdir, ignore_errors=True)
        app.logger.exception("Errore imprevisto durante l'unione dei video")
        return jsonify(error="Errore imprevisto durante l'unione dei video."), 500

    file_size = os.path.getsize(output_path)

    def stream_and_cleanup():
        try:
            with open(output_path, "rb") as handle:
                while True:
                    chunk = handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        finally:
            # File handle is closed here, so cleanup works on Windows too.
            shutil.rmtree(tmpdir, ignore_errors=True)

    response = Response(stream_and_cleanup(), mimetype="video/mp4")
    response.headers["Content-Length"] = str(file_size)
    response.headers["Content-Disposition"] = 'attachment; filename="video-unito.mp4"'
    return response


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    return jsonify(error="I file caricati superano il limite di 4 GB."), 413


if __name__ == "__main__":
    # threaded=True so the browser can download while the server stays responsive.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
