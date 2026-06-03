from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_no_legacy_yuzhu_title_in_user_visible_text() -> None:
    paths = [
        ROOT / "src" / "behavior" / "idle_behavior.py",
        ROOT / "characters" / "daniya" / "character.yaml",
        ROOT / "characters" / "daniya" / "speech.yaml",
        ROOT / "characters" / "daniya" / "story.yaml",
        ROOT / "characters" / "daniya" / "lore_index.yaml",
        ROOT / "characters" / "daniya" / "lore.md",
        ROOT / "characters" / "daniya" / "prompt_pack.md",
    ]

    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "御主" in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_character_pack_does_not_expose_internal_meta_language() -> None:
    forbidden_terms = [
        "Codex 对接",
        "同人桌宠项目",
        "AI 桌宠",
        "人格图腾",
        "桌宠项目",
        "桌宠工程",
        "桌宠里的",
        "桌宠里属于",
        "工程项目",
        "工程意义",
        "工程化 lore",
        "高阶 lore",
        "剧情模式",
        "工程实现",
        "普通恋爱攻略对象",
        "桌宠人格",
        "桌宠达妮娅",
        "Prompt Pack",
        "System Prompt Fragment",
        "Character Fragment",
        "Reply Rules",
    ]

    targets = [
        ROOT / "characters" / "daniya" / "character.yaml",
        ROOT / "characters" / "daniya" / "speech.yaml",
        ROOT / "characters" / "daniya" / "story.yaml",
        ROOT / "characters" / "daniya" / "lore_index.yaml",
        ROOT / "characters" / "daniya" / "lore.md",
        ROOT / "characters" / "daniya" / "prompt_pack.md",
        ROOT / "characters" / "template" / "story.yaml",
    ]
    offenders = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if path.name == "story.yaml":
            body_lines = [
                line
                for line in text.splitlines()
                if line.startswith("      ") and not line.lstrip().startswith("prompt:")
            ]
            text = "\n".join(body_lines)
        for term in forbidden_terms:
            if term in text:
                offenders.append(f"{path.relative_to(ROOT)}: {term}")

    assert offenders == []


def test_pet_window_does_not_persist_runtime_position_into_public_config() -> None:
    text = (ROOT / "src" / "pet_window.py").read_text(encoding="utf-8")
    controller_text = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert 'window_config["start_x"] = final_pos.x()' not in text
    assert 'window_config["start_y"] = final_pos.y()' not in text
    assert 'self.app_config.setdefault("window", {})["start_x"] = x' not in controller_text
    assert 'self.app_config.setdefault("window", {})["start_y"] = y' not in controller_text
