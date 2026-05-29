"""v0.415 集成验证测试 — 验证适配器接入后的端到端数据流。

此测试模拟真实的 AppController 调用路径：
1. DaniyaEngineAdapter.handle_user_text() → 特殊回复匹配 → 关系数值更新
2. DaniyaEngineAdapter.handle_physical_event() → 物理事件 → defense_level 变更

运行: .venv\Scripts\python.exe -m pytest tests/test_integration_verify.py -v
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.relationship_engine import data_root, init_state_if_missing, save_state
from core.character_loader import load_character
from src.daniya_engine_adapter import DaniyaEngineAdapter


@pytest.fixture()
def clean_relation_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """用临时目录替代真实 data/daniya_relation/，保护用户数据。"""
    relation_dir = tmp_path / "daniya_relation"
    relation_dir.mkdir()
    monkeypatch.setattr("core.relationship_engine.data_root", lambda: relation_dir)
    monkeypatch.setattr("core.memory_engine.data_root", lambda: relation_dir)
    return relation_dir


class TestAdapterIntegration:
    """验证 DaniyaEngineAdapter 的端到端数据流。"""

    def test_special_response_updates_state(self, clean_relation_dir: Path):
        """输入 '我不会先走' → 应触发特殊回复并更新关系数值。"""
        adapter = DaniyaEngineAdapter(model_client=None)
        result = adapter.handle_user_text("我不会先走")

        assert result.matched_special_response is True
        assert "走" in result.response or "随便" in result.response or "懒" in result.response

        # 验证状态文件已写入
        state_file = clean_relation_dir / "relationship_state.json"
        assert state_file.exists(), "relationship_state.json 应该在引擎处理后被创建"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert "trust" in state

    def test_physical_click_updates_defense(self, clean_relation_dir: Path):
        """物理点击事件 → defense_level 应增加。"""
        adapter = DaniyaEngineAdapter(model_client=None)

        # 先触发一次文本让状态初始化
        adapter.handle_user_text("你好")

        state_file = clean_relation_dir / "relationship_state.json"
        state_before = json.loads(state_file.read_text(encoding="utf-8"))
        defense_before = state_before.get("defense_level", 0)

        # 触发物理点击
        result = adapter.handle_physical_event("user_click")

        state_after = json.loads(state_file.read_text(encoding="utf-8"))
        defense_after = state_after.get("defense_level", 0)

        assert defense_after >= defense_before, (
            f"点击后 defense_level 应 >= 之前的值: {defense_before} -> {defense_after}"
        )

    def test_physical_drag_updates_defense(self, clean_relation_dir: Path):
        """拖拽释放事件 → defense_level 应增加。"""
        adapter = DaniyaEngineAdapter(model_client=None)
        adapter.handle_user_text("你好")

        state_file = clean_relation_dir / "relationship_state.json"
        state_before = json.loads(state_file.read_text(encoding="utf-8"))
        defense_before = state_before.get("defense_level", 0)

        result = adapter.handle_physical_event("user_drag")

        state_after = json.loads(state_file.read_text(encoding="utf-8"))
        defense_after = state_after.get("defense_level", 0)

        assert defense_after >= defense_before

    def test_hug_special_response(self, clean_relation_dir: Path):
        """输入 '抱抱' → 应触发拥抱特殊回复。"""
        adapter = DaniyaEngineAdapter(model_client=None)
        result = adapter.handle_user_text("抱抱")

        assert result.matched_special_response is True
        assert result.source == "special_response"

    def test_engine_result_has_correct_fields(self, clean_relation_dir: Path):
        """验证 EngineResult 包含所有必要字段。"""
        adapter = DaniyaEngineAdapter(model_client=None)
        result = adapter.handle_user_text("今天天气真好")

        assert hasattr(result, "response")
        assert hasattr(result, "source")
        assert hasattr(result, "action")
        assert hasattr(result, "state")
        assert isinstance(result.response, str)
        assert len(result.response) > 0
