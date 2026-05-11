"""Helpers for loading manual supplement fields from JSON or brief text files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MULTI_ASSIGNMENT_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|[^,，]+)"
)


def _parse_scalar_value(raw_value: str) -> Any:
    text = raw_value.strip()
    if not text:
        return None

    lower = text.lower()
    if lower in {"null", "none", "na", "n/a"}:
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False

    if text.startswith('"') and text.endswith('"'):
        return json.loads(text)
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]

    try:
        if any(marker in text for marker in (".", "e", "E")):
            return float(text)
        return int(text)
    except ValueError:
        return text


def _parse_assignment_line(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if "=" not in stripped:
        return {}

    if stripped.count("=") == 1:
        key_text, value_text = stripped.split("=", 1)
        key = key_text.strip()
        if _FIELD_NAME_RE.match(key):
            return {key: _parse_scalar_value(value_text)}

    parsed: dict[str, Any] = {}
    for match in _MULTI_ASSIGNMENT_RE.finditer(stripped):
        parsed[match.group("key")] = _parse_scalar_value(match.group("value"))
    return parsed


def parse_manual_supplement_text(text: str) -> dict[str, Any]:
    supplement: dict[str, Any] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith(("- ", "-\t", "* ")):
            continue
        content = stripped[2:].strip()
        supplement.update(_parse_assignment_line(content))
    return supplement


def load_manual_supplement_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")

    if file_path.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError(f"Manual supplement file must contain a JSON object: {file_path}")
        return payload

    return parse_manual_supplement_text(text)