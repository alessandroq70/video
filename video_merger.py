"""Core logic for merging video files using FFmpeg.

FFmpeg is provided by the ``imageio-ffmpeg`` package (a bundled static build),
so no separate FFmpeg installation is required.

Stream information is read with ``ffprobe`` when it is available on the system
(it returns clean, structured JSON), falling back to parsing ``ffmpeg -i``
output otherwise — so the "no manual FFmpeg install" promise still holds even
though ``imageio-ffmpeg`` bundles only ``ffmpeg`` (not ``ffprobe``).

Two strategies are used:

* **Fast path (lossless):** when the inputs already share the same codec,
  resolution and frame rate, they are concatenated with stream copy — instant
  and no quality loss. Ideal for joining parts of the same recording.
* **Re-encode path:** otherwise the inputs are normalised (scaled and padded
  to a common canvas, given a uniform frame rate and a guaranteed audio track)
  and re-encoded to a standard H.264/AAC MP4. Handles clips of different
  formats, resolutions, or with/without audio. Reports progress via an
  optional callback.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ``imageio-ffmpeg`` ships ffmpeg but not ffprobe; use a system ffprobe if one
# is on PATH, otherwise ``None`` and we fall back to parsing ``ffmpeg -i``.
FFPROBE = shutil.which("ffprobe")

# Hide ffmpeg console windows on Windows when launched from a GUI/no-console.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# Progress is reported as a float in [0.0, 1.0].
ProgressCallback = Callable[[float], None]


class MergeError(Exception):
    """Raised when the inputs cannot be merged into a valid video."""


@dataclass
class VideoInfo:
    path: str
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    vcodec: str


def _run(cmd: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        creationflags=_NO_WINDOW,
    )


def _probe_with_ffprobe(path: str) -> Optional[VideoInfo]:
    """Read stream info via ffprobe's structured JSON. ``None`` if unusable."""
    if not FFPROBE:
        return None

    result = _run([
        FFPROBE, "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate:format=duration",
        "-of", "json", path,
    ])
    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video:
        raise MergeError(
            f"'{os.path.basename(path)}' non contiene una traccia video valida."
        )

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if width <= 0 or height <= 0:
        raise MergeError(
            f"Impossibile leggere la risoluzione di '{os.path.basename(path)}'."
        )

    # Frame rate comes as a "num/den" fraction; prefer avg, fall back to r.
    fps = _parse_fraction(video.get("avg_frame_rate")) or \
        _parse_fraction(video.get("r_frame_rate")) or 30.0

    vcodec = video.get("codec_name") or "unknown"
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    try:
        duration = float(data.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    return VideoInfo(path, width, height, fps, duration, has_audio, vcodec)


def _parse_fraction(value: Optional[str]) -> float:
    """Turn an ffprobe "num/den" frame-rate string into a float (0.0 if bad)."""
    if not value or "/" not in value:
        return 0.0
    num, den = value.split("/", 1)
    try:
        num_f, den_f = float(num), float(den)
    except ValueError:
        return 0.0
    return num_f / den_f if den_f else 0.0


def _probe_with_ffmpeg(path: str) -> VideoInfo:
    """Fallback probe: parse basic stream info from ``ffmpeg -i`` output."""
    result = _run([FFMPEG, "-hide_banner", "-i", path])
    text = result.stderr  # ffmpeg prints stream info to stderr

    video_lines = [ln for ln in text.splitlines() if "Video:" in ln]
    if not video_lines:
        raise MergeError(f"'{os.path.basename(path)}' non contiene una traccia video valida.")
    vline = video_lines[0]

    size = re.search(r"(\d{2,5})x(\d{2,5})", vline)
    if not size:
        raise MergeError(f"Impossibile leggere la risoluzione di '{os.path.basename(path)}'.")
    width, height = int(size.group(1)), int(size.group(2))

    fps_match = re.search(r"([\d.]+)\s*fps", vline)
    fps = float(fps_match.group(1)) if fps_match else 30.0

    codec_match = re.search(r"Video:\s*([a-zA-Z0-9_]+)", vline)
    vcodec = codec_match.group(1) if codec_match else "unknown"

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", text)
    if dur_match:
        h, m, s = dur_match.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)
    else:
        duration = 0.0

    has_audio = "Audio:" in text

    return VideoInfo(path, width, height, fps, duration, has_audio, vcodec)


def _probe(path: str) -> VideoInfo:
    """Read basic stream info, preferring ffprobe and falling back to ffmpeg."""
    info = _probe_with_ffprobe(path)
    if info is not None:
        return info
    return _probe_with_ffmpeg(path)


def _even(n: int) -> int:
    """H.264 requires even dimensions."""
    return n if n % 2 == 0 else n + 1


def _try_fast_concat(infos: List[VideoInfo], output_path: str) -> bool:
    """Attempt a lossless stream-copy concat. Returns True on success."""
    first = infos[0]
    uniform = all(
        i.width == first.width
        and i.height == first.height
        and i.vcodec == first.vcodec
        and i.has_audio == first.has_audio
        and abs(i.fps - first.fps) < 0.01
        for i in infos
    )
    if not uniform:
        return False

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as listing:
        for info in infos:
            safe = info.path.replace("'", "'\\''")
            listing.write(f"file '{safe}'\n")
        list_path = listing.name

    try:
        result = _run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-c", "copy", "-movflags", "+faststart", output_path]
        )
        return result.returncode == 0 and os.path.getsize(output_path) > 0
    finally:
        os.unlink(list_path)


def _run_reencode(cmd: List[str], total_duration: float,
                  progress_callback: Optional[ProgressCallback]) -> subprocess.CompletedProcess:
    """Run an ffmpeg re-encode, forwarding progress to ``progress_callback``.

    Uses ``-progress pipe:1`` (stable key=value output) to track ``out_time``
    against the known total duration. stderr is still captured so a failure can
    surface a useful message.
    """
    if not progress_callback or total_duration <= 0:
        # Nothing to report against; run plainly.
        return _run(cmd)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=_NO_WINDOW,
    )

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            raw = line.split("=", 1)[1]
            try:
                # Both keys are microseconds in ffmpeg's -progress output.
                seconds = int(raw) / 1_000_000
            except ValueError:
                continue
            fraction = max(0.0, min(seconds / total_duration, 0.999))
            progress_callback(fraction)
        elif line == "progress=end":
            progress_callback(1.0)

    stderr = proc.stderr.read() if proc.stderr else ""
    returncode = proc.wait()
    return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)


def _reencode_concat(infos: List[VideoInfo], output_path: str,
                     progress_callback: Optional[ProgressCallback] = None) -> None:
    """Normalise every input to a common canvas and re-encode into one MP4."""
    canvas_w = _even(max(i.width for i in infos))
    canvas_h = _even(max(i.height for i in infos))
    target_fps = round(max(i.fps for i in infos)) or 30
    total_duration = sum(max(i.duration, 0.0) for i in infos)

    cmd: List[str] = [FFMPEG, "-y"]
    for info in infos:
        cmd += ["-i", info.path]

    # Add a finite silent-audio input for every clip that has no audio, so the
    # concat filter always sees one audio stream per segment.
    silent_input_index = {}
    next_index = len(infos)
    for idx, info in enumerate(infos):
        if not info.has_audio:
            dur = max(info.duration, 0.1)
            cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100"]
            silent_input_index[idx] = next_index
            next_index += 1

    filters = []
    concat_pads = []
    for idx, info in enumerate(infos):
        filters.append(
            f"[{idx}:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease,"
            f"pad={canvas_w}:{canvas_h}:-1:-1:color=black,setsar=1,"
            f"fps={target_fps},format=yuv420p[v{idx}]"
        )
        audio_src = idx if info.has_audio else silent_input_index[idx]
        filters.append(
            f"[{audio_src}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{idx}]"
        )
        concat_pads.append(f"[v{idx}][a{idx}]")

    filter_complex = (
        ";".join(filters)
        + ";"
        + "".join(concat_pads)
        + f"concat=n={len(infos)}:v=1:a=1[outv][outa]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        output_path,
    ]

    result = _run_reencode(cmd, total_duration, progress_callback)
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "errore sconosciuto"
        raise MergeError(f"FFmpeg non è riuscito a unire i video: {detail}")


def merge_videos(input_paths: Sequence[str], output_path: str,
                 progress_callback: Optional[ProgressCallback] = None) -> str:
    """Merge two or more video files (in order) into ``output_path``.

    ``progress_callback``, if given, is called with a float in ``[0.0, 1.0]``
    as the re-encode progresses. The lossless fast path is effectively instant,
    so it simply reports ``1.0`` on completion.

    Returns the output path. Raises :class:`MergeError` on any problem.
    """
    paths = list(input_paths)
    if len(paths) < 2:
        raise MergeError("Sono necessari almeno 2 file video da unire.")

    infos = [_probe(p) for p in paths]

    if _try_fast_concat(infos, output_path):
        if progress_callback:
            progress_callback(1.0)
        return output_path

    _reencode_concat(infos, output_path, progress_callback)
    if progress_callback:
        progress_callback(1.0)
    return output_path
