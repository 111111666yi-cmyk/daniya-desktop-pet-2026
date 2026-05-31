from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.schema import CharacterPack, CharacterPackError, ValidationResult
from src.utils import bundled_root, runtime_root


def default_character_root() -> Path:
    external = runtime_root() / "characters"
    if external.exists():
        return external
    return bundled_root() / "characters"

REQUIRED_YAML_FILES = {
    "character.yaml": "character",
    "speech.yaml": "speech",
    "relationship.yaml": "relationship",
    "events.yaml": "events",
    "actions.yaml": "actions",
}



def character_pack_path(character_id: str = "daniya", root: Path | None = None) -> Path:
    if root:
        return root / character_id
    external = runtime_root() / "characters" / character_id
    if external.exists():
        return external
    return bundled_root() / "characters" / character_id


def load_character(character_id: str = "daniya", root: Path | None = None) -> CharacterPack:
    data, lore, result = _read_pack(character_id, root)
    _validate_pack_data(data, lore, result)
    if not result.ok:
        raise CharacterPackError(result)
    return _build_pack(character_id, result.root, data, lore)


def safe_load_character(character_id: str = "daniya", root: Path | None = None) -> tuple[CharacterPack | None, ValidationResult]:
    data, lore, result = _read_pack(character_id, root)
    _validate_pack_data(data, lore, result)
    if not result.ok:
        return None, result
    return _build_pack(character_id, result.root, data, lore), result


def validate_character_pack(character_id: str = "daniya", root: Path | None = None) -> ValidationResult:
    data, lore, result = _read_pack(character_id, root)
    _validate_pack_data(data, lore, result)
    return result


def _build_pack(character_id: str, root: Path, data: dict[str, dict[str, Any]], lore: str) -> CharacterPack:
    return CharacterPack(
        character_id=character_id,
        root=root,
        character=data["character"],
        speech=data["speech"],
        relationship=data["relationship"],
        events=data["events"],
        actions=data["actions"],
        lore=lore,
        lore_index=data["lore_index"],
    )


def _read_yaml_with_fallback(
    base: Path,
    file_name: str,
    root: Path | None,
    result: ValidationResult,
    character_id: str,
) -> dict[str, Any]:
    path = base / file_name
    if path.exists():
        return _read_yaml(path, file_name, result)
    if character_id != "template":
        template_base = character_pack_path("template", root)
        template_path = template_base / file_name
        if template_path.exists():
            return _read_yaml(template_path, file_name, result)
    result.add_error(file_name, "", "Required file is missing and template fallback failed.")
    return {}


def _read_pack(
    character_id: str,
    root: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], str, ValidationResult]:
    base = character_pack_path(character_id, root)
    result = ValidationResult(character_id=character_id, root=base)
    data: dict[str, dict[str, Any]] = {}

    if not base.exists():
        result.add_error("<pack>", "", f"Character pack directory not found: {base}")
        return data, "", result

    for file_name, key in REQUIRED_YAML_FILES.items():
        data[key] = _read_yaml_with_fallback(base, file_name, root, result, character_id)

    # Optional lore.md
    lore_path = base / "lore.md"
    if lore_path.exists():
        lore = _read_text(lore_path, "lore.md", result)
    else:
        lore = ""

    # Optional lore_index.yaml
    lore_index_path = base / "lore_index.yaml"
    if lore_index_path.exists():
        data["lore_index"] = _read_yaml(lore_index_path, "lore_index.yaml", result)
    else:
        data["lore_index"] = {"fragments": []}

    return data, lore, result


def _read_yaml(path: Path, file_name: str, result: ValidationResult) -> dict[str, Any]:
    if not path.exists():
        result.add_error(file_name, "", "Required file is missing.")
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result.add_error(file_name, "", f"YAML parse failed: {exc.__class__.__name__}.")
        return {}
    except OSError as exc:
        result.add_error(file_name, "", f"Could not read file: {exc}.")
        return {}
    if not isinstance(loaded, dict):
        result.add_error(file_name, "", "File must contain a YAML mapping.")
        return {}
    return loaded


def _read_text(path: Path, file_name: str, result: ValidationResult) -> str:
    if not path.exists():
        result.add_error(file_name, "", "Required file is missing.")
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.add_error(file_name, "", f"Could not read file: {exc}.")
        return ""
    if not text.strip():
        result.add_error(file_name, "", "File must not be empty.")
    return text


def _validate_pack_data(data: dict[str, dict[str, Any]], lore: str, result: ValidationResult) -> None:
    character = data.get("character", {})
    speech = data.get("speech", {})
    relationship = data.get("relationship", {})
    events = data.get("events", {})
    actions = data.get("actions", {})
    lore_index = data.get("lore_index", {})

    _require_keys(character, "character.yaml", "", ["id", "display_name", "core_identity", "forbidden_behavior"], result)
    _require_list(character, "character.yaml", "core_identity", result)
    _require_list(character, "character.yaml", "forbidden_behavior", result)

    _require_keys(speech, "speech.yaml", "", ["speech_style", "forbidden_style", "special_responses"], result)
    _require_list(speech, "speech.yaml", "forbidden_style", result)
    _require_list(speech, "speech.yaml", "special_responses", result)

    _require_keys(relationship, "relationship.yaml", "", ["metrics", "initial_state", "relationship_stages"], result)
    _require_mapping(relationship, "relationship.yaml", "metrics", result)
    _require_mapping(relationship, "relationship.yaml", "initial_state", result)
    _require_list(relationship, "relationship.yaml", "relationship_stages", result)

    _require_list(events, "events.yaml", "events", result)
    for index, event in enumerate(events.get("events", []) if isinstance(events.get("events"), list) else []):
        path = f"events[{index}]"
        if not isinstance(event, dict):
            result.add_error("events.yaml", path, "Event must be a mapping.")
            continue
        _require_keys(event, "events.yaml", path, ["id", "triggers"], result)
        if not isinstance(event.get("triggers"), list) or not event.get("triggers"):
            result.add_error("events.yaml", f"{path}.triggers", "Field must be a non-empty list.")

    _require_mapping(actions, "actions.yaml", "action_mapping", result)
    action_mapping = actions.get("action_mapping", {})
    if isinstance(action_mapping, dict):
        for action_name, action in action_mapping.items():
            path = f"action_mapping.{action_name}"
            if not isinstance(action, dict):
                result.add_error("actions.yaml", path, "Action must be a mapping.")
                continue
            _require_keys(action, "actions.yaml", path, ["fallback"], result)

    if (result.root / "lore_index.yaml").exists():
        _require_list(lore_index, "lore_index.yaml", "fragments", result)
        for index, fragment in enumerate(lore_index.get("fragments", []) if isinstance(lore_index.get("fragments"), list) else []):
            path = f"fragments[{index}]"
            if not isinstance(fragment, dict):
                result.add_error("lore_index.yaml", path, "Fragment must be a mapping.")
                continue
            _require_keys(fragment, "lore_index.yaml", path, ["id", "keywords", "level"], result)
            if not isinstance(fragment.get("keywords"), list) or not fragment.get("keywords"):
                result.add_error("lore_index.yaml", f"{path}.keywords", "Field must be a non-empty list.")


def _require_keys(
    mapping: dict[str, Any],
    file_name: str,
    path: str,
    keys: list[str],
    result: ValidationResult,
) -> None:
    for key in keys:
        if key not in mapping or mapping.get(key) in (None, ""):
            dotted = f"{path}.{key}" if path else key
            result.add_error(file_name, dotted, "Required field is missing.")


def _require_list(mapping: dict[str, Any], file_name: str, key: str, result: ValidationResult) -> None:
    value = _value_at_path(mapping, key)
    if not isinstance(value, list) or not value:
        result.add_error(file_name, key, "Field must be a non-empty list.")


def _require_mapping(mapping: dict[str, Any], file_name: str, key: str, result: ValidationResult) -> None:
    value = _value_at_path(mapping, key)
    if not isinstance(value, dict) or not value:
        result.add_error(file_name, key, "Field must be a non-empty mapping.")


def _value_at_path(mapping: dict[str, Any], path: str) -> Any:
    current: Any = mapping
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
