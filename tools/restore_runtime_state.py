from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ALLOWED_TARGETS = {
    "data",
    ".env",
    "config/api_config.json",
    "config/multimodal_config.json",
    "assets/private",
    "models",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_inside(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError(f"Refusing path outside project root: {relative_path}")
    return target


def latest_backup(backup_root: Path) -> Path:
    candidates = [path for path in backup_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    if not candidates:
        raise FileNotFoundError(f"No runtime state backup found under {backup_root}")
    return sorted(candidates)[-1]


def preserve_current(destination: Path, pre_restore_root: Path, relative: str) -> None:
    if not destination.exists():
        return
    preserved = pre_restore_root / relative
    preserved.parent.mkdir(parents=True, exist_ok=True)
    if preserved.exists():
        raise FileExistsError(f"Pre-restore target already exists: {preserved}")
    shutil.move(str(destination), str(preserved))


def restore_target(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore ignored runtime state after destructive tests.")
    parser.add_argument("--project-root", type=Path, default=project_root())
    parser.add_argument("--backup-root", type=Path, default=None)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    backup_root = (args.backup_root or root / "backups" / "runtime_state").resolve()
    backup_dir = args.backup_dir.resolve() if args.backup_dir else latest_backup(backup_root)
    manifest_path = backup_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_restore_root = root / "backups" / "pre_restore" / timestamp
    restored: list[str] = []

    for entry in manifest.get("targets", []):
        relative = str(entry.get("path", "")).replace("\\", "/").strip("/")
        if relative not in ALLOWED_TARGETS:
            raise ValueError(f"Refusing unexpected restore target: {relative}")
        if not entry.get("exists"):
            continue

        source = backup_dir / relative
        destination = resolve_inside(root, relative)
        if args.dry_run:
            restored.append(relative)
            continue

        preserve_current(destination, pre_restore_root, relative)
        restore_target(source, destination)
        restored.append(relative)

    if args.dry_run:
        print(json.dumps({"backup_dir": str(backup_dir), "would_restore": restored}, ensure_ascii=False, indent=2))
        return 0

    print(f"Runtime state restored from: {backup_dir}")
    print(f"Pre-restore copy, if any: {pre_restore_root}")
    print("Restored targets: " + ", ".join(restored))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
