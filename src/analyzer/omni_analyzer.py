from __future__ import annotations

import xml.etree.ElementTree as ET

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.utils import SF_NS, child_text


def analyze_data_transform(
    name: str, xml_content: str, catalog: RuleCatalog
) -> list[Finding]:
    findings: list[Finding] = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return findings

    description = child_text(root, "description")
    items = root.findall("sf:omniDataTransformItem", SF_NS)
    disabled = [
        item for item in items if child_text(item, "disabled").lower() == "true"
    ]

    rule = catalog.get("OMNI-READ-001")
    if rule and rule.enabled and not description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="OmniDataTransform",
                target_name=name,
                message="Data Transform sans description metadata.",
            )
        )

    rule = catalog.get("OMNI-MAINT-001")
    if rule and rule.enabled and len(disabled) > 3:
        findings.append(
            Finding(
                rule=rule,
                target_kind="OmniDataTransform",
                target_name=name,
                message=f"{len(disabled)} item(s) desactive(s) subsistent dans la definition.",
                details=[
                    f"Exemples : "
                    + ", ".join(
                        filter(
                            None,
                            [child_text(item, "name") or child_text(item, "globalKey") for item in disabled[:5]],
                        )
                    )
                ],
            )
        )

    rule = catalog.get("OMNI-ADAPT-001")
    if rule and rule.enabled and len(items) > 40:
        findings.append(
            Finding(
                rule=rule,
                target_kind="OmniDataTransform",
                target_name=name,
                message=f"Data Transform volumineux : {len(items)} items (seuil recommande : 40).",
            )
        )

    return findings
