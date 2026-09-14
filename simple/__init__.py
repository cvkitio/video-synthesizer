"""simple — hosted image-generation pipeline.

A small, dependency-light alternative to the self-hosted ``diffusion/`` path.
Frames are produced by a pluggable :mod:`simple.providers` backend and stitched
into an MP4 by :mod:`simple.frame_builder`.
"""

__all__ = ["frame_builder", "providers", "scenes"]
