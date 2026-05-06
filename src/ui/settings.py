"""Persistent application settings.

This module centralises everything related to ``app_settings.json``:
loading, saving, and parsing the weight maps used by the scoring screens.
Keeping it separate from :class:`src.ui.application.Application` reduces
the size of the UI module and keeps file I/O logic testable in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    CapabilityLevel,
    PostureCapabilityConfig,
    SNAPSHOT_METRIC_KEYS,
)


def load_settings(path: Path) -> dict[str, Any]:
    """Read ``path`` and return the parsed settings dictionary.

    Returns an empty dict when the file does not exist or cannot be parsed.
    Errors are intentionally swallowed: missing/corrupt settings should not
    prevent the application from starting.
    """

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(path: Path, payload: Mapping[str, Any]) -> None:
    """Write ``payload`` to ``path`` as pretty-printed JSON."""

    path.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")


def parse_weights(
    settings: Mapping[str, Any],
    storage_key: str,
    defaults: Mapping[str, int],
) -> dict[str, int]:
    """Return a dict of integer weights merged with ``defaults``.

    The settings file may contain stale or invalid weights (string values,
    booleans, missing keys); this helper sanitises them while preserving the
    user's deliberate choices.
    """

    weights = dict(defaults)
    raw = settings.get(storage_key)
    if not isinstance(raw, dict):
        return weights

    for key in defaults:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            weights[key] = value
        elif isinstance(value, str):
            text = value.strip()
            if text.lstrip("-").isdigit():
                weights[key] = int(text)
    return weights


def _coerce_int(value: Any) -> int | None:
    """Return ``value`` as an int when it can be parsed, otherwise ``None``.

    Booleans are rejected on purpose: ``True`` would be coerced to ``1`` by
    Python's ``int()`` and silently corrupt threshold values stored as JSON.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


DEFAULT_AI_USAGE_TAGS: tuple[str, ...] = ("@IAgenerated", "@IAassisted")


def parse_ai_tags(
    settings: Mapping[str, Any],
    storage_key: str = "ai_usage_tags",
    defaults: tuple[str, ...] = DEFAULT_AI_USAGE_TAGS,
) -> list[str]:
    """Return a clean, de-duplicated list of AI usage tags.

    The settings file may contain a list of strings, missing values, or
    invalid types (numbers, dicts) sneaked in by hand-edits. This helper
    normalises everything to a non-empty list of stripped strings while
    preserving the order chosen by the user. Falls back to ``defaults``
    when no usable value is found.
    """

    raw = settings.get(storage_key)
    if not isinstance(raw, list):
        return list(defaults)

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)

    if not cleaned:
        return list(defaults)
    return cleaned


_POSTURE_STORAGE_KEY = "posture_adopt_adapt"
_POSTURE_DEFAULT_WEIGHTS: dict[str, int] = {
    d.capability_id: d.weight for d in CAPABILITY_CATALOG
}


def _coerce_capability_level(value: Any) -> CapabilityLevel | None:
    """Return the matching :class:`CapabilityLevel` or ``None``.

    Accepts both the localised value (``"Adopt (OOTB)"``) and the enum
    name (``"ADOPT"``) so settings hand-edited or written by older
    versions of the app keep loading.
    """

    if isinstance(value, CapabilityLevel):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for level in CapabilityLevel:
        if level.value == text or level.name.casefold() == text.casefold():
            return level
    return None


def default_posture_config() -> list[PostureCapabilityConfig]:
    """Return the default posture configuration mirroring the catalogue.

    Each builtin capability gets an entry with ``level=None`` so the
    heuristic assessor drives the result until the user overrides it.
    """

    return [
        PostureCapabilityConfig(
            capability_id=definition.capability_id,
            label=definition.label,
            weight=definition.weight,
            level=None,
            custom=False,
        )
        for definition in CAPABILITY_CATALOG
    ]


def parse_posture_config(
    settings: Mapping[str, Any],
    storage_key: str = _POSTURE_STORAGE_KEY,
) -> list[PostureCapabilityConfig]:
    """Read the posture configuration from ``settings``.

    Falls back to :func:`default_posture_config` whenever the payload is
    missing, malformed or empty. Unknown ``capability_id`` values are
    kept only when ``custom`` is ``True`` so a stale builtin reference
    cannot accidentally hide one of the real capabilities.
    """

    raw = settings.get(storage_key)
    if not isinstance(raw, dict):
        return default_posture_config()

    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return default_posture_config()

    builtin_ids = {d.capability_id for d in CAPABILITY_CATALOG}
    parsed: list[PostureCapabilityConfig] = []
    seen_ids: set[str] = set()

    for entry in capabilities:
        if not isinstance(entry, dict):
            continue
        capability_id = str(entry.get("capability_id") or "").strip()
        if not capability_id or capability_id in seen_ids:
            continue
        custom = bool(entry.get("custom"))
        if not custom and capability_id not in builtin_ids:
            continue
        weight = _coerce_int(entry.get("weight"))
        if weight is None or weight < 0:
            weight = _POSTURE_DEFAULT_WEIGHTS.get(capability_id, 1)
        label = str(entry.get("label") or "").strip()
        if not label:
            for definition in CAPABILITY_CATALOG:
                if definition.capability_id == capability_id:
                    label = definition.label
                    break
            if not label:
                label = capability_id
        metadata_key = str(entry.get("metadata_key") or "").strip()
        if metadata_key and metadata_key not in SNAPSHOT_METRIC_KEYS:
            metadata_key = ""
        level = _coerce_capability_level(entry.get("level"))
        parsed.append(
            PostureCapabilityConfig(
                capability_id=capability_id,
                label=label,
                weight=weight,
                level=level,
                custom=custom,
                metadata_key=metadata_key,
            )
        )
        seen_ids.add(capability_id)

    if not parsed:
        return default_posture_config()

    # Make sure every builtin capability has an entry so the configuration
    # screen can always toggle them, even if the saved file dropped one.
    for definition in CAPABILITY_CATALOG:
        if definition.capability_id in seen_ids:
            continue
        parsed.append(
            PostureCapabilityConfig(
                capability_id=definition.capability_id,
                label=definition.label,
                weight=definition.weight,
                level=None,
                custom=False,
            )
        )
    return parsed


def serialize_posture_config(
    config: list[PostureCapabilityConfig],
) -> dict[str, Any]:
    """Return the JSON-friendly payload for ``config``.

    Stored under the ``posture_adopt_adapt`` key. ``level`` is serialised
    as the localised value when set; ``None`` becomes ``null`` so the
    heuristic assessor wins on the next load.
    """

    return {
        "capabilities": [
            {
                "capability_id": entry.capability_id,
                "label": entry.label,
                "weight": int(entry.weight),
                "level": entry.level.value if entry.level is not None else None,
                "custom": bool(entry.custom),
                "metadata_key": entry.metadata_key,
            }
            for entry in config
        ]
    }


def parse_thresholds(
    settings: Mapping[str, Any],
    storage_key: str,
    defaults: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Return a 3-tuple of monotonically increasing thresholds.

    The settings payload may contain a list, a dict (``{"low", "medium",
    "high"}``) or be missing entirely. Invalid entries fall back to
    ``defaults``; the result is always sorted to keep the level ladder
    well-formed even if the user manually edited ``app_settings.json``.
    """

    raw = settings.get(storage_key)
    values: list[int] = list(defaults)

    if isinstance(raw, list):
        for index, candidate in enumerate(raw[:3]):
            parsed = _coerce_int(candidate)
            if parsed is not None:
                values[index] = parsed
    elif isinstance(raw, dict):
        for index, key in enumerate(("low", "medium", "high")):
            if key in raw:
                parsed = _coerce_int(raw[key])
                if parsed is not None:
                    values[index] = parsed

    sorted_values = sorted(values)
    return (sorted_values[0], sorted_values[1], sorted_values[2])
