"""Generate keyframes via a hosted image-gen provider and stitch them into a
longer test video using ffmpeg.

The default flow is **keyframe + hold**: the provider is called K times
(typically 4–8), each generated PNG is held on screen for several seconds,
and ffmpeg crossfades between them to produce a multi-minute MP4. This is
the cost-effective path — a 5-minute test feed is K provider calls, not
K × fps × minutes.

A legacy **per-frame** mode is still available via ``--mode frames`` for
short, high-frame-rate sequences.

CLI::

    # 5 OpenRouter calls → ~5-minute crossfaded MP4
    python -m simple.frame_builder \\
        --provider openrouter \\
        --keyframes 5 --duration 300 --fps 24 \\
        --transition crossfade --out feed.mp4

    # Offline smoke test
    python -m simple.frame_builder --provider mock \\
        --keyframes 5 --duration 60 --out demo.mp4

Library::

    from simple.frame_builder import KeyframeFeedBuilder
    from simple.providers import build_provider
    from simple.scenes import SecurityCameraScene

    with build_provider("openrouter") as provider:
        report = KeyframeFeedBuilder(provider, SecurityCameraScene()).build(
            keyframe_count=5, duration_seconds=300, out_path="feed.mp4"
        )
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from simple.montage import Transition, build_montage
from simple.providers import ImageProvider, ImageRequest, ProviderError, build_provider
from simple.scenes import SecurityCameraScene

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- protocols


class FrameScene(Protocol):
    """Scene used by per-frame mode — one prompt per output video frame."""

    def prompt_for(self, frame_index: int, total_frames: int) -> str: ...


class KeyframeScene(Protocol):
    """Scene used by keyframe mode — K prompts that span the sequence."""

    def keyframe_prompts(self, k: int) -> list[str]: ...


# ------------------------------------------------------------- shared report


@dataclass
class BuildReport:
    """Returned by both build modes."""

    frame_paths: list[Path] = field(default_factory=list)
    video_path: Path | None = None
    failed_frames: list[tuple[int, str]] = field(default_factory=list)
    plan: dict[str, object] | None = None

    @property
    def succeeded(self) -> bool:
        return not self.failed_frames and (
            self.video_path is None or self.video_path.exists()
        )


# ----------------------------------------------------------- shared renderer


class _Renderer:
    """Thin wrapper around an ``ImageProvider`` with retries and logging."""

    def __init__(
        self,
        provider: ImageProvider,
        *,
        width: int,
        height: int,
        aspect_ratio: str | None,
        negative_prompt: str | None,
        base_seed: int,
        retry: int,
        retry_backoff: float,
    ) -> None:
        self.provider = provider
        self.width = width
        self.height = height
        self.aspect_ratio = aspect_ratio
        self.negative_prompt = negative_prompt
        self.base_seed = base_seed
        self.retry = retry
        self.retry_backoff = retry_backoff

    def render(self, *, prompt: str, index: int, total: int) -> bytes:
        request = ImageRequest(
            prompt=prompt,
            negative_prompt=self.negative_prompt,
            width=self.width,
            height=self.height,
            aspect_ratio=self.aspect_ratio,
            seed=self.base_seed + index,
        )
        last_err: Exception | None = None
        for attempt in range(self.retry + 1):
            try:
                logger.info(
                    "image %d/%d: %s (%s)",
                    index + 1,
                    total,
                    self.provider.name,
                    getattr(self.provider, "model", "?"),
                )
                return self.provider.generate(request).png_bytes
            except ProviderError as exc:
                last_err = exc
                if attempt < self.retry:
                    delay = self.retry_backoff ** attempt
                    logger.warning(
                        "image %d failed (%s); retrying in %.1fs",
                        index + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
        raise ProviderError("retry loop exhausted") from last_err


# ---------------------------------------------------------- keyframe builder


class KeyframeFeedBuilder:
    """Generate K keyframes and stitch into a long MP4 with ffmpeg.

    This is the default flow. Cost scales with ``keyframe_count``, not video
    duration.
    """

    def __init__(
        self,
        provider: ImageProvider,
        scene: KeyframeScene,
        *,
        width: int = 1024,
        height: int = 576,
        aspect_ratio: str | None = "16:9",
        base_seed: int = 1000,
        negative_prompt: str | None = (
            "watermarks, logos, captions, low quality, blurry, double exposure"
        ),
        retry: int = 1,
        retry_backoff: float = 2.0,
    ) -> None:
        self.scene = scene
        self.renderer = _Renderer(
            provider,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            base_seed=base_seed,
            retry=retry,
            retry_backoff=retry_backoff,
        )

    def build(
        self,
        *,
        keyframe_count: int,
        duration_seconds: float,
        fps: int = 24,
        transition: Transition = "crossfade",
        transition_seconds: float = 1.0,
        out_path: str | os.PathLike[str] = "feed.mp4",
        work_dir: str | os.PathLike[str] | None = None,
        keep_frames: bool = False,
        encode_video: bool = True,
    ) -> BuildReport:
        if keyframe_count <= 0:
            raise ValueError("keyframe_count must be > 0")

        owns_work_dir = work_dir is None
        work_path = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="kf-"))
        work_path.mkdir(parents=True, exist_ok=True)

        report = BuildReport()
        prompts = self.scene.keyframe_prompts(keyframe_count)

        try:
            for i, prompt in enumerate(prompts):
                try:
                    png = self.renderer.render(
                        prompt=prompt, index=i, total=keyframe_count
                    )
                except ProviderError as exc:
                    logger.error("keyframe %d failed permanently: %s", i + 1, exc)
                    report.failed_frames.append((i, str(exc)))
                    continue
                path = work_path / f"keyframe_{i:03d}.png"
                path.write_bytes(png)
                report.frame_paths.append(path)

            if encode_video and report.frame_paths:
                plan = build_montage(
                    report.frame_paths,
                    Path(out_path),
                    total_seconds=duration_seconds,
                    fps=fps,
                    transition=transition,
                    transition_seconds=transition_seconds,
                )
                report.video_path = Path(out_path)
                report.plan = {
                    "mode": "keyframes",
                    "keyframe_count": plan.keyframe_count,
                    "hold_seconds": plan.hold_seconds,
                    "transition": transition,
                    "transition_seconds": plan.transition_seconds,
                    "total_seconds": plan.total_seconds,
                    "fps": fps,
                }
            elif encode_video and not report.frame_paths:
                logger.error("no keyframes rendered; skipping MP4 encode")

            return report
        finally:
            if owns_work_dir and not keep_frames:
                shutil.rmtree(work_path, ignore_errors=True)


# ----------------------------------------------------------- per-frame builder
# Kept around for when you really do want one provider call per output frame.


class FrameBuilder:
    """One provider call per output video frame, then concatenate at ``fps``.

    Expensive at non-trivial durations — prefer :class:`KeyframeFeedBuilder`
    unless you specifically want fresh imagery on every frame.
    """

    def __init__(
        self,
        provider: ImageProvider,
        scene: FrameScene,
        *,
        width: int = 1024,
        height: int = 576,
        aspect_ratio: str | None = "16:9",
        base_seed: int = 1000,
        negative_prompt: str | None = (
            "watermarks, logos, captions, low quality, blurry, double exposure"
        ),
        retry: int = 1,
        retry_backoff: float = 2.0,
    ) -> None:
        self.scene = scene
        self.renderer = _Renderer(
            provider,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
            base_seed=base_seed,
            retry=retry,
            retry_backoff=retry_backoff,
        )

    def build(
        self,
        *,
        frame_count: int,
        fps: float = 2.0,
        out_path: str | os.PathLike[str] | None = "feed.mp4",
        work_dir: str | os.PathLike[str] | None = None,
        keep_frames: bool = False,
        encode_video: bool = True,
    ) -> BuildReport:
        if frame_count <= 0:
            raise ValueError("frame_count must be > 0")

        owns_work_dir = work_dir is None
        work_path = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="frames-"))
        work_path.mkdir(parents=True, exist_ok=True)

        report = BuildReport()
        try:
            for i in range(frame_count):
                prompt = self.scene.prompt_for(i, frame_count)
                try:
                    png = self.renderer.render(prompt=prompt, index=i, total=frame_count)
                except ProviderError as exc:
                    logger.error("frame %d failed permanently: %s", i + 1, exc)
                    report.failed_frames.append((i, str(exc)))
                    continue
                path = work_path / f"frame_{i:05d}.png"
                path.write_bytes(png)
                report.frame_paths.append(path)

            if encode_video and report.frame_paths:
                video_path = Path(out_path) if out_path else work_path / "feed.mp4"
                _encode_per_frame_mp4(report.frame_paths, video_path, fps=fps)
                report.video_path = video_path
                report.plan = {
                    "mode": "frames",
                    "frame_count": len(report.frame_paths),
                    "fps": fps,
                }
            elif encode_video and not report.frame_paths:
                logger.error("no frames rendered; skipping MP4 encode")

            return report
        finally:
            if owns_work_dir and not keep_frames:
                shutil.rmtree(work_path, ignore_errors=True)


def _encode_per_frame_mp4(
    frame_paths: list[Path], out_path: Path, *, fps: float
) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH.")
    frame_dir = frame_paths[0].parent
    pattern = str(frame_dir / "frame_%05d.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {proc.returncode}):\n{proc.stderr[-800:]}"
        )


# --------------------------------------------------------------------- CLI


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m simple.frame_builder",
        description="Generate a long security-camera test MP4 from a small number of hosted image-gen calls.",
    )
    p.add_argument(
        "--mode",
        choices=["keyframes", "frames"],
        default="keyframes",
        help="keyframes (default, cheap) holds K generated images for a long total duration; "
             "frames generates a fresh image for every output video frame.",
    )
    p.add_argument(
        "--provider",
        default=os.getenv("VIDEO_SYNTH_PROVIDER", "openrouter"),
        help="Provider name (default: openrouter). 'mock' is offline.",
    )
    p.add_argument("--model", default=None, help="Provider model id (optional).")
    p.add_argument("--api-key", default=None, help="Override provider API key.")
    # keyframe mode
    p.add_argument("--keyframes", type=int, default=5, help="Number of provider calls in keyframe mode (default: 5).")
    p.add_argument("--duration", type=float, default=300.0, help="Target video length in seconds for keyframe mode (default: 300 = 5 min).")
    p.add_argument(
        "--transition",
        choices=["cut", "crossfade", "ken_burns"],
        default="crossfade",
        help="How to transition between keyframes (default: crossfade).",
    )
    p.add_argument("--transition-seconds", type=float, default=1.0, help="Length of each transition (default: 1.0).")
    # frames mode
    p.add_argument("--frames", type=int, default=8, help="Per-frame mode: number of frames to generate.")
    # shared
    p.add_argument("--fps", type=float, default=24.0, help="Output video frame rate (default: 24).")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=576)
    p.add_argument("--aspect-ratio", default="16:9")
    p.add_argument("--seed", type=int, default=1000, help="Base seed; image i uses seed+i.")
    p.add_argument("--out", default="feed.mp4", help="Output MP4 path.")
    p.add_argument("--frames-dir", default=None, help="Where to write intermediate PNGs. Default: temp dir.")
    p.add_argument("--keep-frames", action="store_true", help="Don't delete PNG keyframes after encoding.")
    p.add_argument("--no-video", action="store_true", help="Skip ffmpeg; just write PNGs.")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    provider_kwargs: dict[str, object] = {}
    if args.model:
        provider_kwargs["model"] = args.model
    if args.api_key and args.provider == "openrouter":
        provider_kwargs["api_key"] = args.api_key

    try:
        provider = build_provider(args.provider, **provider_kwargs)
    except ProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    scene = SecurityCameraScene()

    try:
        if args.mode == "keyframes":
            builder = KeyframeFeedBuilder(
                provider, scene,
                width=args.width, height=args.height,
                aspect_ratio=args.aspect_ratio, base_seed=args.seed,
            )
            report = builder.build(
                keyframe_count=args.keyframes,
                duration_seconds=args.duration,
                fps=int(args.fps),
                transition=args.transition,
                transition_seconds=args.transition_seconds,
                out_path=args.out,
                work_dir=args.frames_dir,
                keep_frames=args.keep_frames,
                encode_video=not args.no_video,
            )
        else:
            builder = FrameBuilder(
                provider, scene,
                width=args.width, height=args.height,
                aspect_ratio=args.aspect_ratio, base_seed=args.seed,
            )
            report = builder.build(
                frame_count=args.frames,
                fps=args.fps,
                out_path=args.out,
                work_dir=args.frames_dir,
                keep_frames=args.keep_frames,
                encode_video=not args.no_video,
            )
    finally:
        provider.close()

    summary = {
        "mode": args.mode,
        "images_generated": len(report.frame_paths),
        "images_failed": len(report.failed_frames),
        "video": str(report.video_path) if report.video_path else None,
        "plan": report.plan,
        "failures": report.failed_frames,
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.succeeded else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
