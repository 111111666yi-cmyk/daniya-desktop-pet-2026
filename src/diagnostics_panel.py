from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core.character_loader import validate_character_pack

from .asset_manager import AssetManager
from .settings_manager import SettingsManager
from .utils import runtime_root


def run_diagnostics(
    settings_manager: SettingsManager | None = None,
    asset_manager: AssetManager | None = None,
    chat_client: Any | None = None,
) -> list[dict[str, str]]:
    root = runtime_root()
    settings = settings_manager or SettingsManager(root=root)
    assets = asset_manager or AssetManager({})
    results: list[dict[str, str]] = []

    # LLM Runtime diagnostics
    if chat_client is not None and getattr(chat_client, "provider_manager", None) is not None:
        pm = chat_client.provider_manager
        last_provider = getattr(pm, "last_provider", "无")
        last_model = getattr(pm, "last_model", "无")
        fallback_used = getattr(pm, "fallback_used", False)
        fallback_reason = getattr(pm, "fallback_reason", "无")
        last_error_type = getattr(pm, "last_error_type", "无")
        last_error_traceback = getattr(pm, "last_error_traceback", "无")

        status = "warn" if fallback_used else "pass"
        msg = f"当前/最近云端Provider: {last_provider}, Model: {last_model}, Fallback: {'是' if fallback_used else '否'}, 错误类型: {last_error_type}, 原因: {fallback_reason}\n[堆栈日志]:\n{last_error_traceback}"
        results.append(_item("LLM 运行时状态", status, msg))
    else:
        results.append(_item("LLM 运行时状态", "pass", "未接收到活跃对话客户端，暂无运行时错误记录。"))

    validation = validate_character_pack("daniya")
    results.append(_item("角色包校验", "pass" if validation.ok else "fail", validation.error_summary() or "Character pack OK."))

    api_config = settings.load_api_config()
    active_provider = api_config.get("active_provider", api_config.get("provider", ""))
    provider_conf = api_config.get("providers", {}).get(active_provider, {})
    env_key_name = provider_conf.get("api_key_env", "")
    raw_key = settings.current_api_key(env_key_name)
    results.append(_item(
        "API 配置",
        "pass",
        f"provider={active_provider} model={provider_conf.get('model', api_config.get('model'))} key={provider_conf.get('api_key_masked')}",
    ))
    if raw_key or api_config.get("local_mode"):
        ok, message = settings.test_api_connection(timeout=5)
        results.append(_item("API 测试连接", "pass" if ok else "warn", message))
    else:
        results.append(_item("API 测试连接", "warn", "未配置 API Key，当前会走 fallback。"))

    try:
        manifest = assets.manifest()
        animations = manifest.get("animations", {})
        results.append(_item("manifest 可读", "pass" if isinstance(animations, dict) else "fail", f"actions={len(animations) if isinstance(animations, dict) else 0}"))
        missing = _missing_actions(assets, ["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble"])
        results.append(_item("动作资源", "pass" if not missing else "warn", "missing=" + ",".join(missing) if missing else "all required actions have fallback frames"))
    except Exception as exc:
        results.append(_item("manifest 可读", "fail", exc.__class__.__name__))

    data_dir = root / "data" / "daniya_relation"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        results.append(_item("data/daniya_relation 可写", "pass", str(data_dir)))
    except OSError as exc:
        results.append(_item("data/daniya_relation 可写", "fail", exc.__class__.__name__))

    for path in [".env", "data", "data/daniya_relation", "assets/private", "models", "backups"]:
        ignored = _git_ignored(root, path)
        level = "pass" if ignored else ("warn" if path == "models" and not (root / path).exists() else "fail")
        results.append(_item(f"{path} gitignore", level, "ignored" if ignored else "not ignored"))

    return results


def format_diagnostics(results: list[dict[str, str]]) -> str:
    lines = []
    for item in results:
        lines.append(f"[{item['status'].upper()}] {item['name']}: {item['message']}")
    return "\n".join(lines)


def _item(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


def _missing_actions(asset_manager: AssetManager, actions: list[str]) -> list[str]:
    missing: list[str] = []
    for action in actions:
        frames = asset_manager.frames_for_state(action)
        if not frames or not any(frame.exists() for frame in frames):
            missing.append(action)
    return missing


def _git_ignored(root: Path, path: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", path],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
