from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CharacterPack:
    character_id: str
    root: Path
    character: dict[str, Any]
    speech: dict[str, Any]
    relationship: dict[str, Any]
    events: dict[str, Any]
    actions: dict[str, Any]
    lore: str
    lore_index: dict[str, Any]

    @property
    def display_name(self) -> str:
        return str(self.character.get("display_name") or self.character_id)


@dataclass(frozen=True)
class ValidationIssue:
    file: str
    path: str
    message: str
    severity: str = "error"

    def format(self) -> str:
        location = self.file if not self.path else f"{self.file}:{self.path}"
        return f"[{self.severity}] {location} - {self.message}"


@dataclass
class ValidationResult:
    character_id: str
    root: Path
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add_error(self, file: str, path: str, message: str) -> None:
        self.issues.append(ValidationIssue(file=file, path=path, message=message))

    def error_summary(self) -> str:
        errors = [issue.format() for issue in self.issues if issue.severity == "error"]
        return "\n".join(errors)


class CharacterPackError(Exception):
    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        message = result.error_summary() or f"Character pack validation failed: {result.character_id}"
        super().__init__(message)


@dataclass
class EngineResult:
    response: str
    action: str = "talk"
    fallback_chain: list[str] = field(default_factory=list)
    action_reason: str | None = None
    action_source: str | None = None
    source: str = "local_fallback"
    matched_special_response: bool = False
    raw_model_response: str | None = None
    filtered: bool = False
    errors: list[str] = field(default_factory=list)
    prompt: str | None = None
    special_response_id: str | None = None
    event_id: str | None = None
    state: dict[str, Any] | None = None
    relationship_effect: dict[str, int] = field(default_factory=dict)
    lore_fragments_used: list[str] = field(default_factory=list)
    match_type: str | None = None
