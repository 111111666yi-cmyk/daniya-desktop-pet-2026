from __future__ import annotations

import ctypes
import os
from pathlib import Path
from src.file_organizer import FileMoveItem, FileOrganizer, FileOrganizerPlan

def test_file_organizer_safety_checks(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path)

    # 1. Non-existent source
    plan = organizer.generate_plan(str(tmp_path / "missing_src"), str(tmp_path))
    assert not plan.ok
    assert "不存在" in plan.reason

    # 2. Non-existent target
    plan2 = organizer.generate_plan(str(tmp_path), str(tmp_path / "missing_dst"))
    assert not plan2.ok
    assert "不存在" in plan2.reason

    # 3. Source and target identical
    plan3 = organizer.generate_plan(str(tmp_path), str(tmp_path))
    assert not plan3.ok
    assert "相同" in plan3.reason

    # 4. Target is inside source
    src = tmp_path / "src_folder"
    dst = src / "dst_folder"
    src.mkdir()
    dst.mkdir()
    plan4 = organizer.generate_plan(str(src), str(dst))
    assert not plan4.ok
    assert "子目录" in plan4.reason

    assert organizer.is_sensitive_path(Path("assets") / "private" / "secret.png")
    assert organizer.is_sensitive_path(Path("config") / "api_config.json")
    assert organizer.is_sensitive_path(Path("config") / "multimodal_config.json")


def test_file_organizer_detects_windows_hidden_attribute(tmp_path) -> None:
    if os.name != "nt":
        return

    hidden_file = tmp_path / "hidden-by-attribute.txt"
    hidden_file.write_text("private", encoding="utf-8")
    kernel32 = ctypes.windll.kernel32
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = ctypes.c_uint32
    set_attributes = kernel32.SetFileAttributesW
    set_attributes.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    set_attributes.restype = ctypes.c_int
    original = get_attributes(str(hidden_file))
    assert original != 0xFFFFFFFF
    assert set_attributes(str(hidden_file), original | 0x2)
    try:
        assert FileOrganizer(data_dir=tmp_path).is_hidden_path(hidden_file)
    finally:
        assert set_attributes(str(hidden_file), original)


def test_file_organizer_classification_and_execution(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path)

    src = tmp_path / "source"
    dst = tmp_path / "target"
    src.mkdir()
    dst.mkdir()

    # Create dummy files
    (src / "test1.png").write_text("image content", encoding="utf-8")
    (src / "test2.txt").write_text("doc content", encoding="utf-8")
    (src / "test3.zip").write_text("archive content", encoding="utf-8")
    (src / "test_unknown.xyz").write_text("others content", encoding="utf-8")
    # Sensitive file
    (src / "my_secret_sk-123.txt").write_text("key content", encoding="utf-8")
    # Hidden folder files (e.g. .git/something)
    git_dir = src / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("git config", encoding="utf-8")

    # Generate plan (dry-run)
    plan = organizer.generate_plan(str(src), str(dst))
    assert plan.ok
    assert len(plan.moves) == 4  # test1, test2, test3, test_unknown
    assert len(plan.skipped) >= 1  # my_secret_sk-123.txt is skipped, .git is pruned out

    # Verify no files were moved yet (dry-run concept)
    assert (src / "test1.png").exists()
    assert not (dst / "images" / "test1.png").exists()

    # Execute plan
    results = organizer.execute_plan(plan)
    assert len(results) == 4
    assert all(r["status"] == "success" for r in results)

    # Verify moves
    assert not (src / "test1.png").exists()
    assert (dst / "images" / "test1.png").exists()
    assert (dst / "documents" / "test2.txt").exists()
    assert (dst / "archives" / "test3.zip").exists()
    assert (dst / "others" / "test_unknown.xyz").exists()
    assert (src / "my_secret_sk-123.txt").exists()  # Kept!

    # Verify move_log.json exists
    log_file = tmp_path / "move_log.json"
    assert log_file.exists()

    # Test Restore
    restore_plan = organizer.generate_restore_plan_from_log(results)
    assert restore_plan.ok
    assert len(restore_plan.moves) == 4

    # Execute Restore
    restore_results = organizer.execute_plan(restore_plan)
    assert len(restore_results) == 4
    assert all(r["status"] == "success" for r in restore_results)

    # Verify files are back in source
    assert (src / "test1.png").exists()
    assert not (dst / "images" / "test1.png").exists()

def test_file_organizer_collision_protection(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path)
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    # Create collision files in dst
    (dst / "images").mkdir()
    (dst / "images" / "photo.png").write_text("old photo", encoding="utf-8")

    # Create source file
    (src / "photo.png").write_text("new photo", encoding="utf-8")

    plan = organizer.generate_plan(str(src), str(dst))
    assert plan.ok
    assert len(plan.moves) == 1
    # Should rename destination to avoid collision
    assert plan.moves[0].filename == "photo_1.png"

    # Execute
    organizer.execute_plan(plan)
    assert (dst / "images" / "photo.png").read_text(encoding="utf-8") == "old photo"
    assert (dst / "images" / "photo_1.png").read_text(encoding="utf-8") == "new photo"


def test_file_organizer_reserves_duplicate_names_within_preview(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path / "logs")
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "one").mkdir(parents=True)
    (src / "two").mkdir(parents=True)
    dst.mkdir()
    (src / "one" / "same.txt").write_text("one", encoding="utf-8")
    (src / "two" / "same.txt").write_text("two", encoding="utf-8")

    plan = organizer.generate_plan(str(src), str(dst))

    assert plan.ok
    assert sorted(item.filename for item in plan.moves) == ["same.txt", "same_1.txt"]
    results = organizer.execute_plan(plan)
    assert all(item["status"] == "success" for item in results)
    assert {
        (dst / "documents" / "same.txt").read_text(encoding="utf-8"),
        (dst / "documents" / "same_1.txt").read_text(encoding="utf-8"),
    } == {"one", "two"}


def test_file_organizer_does_not_overwrite_file_created_after_preview(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path / "logs")
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "note.txt").write_text("new", encoding="utf-8")

    plan = organizer.generate_plan(str(src), str(dst))
    planned = Path(plan.moves[0].dst_path)
    planned.parent.mkdir(parents=True)
    planned.write_text("existing", encoding="utf-8")

    results = organizer.execute_plan(plan)

    assert results[0]["status"] == "success"
    assert planned.read_text(encoding="utf-8") == "existing"
    assert (planned.parent / "note_1.txt").read_text(encoding="utf-8") == "new"


def test_file_organizer_rejects_sensitive_roots_and_tampered_moves(tmp_path) -> None:
    organizer = FileOrganizer(data_dir=tmp_path / "logs")
    safe_src = tmp_path / "safe"
    safe_dst = tmp_path / "target"
    sensitive_src = tmp_path / "data"
    sensitive_dst = tmp_path / "release"
    for path in (safe_src, safe_dst, sensitive_src, sensitive_dst):
        path.mkdir()

    assert not organizer.generate_plan(str(sensitive_src), str(safe_dst)).ok
    assert not organizer.generate_plan(str(safe_src), str(sensitive_dst)).ok

    secret = sensitive_src / "secret.txt"
    secret.write_text("do not move", encoding="utf-8")
    tampered = FileOrganizerPlan(
        ok=True,
        source_dir=str(sensitive_src),
        target_dir=str(safe_dst),
        moves=[
            FileMoveItem(
                src_path=str(secret),
                dst_path=str(safe_dst / "documents" / "secret.txt"),
                filename="secret.txt",
                category="documents",
            )
        ],
        skipped=[],
    )

    results = organizer.execute_plan(tampered)

    assert results[0]["status"] == "skipped"
    assert secret.exists()
    assert not (safe_dst / "documents" / "secret.txt").exists()
