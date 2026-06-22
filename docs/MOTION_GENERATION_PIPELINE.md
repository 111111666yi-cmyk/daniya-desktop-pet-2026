# Daniya Motion Generation Pipeline

This document standardizes the toolchain for Daniya motion rebuild work when `image-2` outputs are visually unstable, drift in identity, or keep green spill around the silhouette.

## Goal

Produce motion candidates that are:

- visually consistent from frame to frame
- easy to matte into transparent PNG assets
- compatible with `tools/import_motion_sheet.py`

## Recommended toolchain

### 1. Generation and identity locking

Use these GitHub tools together instead of asking a single image model to draw the final 24-frame sheet directly:

- `ComfyUI`
- `ComfyUI_IPAdapter_plus`
- `ComfyUI-AnimateDiff-Evolved`
- `ComfyUI-Advanced-ControlNet`
- `ComfyUI-VideoHelperSuite`

Recommended role split:

- `ComfyUI`: base workflow host
- `IPAdapter`: lock Daniya identity and outfit
- `AnimateDiff`: maintain temporal continuity
- `Advanced-ControlNet`: constrain pose, reference, and timing
- `VideoHelperSuite`: load and export frame/video sequences

### 2. Matting and spill cleanup

Preferred order:

1. `RobustVideoMatting` for full motion sequences when you have rendered clips or a temporary video
2. `rembg` for still-frame or sprite-sheet cleanup when sequence matting is unavailable
3. repo chroma-key fallback for simple green-screen sheets

## Practical rules

### Do not ask `image-2` for the final production sprite sheet directly

Bad pattern:

- one prompt
- one 24-frame green-sheet
- direct runtime import

This causes the two problems seen in Daniya rebuild work:

- identity drift between cells
- dirty alpha / green spill / detached fragments

### Better generation pattern

Generate in two phases:

1. lock a clean reference identity
2. generate a short pose-controlled sequence or 4-8 key poses, then interpolate / expand in the runtime pipeline

### Avoid green when possible

If the generator can produce transparent background or clean solid neutral background, prefer that over bright green.

If you must use green:

- leave larger safe margins around each panel
- keep feet on one stable baseline
- avoid props, floating effects, or long hair crossing panel borders

## Repo import commands

### Chroma-key path

```bat
python tools\import_motion_sheet.py walk_loop candidate_sheet.png ^
  --grid-cols 6 ^
  --grid-rows 4 ^
  --frame-prefix walk ^
  --matting-backend chroma ^
  --chroma-key "#00ff00" ^
  --transparent-threshold 20 ^
  --opaque-threshold 110 ^
  --alpha-floor 24 ^
  --cell-inset-percent 0.04 ^
  --cleanup-islands ^
  --cleanup-alpha-threshold 24 ^
  --cleanup-min-component-area 96 ^
  --cleanup-near-margin-px 64 ^
  --target-frame-count 24 ^
  --resample-mode blend
```

### `rembg` path

Use this when the green screen is inconsistent or still leaves haze after chroma keying.

```bat
python tools\import_motion_sheet.py walk_loop candidate_sheet.png ^
  --grid-cols 6 ^
  --grid-rows 4 ^
  --frame-prefix walk ^
  --matting-backend rembg ^
  --alpha-floor 24 ^
  --cleanup-islands ^
  --cleanup-alpha-threshold 24 ^
  --cleanup-min-component-area 96 ^
  --cleanup-near-margin-px 64 ^
  --target-frame-count 24 ^
  --resample-mode blend
```

## Daniya acceptance focus

For `walk`, `idle`, and `talk`, reject any candidate that still shows one of these:

- face or hair shape changes from frame to frame
- foot baseline jumping in source-space QA
- detached alpha islands around hands, hair, or shoes
- green edge haze after import
- 24 frames that still look like near-static duplicates

Use `tools/import_motion_sheet.py` output and its QA report as the gate, not just eyeballing the contact sheet.
