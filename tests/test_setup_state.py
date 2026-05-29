import json
import pytest
from src.setup_state_manager import SetupStateManager

def test_setup_state_manager(tmp_path):
    manager = SetupStateManager(root=tmp_path)
    
    # 刚开始应该没设置过
    assert not manager.is_first_run_complete()
    
    # 标记完成
    manager.mark_first_run_complete("api_cloud", {"tts": True})
    
    assert manager.is_first_run_complete()
    config = manager.load_setup_config()
    assert config["first_run_setup"] is True
    assert config["run_mode"] == "api_cloud"
    assert config["multimodal_enabled"]["tts"] is True
