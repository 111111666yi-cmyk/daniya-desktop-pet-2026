import pytest
from pathlib import Path
from src.model_catalog import ModelCatalog

def test_load_default_model_catalog():
    # Load default catalog from the project directory
    catalog = ModelCatalog()
    models = catalog.get_recommended_models()
    assert len(models) > 0
    
    # Check that crucial fields are present in every recommended model
    for model in models:
        assert "id" in model
        assert "display_name" in model
        assert "vendor" in model
        assert "estimated_disk_size" in model
        assert "recommended_hardware" in model
        assert "requires_license_confirmation" in model
        assert "license_url" in model
        assert model.get("bundle_weight") is False
        assert model.get("default_download") is False
        
        # Test download methods formatting
        methods = model.get("download_methods", [])
        assert len(methods) > 0
        for method in methods:
            assert "type" in method

def test_get_model_by_id():
    catalog = ModelCatalog()
    qwen = catalog.get_model_by_id("qwen2_5_0_5b_instruct")
    assert qwen is not None
    assert qwen["display_name"] == "Qwen2.5 0.5B Instruct"
    
    non_existent = catalog.get_model_by_id("non_existent_model_123")
    assert non_existent is None

def test_catalog_fallback_on_missing_file(tmp_path):
    catalog = ModelCatalog(root=tmp_path)
    assert catalog.catalog_path.exists() is False
    assert catalog.get_recommended_models() == []
    assert catalog.get_model_by_id("some-id") is None
