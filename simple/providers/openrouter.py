"""OpenRouter image-generation provider.

OpenRouter doesn't expose a dedicated images endpoint — image-output models are
driven through the standard ``/chat/completions`` API with
``modalities=["image", "text"]``. The generated image comes back as a
``data:image/png;base64,...`` URL inside ``choices[0].message.images[]``.

Reference: https://openrouter.ai/docs/guides/overview/multimodal/image-generation

Cheapest viable model (as of the cached DAME snapshot) is
``google/gemini-2.5-flash-image`` ("Nano Banana"), which is the default here.
Override with the ``OPENROUTER_MODEL`` env var or the ``model=`` kwarg.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any

import requests

from simple.providers.base import (
    ImageProvider,
    ImageRequest,
    ImageResult,
    ProviderError,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/gemini-2.5-flash-image"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Known image-output models from OpenRouter (cached snapshot in DAME). Kept here
# so callers can pick something explicitly; not used for validation.
KNOWN_IMAGE_MODELS = (
    "google/gemini-2.5-flash-image",
    "google/gemini-3.1-flash-image-preview",
    "google/gemini-3-pro-image-preview",
    "openai/gpt-5-image",
    "openai/gpt-5-image-mini",
    "openai/gpt-5.4-image-2",
)

_DATA_URL_RE = re.compile(r"^data:image/(?P<fmt>[a-zA-Z0-9.+-]+);base64,(?P<b64>.+)$")


class OpenRouterProvider(ImageProvider):
    """Calls OpenRouter ``/chat/completions`` for image-output models."""

    name = "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 90.0,
        referer: str | None = None,
        app_title: str | None = "video-synthesizer",
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ProviderError(
                "OpenRouter API key missing. Set OPENROUTER_API_KEY or pass "
                "api_key=... to OpenRouterProvider()."
            )
        self.model = model or os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self._session = requests.Session()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter uses these to attribute traffic; both are optional.
        if referer or os.getenv("OPENROUTER_REFERER"):
            headers["HTTP-Referer"] = referer or os.getenv("OPENROUTER_REFERER", "")
        if app_title:
            headers["X-Title"] = app_title
        self._session.headers.update(headers)

    # ------------------------------------------------------------------ public

    def generate(self, request: ImageRequest) -> ImageResult:
        payload = self._build_payload(request)
        logger.debug("OpenRouter request payload: %s", _redact(payload))
        try:
            response = self._session.post(API_URL, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"HTTP error talking to OpenRouter: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"OpenRouter returned {response.status_code}: {response.text[:500]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError("OpenRouter returned non-JSON body") from exc

        png = _extract_png(body)
        if png is None:
            raise ProviderError(
                f"OpenRouter response had no image payload. Body: {str(body)[:500]}"
            )

        return ImageResult(
            png_bytes=png,
            provider=self.name,
            model=self.model,
            request=request,
            raw_response=body,
        )

    def close(self) -> None:
        self._session.close()

    # ----------------------------------------------------------------- helpers

    def _build_payload(self, request: ImageRequest) -> dict[str, Any]:
        prompt = request.prompt
        if request.negative_prompt:
            # OpenRouter image models don't have a first-class negative_prompt
            # field; we append it as a textual instruction.
            prompt = f"{prompt}\n\nAvoid: {request.negative_prompt}"

        payload: dict[str, Any] = {
            "model": self.model,
            "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": prompt}],
        }

        image_config: dict[str, Any] = {}
        if request.aspect_ratio:
            image_config["aspect_ratio"] = request.aspect_ratio
        # ``image_size`` is "small" / "medium" / "large" on Gemini-family models.
        # Allow callers to override via extras.
        size = request.extras.get("image_size")
        if size:
            image_config["image_size"] = size
        if image_config:
            payload["image_config"] = image_config

        if request.seed is not None:
            payload["seed"] = request.seed

        # Anything else the caller wants to pass straight through.
        for key in ("temperature", "top_p", "max_tokens"):
            if key in request.extras:
                payload[key] = request.extras[key]

        return payload


# --------------------------------------------------------------------- helpers


def _extract_png(body: dict[str, Any]) -> bytes | None:
    """Pull the first PNG out of an OpenRouter chat-completions response."""
    choices = body.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    images = message.get("images") or []
    for entry in images:
        url = (entry.get("image_url") or {}).get("url", "")
        match = _DATA_URL_RE.match(url)
        if match:
            try:
                return base64.b64decode(match.group("b64"))
            except (ValueError, TypeError):
                continue
    return None


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow-copy of payload with no secrets — used for debug logging."""
    return {k: ("<...>" if k == "api_key" else v) for k, v in payload.items()}
