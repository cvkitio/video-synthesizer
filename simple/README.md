# `simple/` — hosted image-gen → long test-video pipeline

A low-cost alternative to the self-hosted `diffusion/` (RunPod/Qwen) path.
**Cost is K provider calls per video, not K × fps × minutes.** A 5-minute
test feed is 5 OpenRouter calls.

## How it works

1. **Render keyframes.** The provider (default: OpenRouter →
   `google/gemini-2.5-flash-image`, "Nano Banana") is called K times
   (typically 4–8) with prompts drawn from a `Scene` — by default
   `SecurityCameraScene`, which holds the camera angle and scenery constant
   and varies only the foreground action.
2. **Stretch to length.** ffmpeg holds each keyframe for `duration / K`
   seconds and stitches with cuts, crossfades, or subtle ken-burns zoom.

## Layout

```
simple/
├── providers/        provider abstraction
│   ├── base.py         ImageProvider ABC + ImageRequest/ImageResult
│   ├── openrouter.py   OpenRouter chat-completions (image modality)
│   ├── mock.py         Local PIL placeholder — no network, for tests
│   └── registry.py     build_provider("openrouter") factory
├── scenes/
│   └── security_camera.py   prompt_for(i,N) + keyframe_prompts(K)
├── montage.py        ffmpeg keyframes → MP4 (cut / crossfade / ken_burns)
├── frame_builder.py  KeyframeFeedBuilder + FrameBuilder + CLI
├── requirements.txt
└── README.md
```

## Quick start

### Offline smoke test (no API key, no credit cost)

```bash
python -m simple.frame_builder \
    --provider mock \
    --keyframes 5 --duration 60 \
    --out demo.mp4
```

Produces 5 placeholder PNGs and stitches them into a 60-second MP4.

### Real run via OpenRouter

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
python -m simple.frame_builder \
    --provider openrouter \
    --model google/gemini-2.5-flash-image \
    --keyframes 5 --duration 300 \
    --transition crossfade --fps 24 \
    --out feed.mp4
```

That's **5 OpenRouter calls** for a 5-minute 24 fps MP4.

### Library use

```python
from simple.frame_builder import KeyframeFeedBuilder
from simple.providers import build_provider
from simple.scenes import SecurityCameraScene

with build_provider("openrouter") as provider:
    report = KeyframeFeedBuilder(provider, SecurityCameraScene()).build(
        keyframe_count=5,
        duration_seconds=300,
        fps=24,
        transition="crossfade",
        out_path="feed.mp4",
    )
print(report.video_path, report.plan)
```

## CLI reference

| Flag | Default | Meaning |
| --- | --- | --- |
| `--mode` | `keyframes` | `keyframes` (default, cheap) or `frames` (one call per output frame). |
| `--provider` | `openrouter` | Registered provider name. `mock` for offline. |
| `--model` | provider default | Model id passed to the provider. |
| `--keyframes` | `5` | Number of provider calls in keyframe mode. |
| `--duration` | `300` | Target video length in seconds (keyframe mode). |
| `--transition` | `crossfade` | `cut`, `crossfade`, or `ken_burns`. |
| `--transition-seconds` | `1.0` | Crossfade length. Ignored for `cut`. |
| `--fps` | `24` | Output video frame rate. |
| `--width` / `--height` | `1024` / `576` | Image and video resolution. |
| `--aspect-ratio` | `16:9` | Aspect-ratio hint sent to the provider. |
| `--seed` | `1000` | Base seed; keyframe `i` uses `seed + i`. |
| `--out` | `feed.mp4` | Output MP4 path. |
| `--frames-dir` / `--keep-frames` | — | Keep intermediate PNGs for inspection. |
| `--no-video` | — | Skip ffmpeg; just write PNGs. |

## Transitions

- **`cut`** — hard cuts between keyframes. Cheapest CPU, obvious slideshow.
- **`crossfade`** (default) — 1-second xfade between keyframes. Smooth, low CPU.
- **`ken_burns`** — slow centred zoom (1.00→1.06) on each keyframe plus
  crossfades. Output codec sees motion, so video-pipeline test consumers
  won't treat it as a still image. Costs more CPU at encode time.

## Providers

| Name | Description | Required env |
| --- | --- | --- |
| `openrouter` | OpenRouter `/chat/completions` with `modalities=["image","text"]`. Default model `google/gemini-2.5-flash-image`. | `OPENROUTER_API_KEY` |
| `mock` | Local PIL placeholder. No network. | — |

Add a provider by dropping a module in `simple/providers/` that subclasses
`ImageProvider` and registering it in `registry.py`.

### OpenRouter image-output models (from DAME's cached model list)

| Model id | Notes |
| --- | --- |
| `google/gemini-2.5-flash-image` | Cheapest. "Nano Banana." Default. |
| `google/gemini-3.1-flash-image-preview` | Newer preview. |
| `google/gemini-3-pro-image-preview` | Higher quality, ~10× the cost. |
| `openai/gpt-5-image-mini` | OpenAI mini. |
| `openai/gpt-5-image` | OpenAI full. |

## Cost notes

At the cached Gemini 2.5 Flash Image price tier, a single keyframe call is
fractions of a cent. A **5-minute test feed at 24 fps via the default
keyframe mode is ~5 calls**, vs. ~7200 calls if you tried to generate every
frame. The whole point of this package is the keyframe-and-hold model.

## What's left

- More providers: Replicate, fal.ai, Together. Each one is ~80 lines following
  the `OpenRouterProvider` template.
- Cost accounting: sum `raw_response["usage"]` across keyframes and surface in
  the `BuildReport`.
- Img2img coherence: Gemini 2.5 Flash Image supports passing a previous
  keyframe as input. Wiring this up would let consecutive keyframes look like
  the same lighting/paint/car, at ~2× per-keyframe cost. Not needed for
  testing, useful for demo footage.
- Per-frame mode (`--mode frames`) is preserved for completeness but is the
  expensive path; prefer keyframe mode unless you specifically need fresh
  imagery every frame.
