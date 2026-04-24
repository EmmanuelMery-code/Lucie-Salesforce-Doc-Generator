"""Build an LLM-friendly description of the latest analysed Salesforce org."""

from __future__ import annotations

from typing import Any

from src.core.models import MetadataSnapshot

_MAX_OBJECTS_DETAILED = 40
_MAX_APEX_DETAILED = 30
_MAX_FLOWS_DETAILED = 30
_MAX_SECURITY_DETAILED = 20


def build_system_prompt(language: str = "fr") -> str:
    """Return the base instructions for the assistant, localised if needed."""
    if (language or "").lower().startswith("en"):
        return (
            "You are an expert Salesforce consultant and architect. "
            "You assist the user in analysing a Salesforce org, giving insights on "
            "customisation, adoption vs adaptation trade-offs, Apex, Flows, LWC, "
            "OmniStudio, security and release engineering. "
            "Always ground your answers in the provided org context.\n\n"
            "To answer accurately you MUST walk through the source repository and the "
            "generated documentation: recursively browse every folder and sub-folder "
            "(objects/, classes/, triggers/, flows/, lwc/, aura/, omniScripts/, "
            "integrationProcedures/, profiles/, permissionsets/, applications/, "
            "layouts/, flexipages/, staticresources/, customMetadata/, etc.) at "
            "several nesting levels. Open the relevant source files (*.xml, *.cls, "
            "*.trigger, *.js, *.html, *.css, meta.xml, *.flow-meta.xml, *.object-meta.xml, "
            "validationRules/*.xml) AND the matching HTML documentation pages "
            "(index.html, objects/*.html, apex/*.html, flows/*.html, omni/*.html, "
            "adopt_adapt.html, scoring.html) before answering. Cross-reference code "
            "and documentation, and cite the exact file paths you relied on.\n\n"
            "If a detail is missing, say so, explain which folders / files you would "
            "still need, and propose how to gather it. Prefer concise, actionable "
            "recommendations with bullet points and code snippets when useful."
        )
    return (
        "Tu es un expert consultant et architecte Salesforce. "
        "Tu aides l'utilisateur a analyser une org Salesforce, a donner des recommandations "
        "sur la customisation, l'arbitrage Adopt vs Adapt, Apex, Flows, LWC, OmniStudio, "
        "la securite et la gestion des livraisons. "
        "Appuie toujours tes reponses sur le contexte fourni sur l'org.\n\n"
        "Pour repondre precisement tu DOIS parcourir le depot source ainsi que la "
        "documentation generee : explore de maniere recursive chaque dossier et "
        "sous-dossier sur plusieurs niveaux (objects/, classes/, triggers/, flows/, "
        "lwc/, aura/, omniScripts/, integrationProcedures/, profiles/, permissionsets/, "
        "applications/, layouts/, flexipages/, staticresources/, customMetadata/, etc.). "
        "Ouvre les fichiers sources pertinents (*.xml, *.cls, *.trigger, *.js, *.html, "
        "*.css, meta.xml, *.flow-meta.xml, *.object-meta.xml, validationRules/*.xml) "
        "ET les pages HTML de documentation correspondantes (index.html, "
        "objects/*.html, apex/*.html, flows/*.html, omni/*.html, adopt_adapt.html, "
        "scoring.html) avant de repondre. Recoupe systematiquement le code et la "
        "documentation, et cite les chemins exacts des fichiers consultes.\n\n"
        "Si une information manque, dis-le, precise quels dossiers ou fichiers "
        "resteraient a ouvrir et propose la facon de la recuperer. Prefere des "
        "reponses concises et actionnables, avec des listes a puces et des extraits "
        "de code lorsque pertinent. Reponds en francais."
    )


def build_org_context(snapshot: MetadataSnapshot | None) -> str:
    """Build a textual context string for the current metadata snapshot."""
    if snapshot is None:
        return (
            "Aucune analyse d'org Salesforce n'a encore ete generee. "
            "Demande a l'utilisateur de lancer la generation de la documentation avant "
            "de poser des questions factuelles sur l'org."
        )

    metrics = snapshot.metrics
    lines: list[str] = []
    lines.append("=== CONTEXTE DE L'ORG SALESFORCE ANALYSEE ===")
    lines.append(f"Dossier source : {snapshot.source_dir}")
    lines.append(f"Packages detectes : {len(snapshot.package_roots)}")
    lines.append("")

    lines.append("## Metriques globales")
    lines.append(f"- Score de complexite : {metrics.score} ({metrics.level})")
    lines.append(
        f"- Score Adopt vs Adapt : {metrics.adopt_adapt_score} ({metrics.adopt_adapt_level})"
    )
    lines.append(f"- Objets personnalises : {metrics.custom_objects}")
    lines.append(f"- Champs personnalises : {metrics.custom_fields}")
    lines.append(f"- Record Types : {metrics.record_types}")
    lines.append(f"- Validation Rules : {metrics.validation_rules}")
    lines.append(f"- Layouts : {metrics.layouts}")
    lines.append(f"- Onglets personnalises : {metrics.custom_tabs}")
    lines.append(f"- Applications personnalisees : {metrics.custom_apps}")
    lines.append(f"- Flows : {metrics.flows}")
    lines.append(f"- Classes Apex : {metrics.apex_classes}")
    lines.append(f"- Triggers Apex : {metrics.apex_triggers}")
    lines.append(f"- Lightning Web Components : {metrics.lwc_count}")
    lines.append(f"- FlexiPages : {metrics.flexipage_count}")
    lines.append(f"- OmniScripts : {metrics.omni_scripts}")
    lines.append(f"- Integration Procedures : {metrics.omni_integration_procedures}")
    lines.append(f"- UI Cards : {metrics.omni_ui_cards}")
    lines.append(f"- Data Transforms : {metrics.omni_data_transforms}")
    lines.append("")

    _append_objects(lines, snapshot)
    _append_apex(lines, snapshot)
    _append_flows(lines, snapshot)
    _append_security(lines, snapshot)
    _append_inventory(lines, snapshot)

    return "\n".join(lines).strip()


def _append_objects(lines: list[str], snapshot: MetadataSnapshot) -> None:
    if not snapshot.objects:
        return
    lines.append(f"## Objets ({len(snapshot.objects)} detectes)")
    for obj in snapshot.objects[:_MAX_OBJECTS_DETAILED]:
        field_count = len(obj.fields)
        custom_field_count = sum(1 for f in obj.fields if f.custom)
        lines.append(
            f"- {obj.api_name}"
            f" (label={obj.label or '-'}"
            f", champs={field_count}/{custom_field_count} custom"
            f", RT={len(obj.record_types)}"
            f", VR={len(obj.validation_rules)}"
            f", relations={len(obj.relationships)})"
        )
    if len(snapshot.objects) > _MAX_OBJECTS_DETAILED:
        lines.append(f"... et {len(snapshot.objects) - _MAX_OBJECTS_DETAILED} autres objets")
    lines.append("")


def _append_apex(lines: list[str], snapshot: MetadataSnapshot) -> None:
    if not snapshot.apex_artifacts:
        return
    classes = [a for a in snapshot.apex_artifacts if a.kind == "class"]
    triggers = [a for a in snapshot.apex_artifacts if a.kind == "trigger"]
    lines.append(
        f"## Apex ({len(classes)} classes, {len(triggers)} triggers,"
        f" {sum(1 for a in snapshot.apex_artifacts if a.is_test)} tests)"
    )
    shown = 0
    for artifact in snapshot.apex_artifacts:
        if shown >= _MAX_APEX_DETAILED:
            break
        lines.append(
            f"- [{artifact.kind}] {artifact.name}"
            f" ({artifact.line_count} lignes,"
            f" SOQL={artifact.soql_count}, DML={artifact.dml_count},"
            f" sharing='{artifact.sharing_declaration or 'non declare'}',"
            f" test={'oui' if artifact.is_test else 'non'})"
        )
        shown += 1
    remaining = len(snapshot.apex_artifacts) - shown
    if remaining > 0:
        lines.append(f"... et {remaining} autres artefacts Apex")
    lines.append("")


def _append_flows(lines: list[str], snapshot: MetadataSnapshot) -> None:
    if not snapshot.flows:
        return
    lines.append(f"## Flows ({len(snapshot.flows)} detectes)")
    for flow in snapshot.flows[:_MAX_FLOWS_DETAILED]:
        lines.append(
            f"- {flow.name} [{flow.process_type or 'type inconnu'}]"
            f" status={flow.status or '-'}"
            f" score={flow.complexity_score} ({flow.complexity_level})"
            f" elements={flow.total_elements}"
            f" decisions={flow.element_counts.get('decisions', 0)}"
            f" loops={flow.element_counts.get('loops', 0)}"
        )
    if len(snapshot.flows) > _MAX_FLOWS_DETAILED:
        lines.append(f"... et {len(snapshot.flows) - _MAX_FLOWS_DETAILED} autres flows")
    lines.append("")


def _append_security(lines: list[str], snapshot: MetadataSnapshot) -> None:
    if not snapshot.profiles and not snapshot.permission_sets:
        return
    lines.append(
        f"## Securite ({len(snapshot.profiles)} profils, "
        f"{len(snapshot.permission_sets)} permission sets)"
    )
    for artifact in snapshot.profiles[:_MAX_SECURITY_DETAILED]:
        lines.append(
            f"- Profil {artifact.name}"
            f" (obj={len(artifact.object_permissions)},"
            f" champs={len(artifact.field_permissions)},"
            f" apps={len(artifact.application_visibilities)})"
        )
    for artifact in snapshot.permission_sets[:_MAX_SECURITY_DETAILED]:
        lines.append(
            f"- PermissionSet {artifact.name}"
            f" (obj={len(artifact.object_permissions)},"
            f" champs={len(artifact.field_permissions)},"
            f" classes={len(artifact.class_accesses)})"
        )
    lines.append("")


def _append_inventory(lines: list[str], snapshot: MetadataSnapshot) -> None:
    if not snapshot.inventory:
        return
    lines.append("## Inventaire additionnel")
    for key, rows in sorted(snapshot.inventory.items()):
        if not isinstance(rows, list):
            continue
        lines.append(f"- {key} : {len(rows)} entrees")
    lines.append("")


def format_conversation_preview(history: list[dict[str, Any]], limit: int = 40) -> str:
    """Utility for debug logs: pretty-print the conversation history."""
    preview = history[-limit:]
    return "\n".join(
        f"{item.get('role', '?')}: {str(item.get('content', ''))[:120]}" for item in preview
    )
