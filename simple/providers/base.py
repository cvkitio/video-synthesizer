"""Provider-agnostic types for image generation.

The abstraction is deliberately narrow: a provider takes an
:class:`ImageRequest` (prompt + size + seed + provider-specific extras) and
returns an :class:`ImageResult` (PNG bytes + metadata). Anything fancier
(streaming, video) is left to the caller to assemble on top.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Mapping


class ProviderError(RuntimeError):
    """Raised when a provider fails to produce an image.

    The original exception, if any, is preserved as ``__cause__``.
    """


@dataclass(frozen=True)
class ImageRequest:
    """A single image-generation request.

    Attributes:
        prompt:       Natural-language description of the image.
        negative_prompt: Optional anti-prompt. Providers that do not support
                      negative prompts should ignore this.
        width:        Pixel width hint. Some providers only honour
                      ``aspect_ratio``; this is then used to pick the closest
                      preset.
        height:       Pixel height hint. See ``width``.
        aspect_ratio: Optional aspect-ratio hint (e.g. ``"16:9"``). Takes
                      precedence over width/height when the provider only
                      supports presets.
        seed:         Optional deterministic seed. Most hosted providers honour
                      this loosely; expect drift between frames.
        extras:       Provider-specific overrides (e.g. ``image_size``,
                      ``num_inference_steps``). Unrecognised keys are ignored.
    """

    prompt: str
    negative_prompt: str | None = None
    width: int = 1024
    height: int = 576
    aspect_ratio: str | None = "16:9"
    seed: int | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageResult:
    """The PNG bytes returned by a provider plus light metadata.

    ``png_bytes`` is the only field downstream code (e.g. the MP4 stitcher)
    needs. Everything else is for logging and cost tracking.
    """

    png_bytes: bytes
    provider: str
    model: str
    request: ImageRequest
    raw_response: Mapping[str, Any] | None = None


class ImageProvider(abc.ABC):
    """Abstract base for image-generation backends.

    Subclasses implement :meth:`generate`. The constructor should accept the
    minimal set of credentials/config it needs and raise a clear error if
    something required is missing — *not* fail lazily at request time.
    """

    #: Stable, lower-case provider id used by the registry (e.g. ``"openrouter"``).
    name: str = "abstract"

    @abc.abstractmethod
    def generate(self, request: ImageRequest) -> ImageResult:
        """Synchronously produce one image.

        Implementations must raise :class:`ProviderError` (with the original
        exception chained as ``__cause__``) on any failure so callers can
        catch a single exception type.
        """

    def close(self) -> None:
        """Optional hook for releasing HTTP sessions etc. Default is a no-op."""
        return None

    # Context-manager sugar so callers can ``with build_provider(...) as p:``.
    def __enter__(self) -> "ImageProvider":  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        self.close()
