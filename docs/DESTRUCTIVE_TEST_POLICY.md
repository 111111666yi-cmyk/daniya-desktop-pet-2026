# Destructive Test Policy

This policy applies to tests that intentionally simulate missing files, broken
runtime data, broken config files, damaged assets, or package-content failures.

## Paths That Must Not Be Deleted Directly

The following paths can contain user runtime state, secrets, private assets, or
large local model files. Do not delete, empty, or overwrite them directly from a
test script:

- `data/`
- `.env`
- `config/api_config.json`
- `config/multimodal_config.json`
- `assets/private/`
- `models/`

## Required Test Pattern

Use one of these approaches instead:

1. Copy the minimum fixture into a temporary sandbox and test there.
2. Run `python tools/backup_runtime_state.py`, execute the test, then run
   `python tools/restore_runtime_state.py`.
3. For a single file, temporarily rename it and restore it in `finally` or an
   equivalent cleanup path.

If a destructive test is interrupted, the most recent backup under
`backups/runtime_state/` must be enough to restore the workspace. Do not claim
recovery succeeded unless it was verified.

## Tool And Package Rules

- `backups/` must remain ignored by Git.
- `tools/backup_runtime_state.py` and `tools/restore_runtime_state.py` are
  development tools and must not enter release packages.
- `pack.bat` must not copy `tools/` into the release package.
- After packaging, scan for `.env`, `data/`, `assets/private/`, `models/`,
  `backups/`, `config/api_config.json`, and `config/multimodal_config.json`.

## Incident Recording

If a test deletes or overwrites ignored runtime files by mistake, record the
incident in a local ignored note or issue tracker item. The record must state:

- whether Git-tracked files were affected
- whether release package contents were affected
- which local runtime files were affected
- whether the files were restored from backup
- what guard was added to prevent recurrence
