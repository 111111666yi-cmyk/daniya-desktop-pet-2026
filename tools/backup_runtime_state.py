from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

DEFAULT_TARGETS = (
    "data",
    ".env",
    "config/api_config.json",
    "config/multimodal_config.json",
    "assets/private",
    "models",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_inside(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError(f"Refusing path outside project root: {relative_path}")
    return target


def copy_target(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
        return "dir"
    shutil.copy2(source, destination)
    return "file"


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up ignored runtime state before destructive tests.")
    parser.add_argument("--project-root", type=Path, default=project_root())
    parser.add_argument("--backup-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("targets", nargs="*", default=list(DEFAULT_TARGETS))
    args = parser.parse_args()

    root = args.project_root.resolve()
    backup_root = (args.backup_root or root / "backups" / "runtime_state").resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / timestamp

    manifest: dict[str, object] = {
        "created_at": timestamp,
        "project_root": str(root),
        "targets": [],
    }

    for relative in args.targets:
        normalized = relative.replace("\\", "/").strip("/")
        source = resolve_inside(root, normalized)
        entry: dict[str, object] = {"path": normalized, "exists": source.exists()}
        if source.exists():
            entry["kind"] = "dir" if source.is_dir() else "file"
            entry["backup_path"] = normalized
            if not args.dry_run:
                copy_target(source, backup_dir / normalized)
        manifest["targets"].append(entry)

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Runtime state backup created: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
