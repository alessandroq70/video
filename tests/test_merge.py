"""Unit tests for the video merge logic.

Test clips are generated on the fly with the bundled FFmpeg, so no fixture
files are needed.
"""
import os
import subprocess

import pytest
import imageio_ffmpeg

from video_merger import MergeError, merge_videos, _probe

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def make_video(path, size="320x240", rate=30, duration=2, with_audio=True):
    cmd = [FFMPEG, "-y", "-f", "lavfi", "-i",
           f"testsrc=size={size}:rate={rate}:duration={duration}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    cmd += ["-c:v", "libx264"]
    if with_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += ["-loglevel", "error", path]
    subprocess.run(cmd, check=True)
    return path


def test_merge_same_format_uses_fast_path(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"), duration=2)
    b = make_video(str(tmp_path / "b.mp4"), duration=3)
    out = str(tmp_path / "out.mp4")
    merge_videos([a, b], out)

    info = _probe(out)
    assert info.width == 320 and info.height == 240
    assert 4.5 < info.duration < 5.6  # ~2 + 3 seconds
    assert info.has_audio


def test_merge_different_resolutions_reencodes(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"), size="640x480", rate=25, duration=4, with_audio=False)
    b = make_video(str(tmp_path / "b.mp4"), size="320x240", rate=30, duration=2, with_audio=True)
    out = str(tmp_path / "out.mp4")
    merge_videos([a, b], out)

    info = _probe(out)
    # Canvas is the largest of the inputs.
    assert info.width == 640 and info.height == 480
    assert 5.5 < info.duration < 6.6  # ~4 + 2 seconds
    assert info.has_audio  # silent track added for the audio-less clip


def test_single_file_raises(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"))
    with pytest.raises(MergeError):
        merge_videos([a], str(tmp_path / "out.mp4"))


def test_no_files_raises(tmp_path):
    with pytest.raises(MergeError):
        merge_videos([], str(tmp_path / "out.mp4"))


def test_invalid_input_raises(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"))
    bad = str(tmp_path / "bad.mp4")
    with open(bad, "wb") as fh:
        fh.write(b"not a real video")
    with pytest.raises(MergeError):
        merge_videos([a, bad], str(tmp_path / "out.mp4"))


def test_progress_callback_fast_path_reports_completion(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"), duration=2)
    b = make_video(str(tmp_path / "b.mp4"), duration=2)
    seen = []
    merge_videos([a, b], str(tmp_path / "out.mp4"), progress_callback=seen.append)
    # The lossless fast path is instant, but it must still report completion.
    assert seen and seen[-1] == 1.0


def test_progress_callback_reencode_reports_monotonic_progress(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"), size="640x480", rate=25, duration=4)
    b = make_video(str(tmp_path / "b.mp4"), size="320x240", rate=30, duration=3)
    seen = []
    merge_videos([a, b], str(tmp_path / "out.mp4"), progress_callback=seen.append)

    assert seen, "expected the re-encode to report progress"
    assert all(0.0 <= f <= 1.0 for f in seen)
    assert seen == sorted(seen), "progress should never go backwards"
    assert seen[-1] == 1.0


def test_probe_reads_stream_info(tmp_path):
    a = make_video(str(tmp_path / "a.mp4"), size="640x480", rate=30, duration=2)
    info = _probe(a)
    assert info.width == 640 and info.height == 480
    assert abs(info.fps - 30) < 1.0
    assert 1.8 < info.duration < 2.4
    assert info.has_audio
