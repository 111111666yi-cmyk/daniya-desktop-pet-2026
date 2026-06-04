# Known Issues

This page tracks stable, public limitations. Historical audit notes, execution
logs, and version-specific QA reports should stay out of the public docs tree.

## PySide6 6.7.2+ Compatibility

- Level: P2
- Status: Some environments can experience UI instability with
  `PySide6>=6.7.2`.
- Cause: PySide6 6.7+ can be sensitive to DPI and GPU driver combinations.
- Recommendation: Keep the project-tested PySide6 pin unless a compatibility
  pass confirms a newer version.

## Non-standard DPI and Multi-monitor Drag

- Level: P3
- Status: Dual-monitor or non-100% scaling setups can make edge snapping and
  drag detection feel offset.
- Cause: Windows screen coordinates and Qt high-DPI mapping can diverge.
- Recommendation: Use Settings Center thresholds where available, and verify
  drag behavior on the primary monitor before release.

## Sleep/Hibernate Timer Blocking

- Level: P3
- Status: System sleep or hibernate pauses Qt timers.
- Cause: The operating system suspends the Python process while asleep.
- Recommendation: The app should detect missed reminders after wake. Use an
  external system scheduler for hard real-time reminders.

## Local API Key and Privacy Data Storage

- Level: P3
- Status: Local API keys and chat history are stored in plaintext runtime files.
- Cause: The project is designed as a local desktop app with simple setup.
- Recommendation: Keep `.env`, `data/`, and private config files ignored. Do
  not commit real keys, chat history, or relationship data.

## run.bat Uses Detached pythonw.exe

- Level: P4
- Status: `run.bat` is suitable for double-click launch, but not for automated
  exit-code checks.
- Recommendation: Use `python main.py` or a dedicated smoke command for
  CI-style launch checks.

## Local Character Assets in Workspace

- Level: P4
- Status: `characters/daniya/assets/` can exist locally but is ignored by Git
  and excluded from packaging.
- Recommendation: Keep local assets private. Public examples belong under
  `characters/daniya/` metadata and placeholder assets.
