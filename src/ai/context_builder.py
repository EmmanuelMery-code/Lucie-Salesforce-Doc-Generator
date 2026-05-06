"""Build an LLM-friendly description of the latest analysed Salesforce org."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.models import MetadataSnapshot

_MAX_OBJECTS_DETAILED = 40
_MAX_APEX_DETAILED = 30
_MAX_FLOWS_DETAILED = 30
_MAX_SECURITY_DETAILED = 20


def build_system_prompt(language: str = "fr") -> str:
    """Return the base instructions for the assistant, localised if needed.

    The concrete source and documentation paths are NOT baked into this text:
    they are injected dynamically by :func:`build_org_context` so they stay
    accurate even after the user edits or resets the system prompt.
    """
    if (language or "").lower().startswith("en"):
        return (
            "You are an expert Salesforce consultant and architect. "
            "You assist the user in analysing a Salesforce org, giving insights on "
            "customisation, adoption vs adaptation trade-offs, Apex, Flows, LWC, "
            "OmniStudio, security and release engineering. "
            "Always ground your answers in the provided org context.\n\n"
            "The exact source repository path and generated documentation path are "
            "provided in the 'Chemins a explorer' / 'Paths to explore' section of "
            "the org context below. You MUST walk through BOTH directories: "
            "recursively browse every folder and sub-folder (objects/, classes/, "
            "triggers/, flows/, lwc/, aura/, omniScripts/, integrationProcedures/, "
            "profiles/, permissionsets/, applications/, layouts/, flexipages/, "
            "staticresources/, customMetadata/, etc.) at several nesting levels. "
            "Open the relevant source files (*.xml, *.cls, *.trigger, *.js, *.html, "
            "*.css, meta.xml, *.flow-meta.xml, *.object-meta.xml, "
            "validationRules/*.xml) AND the matching HTML documentation pages "
            "(index.html, objects/*.html, apex/*.html, flows/*.html, omni/*.html, "
            "adopt_adapt.html, scoring.html, data_dictionary.html) before "
            "answering. Cross-reference code and documentation, and cite the exact "
            "file paths you relied on.\n\n"
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
        "Les chemins exacts du depot source et de la documentation generee te sont "
        "fournis dans la section 'Chemins a explorer' du contexte ci-dessous. Tu "
        "DOIS parcourir ces DEUX repertoires : explore de maniere recursive chaque "
        "dossier et sous-dossier sur plusieurs niveaux (objects/, classes/, "
        "triggers/, flows/, lwc/, aura/, omniScripts/, integrationProcedures/, "
        "profiles/, permissionsets/, applications/, layouts/, flexipages/, "
        "staticresources/, customMetadata/, etc.). Ouvre les fichiers sources "
        "pertinents (*.xml, *.cls, *.trigger, *.js, *.html, *.css, meta.xml, "
        "*.flow-meta.xml, *.object-meta.xml, validationRules/*.xml) ET les pages "
        "HTML de documentation correspondantes (index.html, objects/*.html, "
        "apex/*.html, flows/*.html, omni/*.html, adopt_adapt.html, scoring.html, "
        "data_dictionary.html) avant de repondre. Recoupe systematiquement le code "
        "et la documentation, et cite les chemins exacts des fichiers consultes.\n\n"
        "Si une information manque, dis-le, precise quels dossiers ou fichiers "
        "resteraient a ouvrir et propose la facon de la recuperer. Prefere des "
        "reponses concises et actionnables, avec des listes a puces et des extraits "
        "de code lorsque pertinent. Reponds en francais."
    )


def build_org_context(
    snapshot: MetadataSnapshot | None,
    *,
    source_dir: str | Path | None = None,
    documentation_dir: str | Path | None = None,
) -> str:
    """Build a textual context string for the current metadata snapshot.

    ``source_dir`` and ``documentation_dir`` are the paths currently configured
    in the UI (picker values). They are ALWAYS reinjected at each call so the
    assistant sees the up-to-date locations, even if the user changes them
    between two questions or before the first analysis. When a snapshot is
    available, ``snapshot.source_dir`` is also surfaced (the path used for the
    actual analysis).
    """
    paths_block = _format_paths_block(
        source_dir=source_dir,
        documentation_dir=documentation_dir,
        snapshot=snapshot,
    )

    if snapshot is None:
        # No in-memory snapshot, BUT the source and documentation directories
        # may already be populated on disk from a previous run (very common
        # right after an app restart). In that case the assistant must NOT
        # refuse the question: it must browse the filesystem directly.
        if paths_block:
            lines: list[str] = [paths_block, ""]
            lines.append("## Etat de l'analyse en memoire")
            docs_ready = _documentation_already_generated(documentation_dir)
            source_ready = _directory_has_content(source_dir)
            if docs_ready or source_ready:
                lines.append(
                    "Aucune analyse n'a ete relancee dans la session Lucie en "
                    "cours, mais les dossiers ci-dessus existent deja sur le "
                    "disque et contiennent du contenu exploitable "
                    + (
                        "(la documentation generee est presente : index.html trouve)."
                        if docs_ready
                        else "(code source Salesforce detecte)."
                    )
                )
                lines.append(
                    "Tu DOIS repondre en parcourant directement ces dossiers "
                    "et leurs sous-dossiers (plusieurs niveaux) pour lire les "
                    "fichiers sources et la documentation HTML/Excel. Ne "
                    "refuse PAS la question sous pretexte qu'aucune analyse "
                    "n'a ete generee dans la session courante : ouvre les "
                    "fichiers sur disque et fournis une reponse concrete en "
                    "citant les chemins exacts consultes."
                )
            else:
                lines.append(
                    "Les chemins indiques pointent vers des dossiers vides ou "
                    "introuvables. Demande a l'utilisateur de verifier le "
                    "repertoire source et/ou de lancer 'Generer la "
                    "documentation' avant de pouvoir repondre."
                )
            return "\n".join(lines)

        return (
            "Aucun dossier source ni dossier de documentation n'est configure "
            "dans Lucie. Demande a l'utilisateur de renseigner ces chemins "
            "dans l'ecran principal, puis de lancer la generation de la "
            "documentation si elle n'a pas encore ete faite."
        )

    metrics = snapshot.metrics
    lines: list[str] = []
    lines.append("=== CONTEXTE DE L'ORG SALESFORCE ANALYSEE ===")
    if paths_block:
        lines.append(paths_block)
        lines.append("")
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


def _normalize_path(value: str | Path | None) -> str:
    """Return an absolute, readable path string, or '' when unusable."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(Path(text).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        return text


def _resolve_path(value: str | Path | None) -> Path | None:
    """Return a ``Path`` object if ``value`` is usable, else ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Path(text).expanduser()
    except (OSError, RuntimeError, ValueError):
        return None


def _documentation_already_generated(value: str | Path | None) -> bool:
    """Return True when the output directory already contains a Lucie report."""
    path = _resolve_path(value)
    if path is None or not path.is_dir():
        return False
    # Lucie always emits index.html at the root of the documentation folder.
    if (path / "index.html").is_file():
        return True
    # Fallback: any typical sub-folder is a good indicator too.
    for probe in ("objects", "apex", "flows", "omni"):
        if (path / probe).is_dir():
            return True
    return False


def _directory_has_content(value: str | Path | None) -> bool:
    """Return True when the directory exists and is not empty."""
    path = _resolve_path(value)
    if path is None or not path.is_dir():
        return False
    try:
        next(path.iterdir())
    except StopIteration:
        return False
    except OSError:
        return False
    return True


def _format_paths_block(
    *,
    source_dir: str | Path | None,
    documentation_dir: str | Path | None,
    snapshot: MetadataSnapshot | None,
) -> str:
    """Build the 'Chemins a explorer' section listing the live paths.

    Always refreshed from the UI values (``source_dir`` / ``documentation_dir``)
    so the assistant receives accurate locations on every message.
    """
    configured_source = _normalize_path(source_dir)
    configured_docs = _normalize_path(documentation_dir)
    analysed_source = (
        _normalize_path(snapshot.source_dir) if snapshot is not None else ""
    )

    if not (configured_source or configured_docs or analysed_source):
        return ""

    entries: list[str] = []
    entries.append("## Chemins a explorer (a jour a chaque message)")
    if configured_source:
        entries.append(f"- Repertoire source (code Salesforce) : {configured_source}")
    if (
        analysed_source
        and analysed_source != configured_source
    ):
        entries.append(
            f"- Repertoire source utilise pour la derniere analyse : {analysed_source}"
        )
    if configured_docs:
        entries.append(
            f"- Repertoire de la documentation generee (HTML/Excel) : {configured_docs}"
        )
    entries.append(
        "Tu DOIS parcourir recursivement ces dossiers et leurs sous-dossiers "
        "pour lire les fichiers sources et les fichiers de documentation avant "
        "de repondre. Cite les chemins exacts des fichiers consultes."
    )
    return "\n".join(entries)


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
