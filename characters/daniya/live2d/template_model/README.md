# Live2D Template Slot

This directory is the public binding slot for Daniya's optional Live2D preview model.

Expected private payload at runtime:

- `*.model3.json`
- `*.moc3`
- `textures/`
- `motions/`
- `expressions/`
- `physics3.json` (optional)

Rules:

- Keep `bindings.json` as the only state-to-motion mapping source.
- Missing Live2D files must fall back to the mapped sprite state without warnings that spam the user.
- Do not commit licensed model binaries to the public repo by default.

