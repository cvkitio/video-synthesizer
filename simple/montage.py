"""Stretch a handful of keyframe PNGs into a long MP4 using ffmpeg.

This is the actual cost-saver: instead of generating one image per output
video frame (which would mean hundreds of OpenRouter calls for a 5-minute
clip), we generate K keyframes and hold each on screen for several seconds.
For testing pipelines that consume video, this is usually more than enough.

Three transition modes are supported:

* ``cut``       — hard cuts between keyframes. Lowest CPU; obviously a slideshow.
* ``crossfade`` — 1-second xfade between keyframes (default). Smooth.
* ``ken_burns`` — slow zoom on each keyframe plus crossfades. Gives the
                  output codec something to chew on so test consumers don't
                  see a near-static image.

ffmpeg ≥ 4.3 (for the ``xfade`` filter) is required for any mode other than
``cut``. ``ffprobe`` is not required.
"""

from __future__ import annotations

import logging
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

logger = logging.getLogger(__name__)

Transition = Literal["cut", "crossfade", "ken_burns"]


@dataclass(frozen=True)
class MontagePlan:
    """Resolved per-keyframe timing — exposed mostly for logging/tests."""

    hold_seconds: float
    transition_seconds: float
    total_seconds: float
    keyframe_count: int

    def offsets(self) -> list[float]:
        """xfade ``offset=`` values, one per transition (``keyframe_count - 1``)."""
        return [
            (i + 1) * self.hold_seconds - (i + 1) * self.transition_seconds
            for i in range(self.keyframe_count - 1)
        ]


def plan_montage(
    *,
    keyframe_count: int,
    total_seconds: float,
    transition_seconds: float,
    transition: Transition,
) -> MontagePlan:
    """Compute per-keyframe hold time so the final video lands on ``total_seconds``.

    With ``crossfade``/``ken_burns`` the transitions overlap the held images,
    so total duration = ``k*hold - (k-1)*transition``. With ``cut`` the
    transitions are zero-length.
    """
    if keyframe_count < 1:
        raise ValueError("keyframe_count must be >= 1")
    if total_seconds <= 0:
        raise ValueError("total_seconds must be > 0")
    if transition_seconds < 0:
        raise ValueError("transition_seconds must be >= 0")

    if transition == "cut" or keyframe_count == 1:
        effective_transition = 0.0
    else:
        effective_transition = transition_seconds

    # total = k * hold - (k - 1) * transition  =>  hold = (total + (k-1)*t) / k
    hold = (total_seconds + (keyframe_count - 1) * effective_transition) / keyframe_count
    if hold <= effective_transition:
        raise ValueError(
            f"hold_seconds={hold:.2f} would be <= transition_seconds="
            f"{effective_transition:.2f}; lower --transition-seconds or use more keyframes"
        )
    return MontagePlan(
        hold_seconds=hold,
        transition_seconds=effective_transition,
        total_seconds=total_seconds,
        keyframe_count=keyframe_count,
    )


def build_montage(
    keyframe_paths: Sequence[Path],
    out_path: Path,
    *,
    total_seconds: float,
    fps: int = 24,
    transition: Transition = "crossfade",
    transition_seconds: float = 1.0,
    crf: int = 23,
    extra_ffmpeg_args: Sequence[str] = (),
) -> MontagePlan:
    """Run ffmpeg to produce an MP4 of length ``total_seconds`` from keyframes.

    Args:
        keyframe_paths: PNG/JPG paths in playback order. Must all be the same
                        resolution; ffmpeg won't auto-resize for ``xfade``.
        out_path:       Destination ``.mp4``. Parent directories are created.
        total_seconds:  Target wall-clock length of the output video.
        fps:            Output frame rate. 24 looks natural; pick 12 or 15 if
                        CCTV-feel matters more.
        transition:     ``cut`` | ``crossfade`` | ``ken_burns``.
        transition_seconds: Length of each transition. Ignored for ``cut``.
        crf:            libx264 quality; lower = larger file, better quality.
        extra_ffmpeg_args: Appended just before the output path. Escape hatch.

    Returns:
        The :class:`MontagePlan` actually used.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`)."
        )
    keyframe_paths = list(keyframe_paths)
    if not keyframe_paths:
        raise ValueError("at least one keyframe is required")

    plan = plan_montage(
        keyframe_count=len(keyframe_paths),
        total_seconds=total_seconds,
        transition_seconds=transition_seconds,
        transition=transition,
    )
    logger.info(
        "montage plan: %d keyframes × %.2fs hold (%s, %.2fs xfade) → %.1fs @ %d fps",
        plan.keyframe_count,
        plan.hold_seconds,
        transition,
        plan.transition_seconds,
        plan.total_seconds,
        fps,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if transition == "cut" or plan.keyframe_count == 1:
        cmd = _cut_command(keyframe_paths, out_path, plan, fps=fps, crf=crf)
    else:
        size = _read_png_size(keyframe_paths[0])
        cmd = _xfade_command(
            keyframe_paths,
            out_path,
            plan,
            fps=fps,
            crf=crf,
            ken_burns=(transition == "ken_burns"),
            size=size,
        )
    cmd.extend(extra_ffmpeg_args)
    cmd.append(str(out_path))

    logger.debug("ffmpeg cmd: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}):\n{proc.stderr[-1200:]}"
        )
    return plan


# ------------------------------------------------------------------ ffmpeg cmds


def _cut_command(
    keyframe_paths: Sequence[Path],
    out_path: Path,
    plan: MontagePlan,
    *,
    fps: int,
    crf: int,
) -> list[str]:
    """Hard-cut concat. Each keyframe held for ``plan.hold_seconds``."""
    cmd: list[str] = ["ffmpeg", "-y"]
    for path in keyframe_paths:
        cmd += ["-loop", "1", "-t", f"{plan.hold_seconds:.3f}", "-i", str(path)]
    # Concat filter — one input per keyframe.
    n = len(keyframe_paths)
    inputs = "".join(f"[{i}:v]" for i in range(n))
    filter_complex = (
        f"{inputs}concat=n={n}:v=1:a=0[v];"
        "[v]pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p[vout]"
    )
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-r", str(fps),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "veryfast",
        "-movflags", "+faststart",
    ]
    return cmd


def _xfade_command(
    keyframe_paths: Sequence[Path],
    out_path: Path,
    plan: MontagePlan,
    *,
    fps: int,
    crf: int,
    ken_burns: bool,
    size: tuple[int, int],
) -> list[str]:
    """xfade chain — optionally with a zoompan ken-burns prefilter per input."""
    cmd: list[str] = ["ffmpeg", "-y"]
    for path in keyframe_paths:
        cmd += ["-loop", "1", "-t", f"{plan.hold_seconds:.3f}", "-i", str(path)]

    n = len(keyframe_paths)
    filters: list[str] = []
    width, height = size

    # Per-input preprocessing. zoompan's ``d`` is frames-per-input-frame, and
    # ``-loop 1 -t T`` feeds it many input frames, which causes the output to
    # explode. We pin to a single input frame (``trim=end_frame=1``) and let
    # zoompan extend it to ``d`` outputs at ``fps``.
    for i in range(n):
        if ken_burns:
            zoom_frames = max(1, int(plan.hold_seconds * fps))
            zoom_step = 0.06 / zoom_frames
            filters.append(
                f"[{i}:v]trim=end_frame=1,setpts=PTS-STARTPTS,"
                f"zoompan=z='min(zoom+{zoom_step:.6f},1.06)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={zoom_frames}:s={width}x{height}:fps={fps},"
                f"setsar=1,format=yuv420p[v{i}]"
            )
        else:
            filters.append(
                f"[{i}:v]fps={fps},setsar=1,format=yuv420p[v{i}]"
            )

    # Build the xfade chain. Each xfade has offset = (i+1)*hold - (i+1)*transition.
    prev_label = "v0"
    for i, offset in enumerate(plan.offsets()):
        next_label = f"x{i}"
        filters.append(
            f"[{prev_label}][v{i + 1}]"
            f"xfade=transition=fade:duration={plan.transition_seconds:.3f}:"
            f"offset={offset:.3f}[{next_label}]"
        )
        prev_label = next_label

    # Final pad-to-even (libx264 requires even dimensions).
    filters.append(f"[{prev_label}]pad=ceil(iw/2)*2:ceil(ih/2)*2[vout]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]",
        "-r", str(fps),
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    return cmd


def _read_png_size(path: Path) -> tuple[int, int]:
    """Parse a PNG IHDR for its width/height without dragging in Pillow.

    Falls back to Pillow if the header doesn't look like a PNG (e.g. a JPG
    was passed in).
    """
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
        width, height = struct.unpack(">II", header[16:24])
        return int(width), int(height)
    # Fallback for non-PNG inputs.
    from PIL import Image  # noqa: WPS433 — local import is intentional

    with Image.open(path) as img:
        return int(img.width), int(img.height)
