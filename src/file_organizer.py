from __future__ import annotations

import ctypes
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Categories mapping
EXT_MAPPING = {
    # images
    ".png": "images", ".jpg": "images", ".jpeg": "images", ".gif": "images", ".webp": "images", ".svg": "images",
    # documents
    ".pdf": "documents", ".docx": "documents", ".txt": "documents", ".md": "documents", ".xlsx": "documents", ".pptx": "documents",
    # archives
    ".zip": "archives", ".rar": "archives", ".7z": "archives",
    # code
    ".py": "code", ".js": "code", ".ts": "code", ".html": "code", ".css": "code", ".json": "code", ".yaml": "code", ".yml": "code",
    # audio
    ".mp3": "audio", ".wav": "audio", ".flac": "audio",
    # video
    ".mp4": "video", ".mov": "video", ".mkv": "video"
}

@dataclass
class FileMoveItem:
    src_path: str
    dst_path: str
    filename: str
    category: str
    status: str = "pending"  # pending, success, failed, skipped
    error_message: str = ""

@dataclass
class FileOrganizerPlan:
    ok: bool
    source_dir: str
    target_dir: str
    moves: list[FileMoveItem]
    skipped: list[tuple[str, str]]  # list of (filepath, reason)
    reason: str = ""

class FileOrganizer:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir
        if self.data_dir:
            self.data_dir.mkdir(parents=True, exist_ok=True)

    def is_sensitive_path(self, path: Path) -> bool:
        # Check folders
        parts = {part.lower() for part in path.parts}
        forbidden_dirs = {".git", ".venv", "venv", "models", "backups", "dist", "build", "release", "data"}
        if parts & forbidden_dirs:
            return True
        lowered = [part.lower() for part in path.parts]
        if any(lowered[i] == "assets" and lowered[i + 1] == "private" for i in range(len(lowered) - 1)):
            return True
        # Check files
        name = path.name.lower()
        if path.as_posix().lower().endswith(("config/api_config.json", "config/multimodal_config.json")):
            return True
        if any(marker in name for marker in ("sk-", "api_key", ".env", "secret", "password", "token", "credentials")):
            return True
        return False

    def is_hidden_path(self, path: Path) -> bool:
        # Starts with '.'
        if any(p.startswith(".") for p in path.parts):
            return True
        # Windows hidden attribute check
        try:
            if os.name == "nt":
                get_attributes = ctypes.windll.kernel32.GetFileAttributesW
                get_attributes.argtypes = [ctypes.c_wchar_p]
                get_attributes.restype = ctypes.c_uint32
                attrs = get_attributes(str(path))
                if attrs != 0xFFFFFFFF and attrs & 0x2:
                    return True
        except Exception:
            pass
        return False

    def generate_plan(self, source_dir: str, target_dir: str) -> FileOrganizerPlan:
        src = Path(source_dir).resolve()
        dst = Path(target_dir).resolve()

        if not src.exists() or not src.is_dir():
            return FileOrganizerPlan(False, source_dir, target_dir, [], [], "源目录不存在或不是文件夹")
        if not dst.exists() or not dst.is_dir():
            return FileOrganizerPlan(False, source_dir, target_dir, [], [], "目标目录不存在或不是文件夹")

        if src == dst:
            return FileOrganizerPlan(False, source_dir, target_dir, [], [], "源目录和目标目录不能相同")

        # Destination shouldn't be inside source folder (avoid infinite loops/cycles)
        if src in dst.parents:
            return FileOrganizerPlan(False, source_dir, target_dir, [], [], "目标目录不能是源目录的子目录")

        moves: list[FileMoveItem] = []
        skipped: list[tuple[str, str]] = []

        for root, dirs, files in os.walk(src):
            # Prune dirs in walk to skip forbidden directories
            pruned_dirs = []
            for d in dirs:
                d_path = Path(root) / d
                if self.is_sensitive_path(d_path):
                    skipped.append((str(d_path), "敏感目录跳过"))
                    continue
                if self.is_hidden_path(d_path):
                    skipped.append((str(d_path), "隐藏目录跳过"))
                    continue
                pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for f in files:
                f_path = Path(root) / f
                if self.is_sensitive_path(f_path):
                    skipped.append((str(f_path), "敏感文件跳过"))
                    continue
                if self.is_hidden_path(f_path):
                    skipped.append((str(f_path), "隐藏文件跳过"))
                    continue

                # Classify by extension
                ext = f_path.suffix.lower()
                category = EXT_MAPPING.get(ext, "others")

                # Resolve target filename collision
                target_category_dir = dst / category
                target_file_path = target_category_dir / f
                
                # Check for collision and rename (e.g., file_1.txt)
                count = 1
                base_name = f_path.stem
                while target_file_path.exists():
                    target_file_path = target_category_dir / f"{base_name}_{count}{ext}"
                    count += 1

                moves.append(FileMoveItem(
                    src_path=str(f_path),
                    dst_path=str(target_file_path),
                    filename=target_file_path.name,
                    category=category
                ))

        return FileOrganizerPlan(True, source_dir, target_dir, moves, skipped)

    def execute_plan(self, plan: FileOrganizerPlan) -> list[dict[str, Any]]:
        results = []
        if not plan.ok:
            return []

        for move in plan.moves:
            src = Path(move.src_path)
            dst = Path(move.dst_path)

            if not src.exists():
                move.status = "failed"
                move.error_message = "源文件已不存在"
                results.append(self._move_item_to_dict(move))
                continue

            try:
                # Ensure destination folder category exists
                dst.parent.mkdir(parents=True, exist_ok=True)
                # Move file
                shutil.move(str(src), str(dst))
                move.status = "success"
            except Exception as e:
                move.status = "failed"
                move.error_message = str(e)

            results.append(self._move_item_to_dict(move))

        # Write to move_log
        if self.data_dir:
            log_path = self.data_dir / "move_log.json"
            self._save_log(log_path, results)

        return results

    def generate_restore_plan_from_log(self, log_data: list[dict[str, Any]]) -> FileOrganizerPlan:
        # Create plan to move files back to their original src_path
        moves = []
        for item in log_data:
            if item.get("status") == "success":
                src = item["dst_path"]  # Currently at dst_path
                dst = item["src_path"]  # Original src_path
                
                # Deal with collisions when moving back
                dst_p = Path(dst)
                count = 1
                while dst_p.exists():
                    ext = dst_p.suffix
                    base = dst_p.stem
                    dst_p = dst_p.parent / f"{base}_{count}{ext}"
                    count += 1

                moves.append(FileMoveItem(
                    src_path=src,
                    dst_path=str(dst_p),
                    filename=dst_p.name,
                    category=item["category"]
                ))
        # Swap source and target context
        return FileOrganizerPlan(ok=True, source_dir="", target_dir="", moves=moves, skipped=[])

    def _move_item_to_dict(self, item: FileMoveItem) -> dict[str, Any]:
        return {
            "src_path": item.src_path,
            "dst_path": item.dst_path,
            "filename": item.filename,
            "category": item.category,
            "status": item.status,
            "error_message": item.error_message
        }

    def _save_log(self, path: Path, results: list[dict[str, Any]]) -> None:
        try:
            path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
