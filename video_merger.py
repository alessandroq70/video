"""Core logic for merging video files using FFmpeg.

FFmpeg is provided by the ``imageio-ffmpeg`` package (a bundled static build),
so no separate FFmpeg installation is required.

Two strategies are used:

* **Fast path (lossless):** when the inputs already share the same codec,
  resolution and frame rate, they are concatenated with stream copy — instant
  and no quality loss. Ideal for joining parts of the same recording.
* **Re-encode path:** otherwise the inputs are normalised (scaled and padded
  to a common canvas, given a uniform frame rate and a guaranteed audio track)
  and re-encoded to a standard H.264/AAC MP4. Handles clips of different
  formats, resolutions, or with/without audio.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Sequence

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Hide ffmpeg console windows on Windows when launched from a GUI/no-console.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


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


def _probe(path: str) -> VideoInfo:
    """Read basic stream info by parsing ``ffmpeg -i`` output."""
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


def _reencode_concat(infos: List[VideoInfo], output_path: str) -> None:
    """Normalise every input to a common canvas and re-encode into one MP4."""
    canvas_w = _even(max(i.width for i in infos))
    canvas_h = _even(max(i.height for i in infos))
    target_fps = round(max(i.fps for i in infos)) or 30

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
        output_path,
    ]

    result = _run(cmd)
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "errore sconosciuto"
        raise MergeError(f"FFmpeg non è riuscito a unire i video: {detail}")


def merge_videos(input_paths: Sequence[str], output_path: str) -> str:
    """Merge two or more video files (in order) into ``output_path``.

    Returns the output path. Raises :class:`MergeError` on any problem.
    """
    paths = list(input_paths)
    if len(paths) < 2:
        raise MergeError("Sono necessari almeno 2 file video da unire.")

    infos = [_probe(p) for p in paths]

    if _try_fast_concat(infos, output_path):
        return output_path

    _reencode_concat(infos, output_path)
    return output_path
