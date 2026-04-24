from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.analyzer.models import Rule


DEFAULT_RULES_PATH = Path(__file__).with_name("rules.xml")


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() == "true"


def _child(node: ET.Element, tag: str, default: str = "") -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def load_rules(path: str | Path | None = None) -> list[Rule]:
    """Charge le catalogue de regles depuis le XML.

    Les regles ayant enabled=false sont conservees mais ignorees par l'engine.
    """
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    if not rules_path.exists():
        return []

    tree = ET.parse(rules_path)
    root = tree.getroot()

    rules: list[Rule] = []
    for node in root.findall("rule"):
        rule_id = (node.get("id") or "").strip()
        if not rule_id:
            continue
        rules.append(
            Rule(
                id=rule_id,
                enabled=_to_bool(node.get("enabled"), default=True),
                scope=(node.get("scope") or "").strip(),
                category=(node.get("category") or "").strip(),
                subcategory=(node.get("subcategory") or "").strip(),
                severity=(node.get("severity") or "Info").strip(),
                source=(node.get("source") or "").strip(),
                reference=(node.get("reference") or "").strip(),
                title=_child(node, "title"),
                description=_child(node, "description"),
                rationale=_child(node, "rationale"),
                remediation=_child(node, "remediation"),
            )
        )
    return rules


class RuleCatalog:
    """Accesseur centralise aux regles activees / desactivees."""

    def __init__(self, rules: list[Rule]) -> None:
        self._rules = list(rules)
        self._by_id = {rule.id: rule for rule in self._rules}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RuleCatalog":
        return cls(load_rules(path))

    @property
    def all(self) -> list[Rule]:
        return list(self._rules)

    @property
    def enabled(self) -> list[Rule]:
        return [rule for rule in self._rules if rule.enabled]

    def get(self, rule_id: str) -> Rule | None:
        return self._by_id.get(rule_id)

    def is_enabled(self, rule_id: str) -> bool:
        rule = self.get(rule_id)
        return bool(rule and rule.enabled)

    def for_scope(self, scope: str, enabled_only: bool = True) -> list[Rule]:
        return [
            rule
            for rule in self._rules
            if rule.scope == scope and (not enabled_only or rule.enabled)
        ]
