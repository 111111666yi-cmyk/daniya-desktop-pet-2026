from src.setup_state_manager import SetupStateManager


def test_setup_state_manager(tmp_path):
    manager = SetupStateManager(root=tmp_path)

    assert not manager.is_first_run_complete()

    manager.mark_first_run_complete("api_cloud", api_configured=True)

    assert manager.is_first_run_complete()
    first_run = manager.load_first_run_done()
    assert first_run["completed"] is True
    assert first_run["run_mode"] == "api_cloud"
    assert first_run["api_configured"] is True
    config = manager.load_setup_config()
    assert config["first_run_setup"] is True
    assert config["run_mode"] == "api_cloud"


def test_setup_state_migrates_legacy_config(tmp_path):
    manager = SetupStateManager(root=tmp_path)
    manager.save_setup_config({"first_run_setup": True, "run_mode": "fast"})

    assert manager.is_first_run_complete()
    first_run = manager.load_first_run_done()
    assert first_run["completed"] is True
    assert first_run["run_mode"] == "fast"
    assert first_run["skipped_api"] is True


def test_setup_state_bad_first_run_file_is_not_complete(tmp_path):
    manager = SetupStateManager(root=tmp_path)
    manager.first_run_done_path.write_text("{bad json", encoding="utf-8")

    assert not manager.is_first_run_complete()
