import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import ensure_dir, runtime_root
from .atomic_io import atomic_write_json


class SetupStateManager:
    """
    负责管理首次启动 (First Run) 状态。
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.config_dir = ensure_dir(self.root / "config")
        self.data_dir = ensure_dir(self.root / "data")
        self.legacy_setup_config_path = self.config_dir / "setup_config.json"
        self.setup_config_path = self.data_dir / "setup_config.json"
        self.first_run_done_path = self.data_dir / "first_run_done.json"

    def load_setup_config(self) -> dict[str, Any]:
        """读取当前的 setup_config.json，如果不存在则返回默认空字典。"""
        path = self.setup_config_path if self.setup_config_path.exists() else self.legacy_setup_config_path
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_setup_config(self, config: dict[str, Any]) -> None:
        """保存配置到 setup_config.json。"""
        atomic_write_json(self.setup_config_path, config)

    def load_first_run_done(self) -> dict[str, Any]:
        """读取 canonical 首次启动完成状态，坏文件视为未完成。"""
        if not self.first_run_done_path.exists():
            return {}
        try:
            loaded = json.loads(self.first_run_done_path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save_first_run_done(self, config: dict[str, Any]) -> None:
        atomic_write_json(self.first_run_done_path, config)

    def is_first_run_complete(self) -> bool:
        """判断用户是否已经完成了首次启动向导。"""
        first_run = self.load_first_run_done()
        if first_run.get("completed") is True:
            return True

        legacy = self.load_setup_config()
        if legacy.get("first_run_setup") is True:
            self.mark_first_run_complete(
                run_mode=str(legacy.get("run_mode", "legacy")),
                api_configured=bool(legacy.get("run_mode") == "api_cloud"),
                skipped_api=bool(legacy.get("run_mode") in {"fast", "mock"}),
            )
            return True
        return False

    def mark_first_run_complete(
        self,
        run_mode: str,
        api_configured: bool = False,
        skipped_api: bool = False,
    ) -> None:
        """
        保存完成状态，并记录用户的选择。
        :param run_mode: 运行模式，例如 api_cloud, local_model, local_fallback 等
        """
        payload = {
            "completed": True,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
            "run_mode": run_mode,
            "api_configured": bool(api_configured),
            "skipped_api": bool(skipped_api),
        }
        self.save_first_run_done(payload)

        # Keep the old config flag for compatibility with older checks.
        config = self.load_setup_config()
        config["first_run_setup"] = True
        config["run_mode"] = run_mode
        self.save_setup_config(config)
