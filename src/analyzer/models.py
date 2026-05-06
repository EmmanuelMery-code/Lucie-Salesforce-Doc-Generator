from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


Severity = Literal["Critical", "Major", "Minor", "Info"]
Category = Literal["Trusted", "Easy", "Adaptable"]


SEVERITY_ORDER: dict[str, int] = {
    "Critical": 0,
    "Major": 1,
    "Minor": 2,
    "Info": 3,
}


@dataclass(slots=True)
class Rule:
    """Definition d'une regle d'analyse statique (chargee depuis rules.xml)."""

    id: str
    enabled: bool
    scope: str
    category: str
    subcategory: str
    severity: str
    source: str
    reference: str
    title: str
    description: str
    rationale: str
    remediation: str


@dataclass(slots=True)
class Finding:
    """Occurrence d'une regle violee sur un artefact donne."""

    rule: Rule
    target_kind: str
    target_name: str
    message: str = ""
    details: list[str] = field(default_factory=list)
    source_path: Path | None = None
    line: int | None = None

    @property
    def severity_rank(self) -> int:
        return SEVERITY_ORDER.get(self.rule.severity, 99)
