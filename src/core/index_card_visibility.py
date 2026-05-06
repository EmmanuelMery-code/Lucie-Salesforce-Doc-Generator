"""User-configurable visibility flags for the index page cards.

The home page (``index.html``) displays a row of summary cards. Some
users want a clean dashboard focused on a couple of figures, others want
the full picture. Rather than hard-code that decision, the application
exposes a simple boolean per card. Defaults are ``True`` so a fresh
``app_settings.json`` keeps the historical behaviour.

The dataclass lives in :mod:`src.core` rather than :mod:`src.ui` so the
HTML renderer (which must not depend on Tk) can consume it directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class IndexCardVisibility:
    """Toggles controlling which summary cards are rendered on the index."""

    show_customization_level: bool = True
    show_score: bool = True
    show_adopt_vs_adapt: bool = True
    show_adopt_adapt_score: bool = True
    show_custom_objects: bool = True
    show_custom_fields: bool = True
    show_flows: bool = True
    show_apex_classes_triggers: bool = True
    show_omni_components: bool = True
    show_findings: bool = True
    show_ai_usage: bool = True
    show_data_model_footprint: bool = True
    show_adopt_adapt_posture: bool = True
    show_agents: bool = True
    show_gen_ai_prompts: bool = True
    show_einstein_predictions: bool = True

    def to_settings(self) -> dict[str, bool]:
        """Return the JSON-friendly mapping persisted in ``app_settings.json``."""

        return {
            "show_card_customization_level": self.show_customization_level,
            "show_card_score": self.show_score,
            "show_card_adopt_vs_adapt": self.show_adopt_vs_adapt,
            "show_card_adopt_adapt_score": self.show_adopt_adapt_score,
            "show_card_custom_objects": self.show_custom_objects,
            "show_card_custom_fields": self.show_custom_fields,
            "show_card_flows": self.show_flows,
            "show_card_apex_classes_triggers": self.show_apex_classes_triggers,
            "show_card_omni_components": self.show_omni_components,
            "show_card_findings": self.show_findings,
            "show_card_ai_usage": self.show_ai_usage,
            "show_card_data_model_footprint": self.show_data_model_footprint,
            "show_card_adopt_adapt_posture": self.show_adopt_adapt_posture,
            "show_card_agents": self.show_agents,
            "show_card_gen_ai_prompts": self.show_gen_ai_prompts,
            "show_card_einstein_predictions": self.show_einstein_predictions,
        }


_SETTING_KEYS: dict[str, str] = {
    "show_customization_level": "show_card_customization_level",
    "show_score": "show_card_score",
    "show_adopt_vs_adapt": "show_card_adopt_vs_adapt",
    "show_adopt_adapt_score": "show_card_adopt_adapt_score",
    "show_custom_objects": "show_card_custom_objects",
    "show_custom_fields": "show_card_custom_fields",
    "show_flows": "show_card_flows",
    "show_apex_classes_triggers": "show_card_apex_classes_triggers",
    "show_omni_components": "show_card_omni_components",
    "show_findings": "show_card_findings",
    "show_ai_usage": "show_card_ai_usage",
    "show_data_model_footprint": "show_card_data_model_footprint",
    "show_adopt_adapt_posture": "show_card_adopt_adapt_posture",
    "show_agents": "show_card_agents",
    "show_gen_ai_prompts": "show_card_gen_ai_prompts",
    "show_einstein_predictions": "show_card_einstein_predictions",
}


def _coerce_bool(value: Any, default: bool) -> bool:
    """Tolerantly convert a settings value into a boolean.

    A hand-edited ``app_settings.json`` may store the flag as a literal
    bool, the strings ``"true"``/``"false"`` (any casing), or as
    ``0``/``1``. Anything unrecognised falls back to ``default`` so a
    typo never silently turns a card off.
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
    return default


def parse_index_card_visibility(
    settings: Mapping[str, Any],
) -> IndexCardVisibility:
    """Read card visibility flags from a parsed ``app_settings.json``."""

    visibility = IndexCardVisibility()
    for attr, key in _SETTING_KEYS.items():
        if key in settings:
            current = getattr(visibility, attr)
            setattr(visibility, attr, _coerce_bool(settings[key], current))
    return visibility


__all__ = [
    "IndexCardVisibility",
    "parse_index_card_visibility",
]
