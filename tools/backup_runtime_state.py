from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

MANIFEST_NAME = "BACKUP_MANIFEST.json"
MODEL_METADATA_MAX_BYTES = 5 * 1024 * 1024
MODEL_BODY_EXTENSIONS = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".ggml",
    ".model",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
    ".tflite",
}

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


def should_copy_model_metadata(path: Path) -> tuple[bool, str]:
    if path.suffix.lower() in MODEL_BODY_EXTENSIONS:
        return False, "model-body-extension"
    try:
        if path.stat().st_size > MODEL_METADATA_MAX_BYTES:
            return False, "larger-than-metadata-limit"
    except OSError:
        return False, "stat-failed"
    return True, "metadata"


def copy_models_metadata(source: Path, destination: Path) -> tuple[int, list[dict[str, str]]]:
    copied = 0
    skipped: list[dict[str, str]] = []
    if source.is_file():
        should_copy, reason = should_copy_model_metadata(source)
        if should_copy:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return 1, skipped
        skipped.append({"path": source.name, "reason": reason})
        return 0, skipped

    for file_path in source.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(source)
        should_copy, reason = should_copy_model_metadata(file_path)
        if not should_copy:
            skipped.append({"path": relative.as_posix(), "reason": reason})
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        copied += 1
    return copied, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up ignored runtime state before destructive tests.")
    parser.add_argument("--project-root", type=Path, default=project_root())
    parser.add_argument("--backup-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("targets", nargs="*", default=list(DEFAULT_TARGETS))
    args = parser.parse_args()

    root = args.project_root.resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = (args.backup_root or root / "backups").resolve()
    backup_dir = backup_root / f"runtime_backup_{timestamp}"

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
            if normalized == "models":
                if args.dry_run:
                    entry["models_policy"] = "metadata-only"
                else:
                    copied, skipped = copy_models_metadata(source, backup_dir / normalized)
                    entry["models_policy"] = "metadata-only"
                    entry["copied_files"] = copied
                    entry["skipped_files"] = skipped
            elif not args.dry_run:
                copy_target(source, backup_dir / normalized)
        manifest["targets"].append(entry)

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Runtime state backup created: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
