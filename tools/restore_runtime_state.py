from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

MANIFEST_NAME = "BACKUP_MANIFEST.json"
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


def copy_existing(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def preserve_current(destination: Path, pre_restore_root: Path, relative: str) -> bool:
    if not destination.exists():
        return False
    preserved = pre_restore_root / relative
    if preserved.exists():
        raise FileExistsError(f"Pre-restore target already exists: {preserved}")
    copy_existing(destination, preserved)
    return True


def restore_target(source: Path, destination: Path) -> None:
    if source.is_dir():
        for item in source.rglob("*"):
            if not item.is_file():
                continue
            target = destination / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore ignored runtime state after destructive tests.")
    parser.add_argument("--project-root", type=Path, default=project_root())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("backup_dir", type=Path, help="Explicit backup directory created by backup_runtime_state.py")
    args = parser.parse_args()

    root = args.project_root.resolve()
    backup_dir = args.backup_dir.resolve()
    manifest_path = backup_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_restore_root = root / "backups" / f"pre_restore_{timestamp}"
    restored: list[str] = []
    preserved_any = False

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

        if not source.exists():
            continue
        preserved_any = preserve_current(destination, pre_restore_root, relative) or preserved_any
        restore_target(source, destination)
        restored.append(relative)

    if args.dry_run:
        print(json.dumps({"backup_dir": str(backup_dir), "would_restore": restored}, ensure_ascii=False, indent=2))
        return 0

    print(f"Runtime state restored from: {backup_dir}")
    print(f"Pre-restore copy, if any: {pre_restore_root if preserved_any else 'none'}")
    print("Restored targets: " + ", ".join(restored))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
