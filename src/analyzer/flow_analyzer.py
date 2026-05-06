from __future__ import annotations

from src.analyzer.models import Finding
from src.analyzer.rule_catalog import RuleCatalog
from src.core.models import FlowInfo


def analyze_flow(flow: FlowInfo, catalog: RuleCatalog) -> list[Finding]:
    findings: list[Finding] = []

    rule = catalog.get("FLOW-READ-001")
    if rule and rule.enabled and not flow.description:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message="Le flow ne porte pas de description globale.",
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-READ-002")
    if rule and rule.enabled and flow.total_elements > 0:
        described_ratio = flow.described_elements / flow.total_elements
        if described_ratio < 0.5:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=f"Seulement {described_ratio:.0%} des elements du flow portent une description.",
                    details=[
                        f"{flow.described_elements}/{flow.total_elements} elements documentes.",
                    ],
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-MAINT-001")
    if rule and rule.enabled and flow.total_elements > 40:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=f"Flow comportant {flow.total_elements} elements (seuil recommande : 40).",
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-MAINT-002")
    if rule and rule.enabled:
        decisions = flow.element_counts.get("decisions", 0)
        if decisions > 8:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=f"{decisions} decisions detectees dans le flow (seuil recommande : 8).",
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-PERF-001")
    if rule and rule.enabled:
        data_ops = sum(
            flow.element_counts.get(name, 0)
            for name in ("recordCreates", "recordUpdates", "recordDeletes", "recordLookups")
        )
        if data_ops > 6:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=f"{data_ops} operations de donnees (create/update/delete/lookup) detectees.",
                    details=[
                        f"Lookups = {flow.element_counts.get('recordLookups', 0)}, "
                        f"Creates = {flow.element_counts.get('recordCreates', 0)}, "
                        f"Updates = {flow.element_counts.get('recordUpdates', 0)}, "
                        f"Deletes = {flow.element_counts.get('recordDeletes', 0)}.",
                    ],
                    source_path=flow.source_path,
                )
            )

    rule = catalog.get("FLOW-MAINT-003")
    if rule and rule.enabled and flow.max_depth > 4:
        findings.append(
            Finding(
                rule=rule,
                target_kind="Flow",
                target_name=flow.name,
                message=f"Profondeur maximale = {flow.max_depth} (seuil recommande : 4).",
                source_path=flow.source_path,
            )
        )

    rule = catalog.get("FLOW-ADAPT-001")
    if rule and rule.enabled:
        status = (flow.status or "").lower()
        if status and status not in {"active", "obsolete"}:
            findings.append(
                Finding(
                    rule=rule,
                    target_kind="Flow",
                    target_name=flow.name,
                    message=f"Le flow est au statut '{flow.status or 'Non renseigne'}'.",
                    source_path=flow.source_path,
                )
            )

    return findings
