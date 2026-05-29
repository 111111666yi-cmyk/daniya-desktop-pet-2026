import pytest


@pytest.fixture(autouse=True)
def isolated_relation_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "daniya_relation"))

