import pytest
from src.action_manifest import ActionManifest

def test_load_manifest_defaults():
    manifest = ActionManifest()
    assert "idle" in manifest.available_actions()
    frames = manifest.get_frames("idle")
    assert len(frames) > 0

def test_fallback_frames():
    manifest = ActionManifest()
    # If frames don't exist, we fallback. But wait, in test environment, normal1.png might not exist either.
    # The _verify_frames checks if path exists.
    assert manifest.resolve_action("unknown") == "idle"
    assert manifest.resolve_action("happy") == "happy"

def test_damaged_manifest(tmp_path, monkeypatch):
    import json
    damaged_file = tmp_path / "manifest.json"
    damaged_file.write_text("{ broken json", encoding="utf-8")
    
    # Mock resource_path to point to our tmp_path
    def mock_resource_path(*args):
        return tmp_path
        
    import src.action_manifest
    monkeypatch.setattr(src.action_manifest, "resource_path", mock_resource_path)
    
    manifest = ActionManifest()
    assert "idle" in manifest.available_actions()
    config = manifest.get_action_config("idle")
    assert config is not None
    assert config["frames"] == ["normal1.png"]
