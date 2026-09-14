"""A simple security-camera scene generator.

A "scene" is a callable that produces a prompt for frame *i* of *N*. The
intent here is to keep the camera pose and scenery stable across frames while
varying a single foreground event, so the stitched MP4 reads as a sequence
from the same fixed camera rather than a slideshow of unrelated images.

Hosted image models don't have temporal coherence — frames *will* drift in
small details (lighting, paint, exact car make). For a test feed that's fine;
the goal is to exercise the pipeline, not to fool an analyst.
"""

from __future__ import annotations

from dataclasses import dataclass

# Foreground actions, looped if the requested frame count exceeds the list.
DEFAULT_ACTIONS = (
    "the lot is empty and still",
    "a silver sedan slowly drives in from the left and parks in the third bay",
    "the driver, wearing a dark hoodie, steps out of the silver sedan",
    "the hoodie figure walks across the lot toward the side entrance",
    "the side entrance door is propped open, light spills onto the asphalt",
    "the hoodie figure has disappeared inside; the lot is still",
    "a small fox trots across the foreground from right to left",
    "the silver sedan's brake lights flicker on; exhaust drifts from the tailpipe",
    "the hoodie figure reappears at the door carrying a cardboard box",
    "the silver sedan reverses out of the bay, headlights sweeping the camera",
)

BASE_STYLE = (
    "Low-resolution colour CCTV still from a fixed pole-mounted security camera, "
    "ultra-wide lens with slight barrel distortion, 16:9 frame, mild rolling-shutter "
    "skew, ambient sodium-vapour streetlight casting an orange tint, dim ambient light, "
    "shallow JPEG compression artefacts, faint timecode burn-in not legible. "
    "Camera is mounted ~4m above ground looking down at a small suburban car park at "
    "night, four parking bays visible, a single-storey grey-brick building on the right "
    "with a glass side entrance, low chain-link fence at the back of the lot."
)


@dataclass(frozen=True)
class SecurityCameraScene:
    """Generate one prompt per frame for a fixed-camera car-park scene.

    Attributes:
        actions:      Ordered foreground events. Frames cycle through these.
        style:        Camera/setting description applied to every frame.
        timestamp_label: Optional label rendered into the prompt's text overlay
                      request (most models will *try* but won't render text
                      perfectly — don't rely on it).
    """

    actions: tuple[str, ...] = DEFAULT_ACTIONS
    style: str = BASE_STYLE
    timestamp_label: str | None = "CAM-01"

    def prompt_for(self, frame_index: int, total_frames: int) -> str:
        """Return the prompt for frame ``frame_index`` of ``total_frames``.

        Used by per-frame generation. Each frame steps to the next action.
        """
        if not self.actions:
            raise ValueError("SecurityCameraScene requires at least one action")
        action = self.actions[frame_index % len(self.actions)]
        return self._wrap(action, progress=f"frame {frame_index + 1} of {total_frames}")

    def keyframe_prompts(self, k: int) -> list[str]:
        """Return ``k`` prompts that span the action sequence.

        Used by the keyframe-montage flow: a small number of generated images
        are held for several seconds each in the output video. The chosen
        moments are spaced across :attr:`actions` so the video has visible
        story beats rather than ``k`` near-duplicates.
        """
        if k <= 0:
            raise ValueError("k must be > 0")
        if not self.actions:
            raise ValueError("SecurityCameraScene requires at least one action")
        # Evenly sample ``k`` actions from the full list.
        if k >= len(self.actions):
            chosen = list(self.actions[:k])
        else:
            step = (len(self.actions) - 1) / (k - 1) if k > 1 else 0
            indices = [round(i * step) for i in range(k)] if k > 1 else [0]
            chosen = [self.actions[i] for i in indices]
        return [
            self._wrap(action, progress=f"keyframe {i + 1} of {k}")
            for i, action in enumerate(chosen)
        ]

    # ----------------------------------------------------------------- helpers

    def _wrap(self, action: str, *, progress: str) -> str:
        label = (
            f" Overlay timestamp text in the top-left reading '{self.timestamp_label}'."
            if self.timestamp_label
            else ""
        )
        return (
            f"{self.style} In this {progress}, {action}.{label} "
            "Keep the camera angle, framing, building, parking bays, and fence "
            "identical to other frames in the sequence."
        )
