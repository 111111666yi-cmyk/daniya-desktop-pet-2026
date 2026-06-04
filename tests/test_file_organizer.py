from __future__ import annotations

import os
from pathlib import Path
from src.file_organizer import FileOrganizer

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
