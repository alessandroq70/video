"""Flask web application that merges 2+ video files into one.

Run with:  python app.py
Then open http://127.0.0.1:5000 in your browser.

Uploaded videos are streamed to temporary files on disk (never held whole in
memory), so large videos are handled gracefully. The merge runs in a background
thread and reports progress, so the browser can show a real progress bar and
then download the finished file.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
import uuid

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

# Finished/failed jobs older than this are swept away (with their temp files).
JOB_TTL_SECONDS = 60 * 60  # 1 hour

# In-memory registry of merge jobs, keyed by job id. Guarded by ``_jobs_lock``.
# Each job: {status, progress, tmpdir, output_path, file_size, error, created}.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job(tmpdir: str) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "tmpdir": tmpdir,
            "output_path": None,
            "file_size": 0,
            "error": None,
            "created": time.time(),
        }
    return job_id


def _update_job(job_id: str, **changes) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.update(changes)


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None


def _drop_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.pop(job_id, None)


def _sweep_stale_jobs() -> None:
    """Remove abandoned finished/failed jobs and their temp directories."""
    cutoff = time.time() - JOB_TTL_SECONDS
    stale = []
    with _jobs_lock:
        for job_id, job in list(_jobs.items()):
            if job["status"] != "processing" and job["created"] < cutoff:
                stale.append(_jobs.pop(job_id))
    for job in stale:
        shutil.rmtree(job["tmpdir"], ignore_errors=True)


def _run_merge(job_id: str, input_paths: list[str], output_path: str) -> None:
    """Background worker: merge the videos and record the outcome on the job."""

    def on_progress(fraction: float) -> None:
        _update_job(job_id, progress=fraction)

    try:
        merge_videos(input_paths, output_path, progress_callback=on_progress)
    except MergeError as exc:
        _update_job(job_id, status="error", error=str(exc))
        return
    except Exception:  # noqa: BLE001 - surface a friendly message, log the rest
        app.logger.exception("Errore imprevisto durante l'unione dei video")
        _update_job(
            job_id, status="error",
            error="Errore imprevisto durante l'unione dei video.",
        )
        return

    _update_job(
        job_id,
        status="done",
        progress=1.0,
        output_path=output_path,
        file_size=os.path.getsize(output_path),
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/merge", methods=["POST"])
def merge():
    """Accept the uploaded videos and start a background merge job.

    Returns a job id the client can poll via ``/progress/<job_id>`` and, once
    done, fetch the result from ``/download/<job_id>``.
    """
    _sweep_stale_jobs()

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
    except Exception:  # noqa: BLE001
        shutil.rmtree(tmpdir, ignore_errors=True)
        app.logger.exception("Errore durante il salvataggio dei file caricati")
        return jsonify(error="Errore durante il caricamento dei file."), 500

    output_path = os.path.join(tmpdir, "video-unito.mp4")
    job_id = _new_job(tmpdir)

    worker = threading.Thread(
        target=_run_merge, args=(job_id, input_paths, output_path), daemon=True
    )
    worker.start()

    return jsonify(job_id=job_id), 202


@app.route("/progress/<job_id>")
def progress(job_id: str):
    """Report the status and progress (0..1) of a merge job."""
    job = _get_job(job_id)
    if job is None:
        return jsonify(error="Lavoro non trovato o scaduto."), 404

    payload = {"status": job["status"], "progress": round(job["progress"], 4)}
    if job["status"] == "error":
        payload["error"] = job["error"]
    return jsonify(payload)


@app.route("/download/<job_id>")
def download(job_id: str):
    """Stream a finished job's output, then clean up its temp files."""
    job = _get_job(job_id)
    if job is None:
        return jsonify(error="Lavoro non trovato o scaduto."), 404
    if job["status"] == "processing":
        return jsonify(error="L'unione è ancora in corso."), 409
    if job["status"] == "error":
        return jsonify(error=job["error"] or "Unione fallita."), 400

    # Take ownership of the job so its temp dir is cleaned up exactly once.
    job = _drop_job(job_id)
    if job is None:
        return jsonify(error="Lavoro non trovato o scaduto."), 404

    output_path = job["output_path"]
    tmpdir = job["tmpdir"]

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
    response.headers["Content-Length"] = str(job["file_size"])
    response.headers["Content-Disposition"] = 'attachment; filename="video-unito.mp4"'
    return response


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    return jsonify(error="I file caricati superano il limite di 4 GB."), 413


if __name__ == "__main__":
    # threaded=True so the browser can download while the server stays responsive.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
