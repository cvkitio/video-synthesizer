"""Tiny string-keyed factory for :class:`~simple.providers.base.ImageProvider`.

Kept separate from ``__init__`` so it can be imported without forcing every
provider module (and its third-party deps) to load.
"""

from __future__ import annotations

from typing import Any, Callable

from simple.providers.base import ImageProvider, ProviderError


def _build_openrouter(**kwargs: Any) -> ImageProvider:
    from simple.providers.openrouter import OpenRouterProvider

    return OpenRouterProvider(**kwargs)


def _build_mock(**kwargs: Any) -> ImageProvider:
    from simple.providers.mock import MockProvider

    return MockProvider(**kwargs)


# Add new providers (replicate, fal, together, ...) here.
_REGISTRY: dict[str, Callable[..., ImageProvider]] = {
    "openrouter": _build_openrouter,
    "mock": _build_mock,
}


def list_providers() -> list[str]:
    """Names accepted by :func:`build_provider`."""
    return sorted(_REGISTRY)


def build_provider(name: str, **kwargs: Any) -> ImageProvider:
    """Instantiate a provider by registry name.

    Raises:
        ProviderError: if ``name`` is unknown.
    """
    try:
        factory = _REGISTRY[name.lower()]
    except KeyError as exc:
        raise ProviderError(
            f"Unknown provider {name!r}. Known: {', '.join(list_providers())}"
        ) from exc
    return factory(**kwargs)
