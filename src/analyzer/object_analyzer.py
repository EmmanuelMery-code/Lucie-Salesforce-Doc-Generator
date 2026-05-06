from __future__ import annotations

import re

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import ObjectInfo, ValidationRuleInfo


def analyze_object(obj: ObjectInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    rule = catalog.get("OBJ-READ-001")
    if rule and rule.enabled and obj.custom and not obj.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Object",
                target_name=obj.api_name,
                message="Objet personnalise sans description metadata.",
                source_path=obj.source_path,
            )
        )

    rule = catalog.get("OBJ-ADAPT-001")
    if rule and rule.enabled:
        custom_fields = [f for f in obj.fields if f.custom]
        if len(custom_fields) > 50:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=f"{len(custom_fields)} champs personnalises sur l'objet (seuil recommande : 50).",
                    source_path=obj.source_path,
                )
            )

    rule = catalog.get("OBJ-MAINT-001")
    if rule and rule.enabled:
        active_vrs = [vr for vr in obj.validation_rules if vr.active]
        if len(active_vrs) > 10:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=f"{len(active_vrs)} validation rules actives sur l'objet (seuil recommande : 10).",
                    source_path=obj.source_path,
                )
            )

    rule = catalog.get("OBJ-MAINT-002")
    if rule and rule.enabled:
        active_rts = [rt for rt in obj.record_types if rt.active]
        if len(active_rts) > 3:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Object",
                    target_name=obj.api_name,
                    message=f"{len(active_rts)} record types actifs (seuil recommande : 3).",
                    source_path=obj.source_path,
                )
            )

    # FIELD-READ-001 : champs custom sans description (agrege au niveau de l'objet)
    rule = catalog.get("FIELD-READ-001")
    if rule and rule.enabled:
        undocumented = [
            field.api_name
            for field in obj.fields
            if field.custom and not field.description
        ]
        if undocumented:
            details: list[str] = []
            preview = ", ".join(undocumented[:10])
            if len(undocumented) > 10:
                preview += f", ... (+{len(undocumented) - 10})"
            details.append(f"Champs concernes : {preview}.")
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Field",
                    target_name=obj.api_name,
                    message=f"{len(undocumented)} champ(s) personnalise(s) sans description.",
                    details=details,
                    source_path=obj.source_path,
                )
            )

    return findings


def analyze_validation_rule(
    vr: ValidationRuleInfo, object_name: str, catalog: RuleCatalog
) -> list[Finding]:
    findings: list[Finding] = []
    target_name = f"{object_name}.{vr.full_name}"

    rule = catalog.get("VR-READ-001")
    if rule and rule.enabled and not vr.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="ValidationRule",
                target_name=target_name,
                message="La validation rule ne fournit pas de description.",
            )
        )

    rule = catalog.get("VR-MAINT-001")
    if rule and rule.enabled:
        formula = vr.error_condition_formula or ""
        operator_count = len(re.findall(r"\b(AND|OR|NOT|IF)\b\s*\(", formula))
        if len(formula) > 500 or operator_count > 8:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="ValidationRule",
                    target_name=target_name,
                    message=f"Formule de {len(formula)} caracteres, {operator_count} operateurs logiques.",
                )
            )

    return findings
