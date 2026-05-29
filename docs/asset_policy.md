# Asset Policy

Daniya Summer Desktop Pet is an unofficial fan project. Public repository assets are intentionally limited.

## Repository Rules

- The repository does not distribute official game resources.
- The repository does not distribute unauthorized character art, voice, model, Live2D, or animation resources.
- The repository only provides placeholder assets under `assets/placeholder/`.
- User-provided private assets belong under `assets/private/`.
- `assets/private/` is ignored by Git and must not be included in public commits.
- Default Release packages must not include private assets.
- The MIT License covers repository code and documentation only. It does not grant rights to third-party assets or user-provided material.

## User Asset Rules

- Users are responsible for confirming they have the right to use any assets they place in `assets/private/`.
- Recommended action image format: transparent PNG.
- Keep the same canvas size inside one action group.
- Keep the character center point aligned inside one action group.
- Missing private action frames must fall back to placeholder or base idle/talk frames.

## Suggested Layout

```text
assets/private/daniya_summer/normal1.png
assets/private/daniya_summer/normal2.png
assets/private/daniya_summer/app.ico
assets/private/daniya_summer/idle/
assets/private/daniya_summer/talk/
assets/private/daniya_summer/clicked/
assets/private/daniya_summer/drag/
assets/private/daniya_summer/sleep/
assets/private/daniya_summer/happy/
assets/private/daniya_summer/remind/
```

Do not commit `assets/private/`.
