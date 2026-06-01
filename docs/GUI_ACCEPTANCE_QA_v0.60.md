# GUI Acceptance QA v0.60

Date: 2026-06-01
Branch: `stabilize-v0.56-v0.60`

## Scope

This document records the GUI acceptance pass performed after the MiMo OpenAI-compatible auth fix.

The automated GUI pass used temporary runtime directories under `scratch/` and did not touch the user's real `.env`, `data/`, AppData, private assets, or models.

## Automated GUI Checks

Environment:

```text
QT_QPA_PLATFORM=offscreen
DANIYA_RUNTIME_ROOT=scratch/gui_acceptance_v060_runtime
DANIYA_RELATION_DATA_DIR=scratch/gui_acceptance_v060_relation
```

Results:

| Area | Result | Evidence |
| --- | --- | --- |
| First-run wizard opens | PASS | Wizard has 5 pages. |
| First-run skip API path | PASS | Writes `first_run_done.json` with `run_mode=local_fallback`. |
| First-run MiMo save path | PASS | `xiaomimimo.com` OpenAI-compatible profile saves `auth_header=api-key`. |
| MiMo key safety | PASS | API key is written to `.env`, not JSON config. |
| Main pet window startup | PASS | Window becomes visible in isolated runtime. |
| Pet pixmap render | PASS | Pet pixmap is present and non-null. |
| Right-click/context menu | PASS | Menu opens and exposes top-level submenus. |
| Settings Center opens | PASS | Settings Center becomes visible with 5 tabs. |
| Auth Header control | PASS | Settings Center exposes `bearer`, `api-key`, `x-api-key`, and `none`. |
| Drag clamp | PASS | Dragging to an extreme coordinate remains inside the screen bounds. |
| Edge docking positions | PASS | Left, right, top, and bottom dock positions remain inside screen bounds. |
| Long text bubble layout | PASS | Bubble remains visible, max width is 300, and window stays inside screen bounds. |
| Screenshot smoke | PASS | Long-text screenshot was generated in the temporary runtime. |

## Special Sentence Checks

The special sentence checks were rerun with Unicode escapes to avoid PowerShell console encoding corruption.

| Input | Result | Source | Action |
| --- | --- | --- | --- |
| `抱抱` | PASS | `special_response` | `happy` |
| `我好累` | PASS | `special_response` | `remind` |
| `晚安，顺便提醒我明天喝水` without model | PASS | `local_fallback` | `soft_idle` |
| `晚安，顺便提醒我明天喝水` with model | PASS | `api` | `talk` |

The combined "晚安 + reminder" sentence did not create a due reminder or trigger the reminder-due path during this automated check.

## Package Smoke Checks

Commands run:

```bat
pack.bat
.venv\Scripts\python.exe tools\check_release_zip.py release\DaniyaSummerPet-v0.60-win-x64.zip
```

Results:

- Release zip entry count: `449`
- Forbidden entries: none
- Secret hits: none
- MiMo QA documentation included in zip: PASS
- Release exe smoke: PASS, alive after 10 seconds with isolated AppData runtime
- Release directory runtime leaks: none
- Source startup smoke: PASS, alive after 8 seconds with isolated runtime and no leftover `main.py` process

## Limits

This pass is an automated GUI smoke and layout check, not a human physical observation pass. The following remain manual acceptance items:

- Real monitor/desktop visual feel of dragging and snapping.
- Real right-click interaction feel with mouse input.
- Real font rendering on the user's display and Windows theme.
- Human observation of whether long bubbles look aesthetically acceptable, beyond the automated no-overlap/no-offscreen checks.
