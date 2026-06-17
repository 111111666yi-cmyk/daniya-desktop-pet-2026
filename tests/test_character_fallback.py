from pathlib import Path

from core.character_loader import discover_character_ids, safe_load_character
from src.asset_manager import AssetManager
from src.action_manifest import ActionManifest

def test_character_config_fallback(tmp_path, monkeypatch):
    # Setup a temp character pack directory with ONLY character.yaml
    char_id = "test_temp_fallback"
    char_dir = tmp_path / "characters" / char_id
    char_dir.mkdir(parents=True)

    # Write only character.yaml
    char_yaml = char_dir / "character.yaml"
    char_yaml.write_text("""
id: test_temp_fallback
display_name: Temporary Fallback Test
core_identity:
  - Line 1
forbidden_behavior:
  - Line 2
""", encoding="utf-8")

    import core.character_loader
    original_path = core.character_loader.character_pack_path

    def mock_character_pack_path(cid, root=None):
        if cid == char_id:
            return tmp_path / "characters" / char_id
        return original_path(cid, root)

    monkeypatch.setattr(core.character_loader, "character_pack_path", mock_character_pack_path)

    # Now load! Since other files like speech.yaml are missing in char_dir,
    # they should fallback to characters/template/speech.yaml etc.
    pack, result = safe_load_character(char_id)
    if not result.ok:
        print("VALIDATION ISSUES:")
        print(result.error_summary())
    assert pack is not None
    assert result.ok
    assert pack.character_id == char_id
    assert pack.character["display_name"] == "Temporary Fallback Test"
    # Verify loaded from template fallback:
    assert "speech_style" in pack.speech
    assert "metrics" in pack.relationship
    assert "events" in pack.events
    assert "action_mapping" in pack.actions
    # Optional lore.md and lore_index.yaml should be empty
    assert pack.lore == ""
    assert pack.lore_index == {"fragments": []}

def test_asset_and_manifest_fallback():
    # Instantiate AssetManager with a non-existent character ID
    config = {}
    manager = AssetManager(config, "non_existent_character_xyz")

    # The active_asset_dir should fallback to template assets
    active_dir = manager.active_asset_dir()
    assert active_dir.exists()
    assert "template" in str(active_dir).lower() or "placeholder" in str(active_dir).lower()

    # Verify image resolving falls back successfully to template or placeholder
    p = manager._resolve_image_ref("normal1.png")
    assert p.exists()

    p2 = manager._resolve_image_ref("non_existent_image.png")
    assert p2.exists() # Should fallback to normal1.png or normal2.png
    assert p2.name in ("normal1.png", "normal2.png")

def test_action_manifest_fallback():
    # If we pass a non-existent dir, ActionManifest should fallback to template or default
    manifest = ActionManifest(Path("not_exist_dir_xyz"))
    assert "idle" in manifest.available_actions()

    frames = manifest.get_frames("idle")
    assert len(frames) > 0
    assert Path(frames[0]).exists()


def test_character_discovery_excludes_internal_test_pack(tmp_path):
    root = tmp_path / "characters"
    for character_id in ("daniya", "template", "test_dummy", ".scratch", "empty"):
        (root / character_id).mkdir(parents=True)
    for character_id in ("daniya", "template", "test_dummy"):
        (root / character_id / "character.yaml").write_text("id: test\n", encoding="utf-8")

    assert discover_character_ids(root) == ["daniya", "template"]
    assert discover_character_ids(root, include_internal=True) == ["daniya", "template", "test_dummy"]
