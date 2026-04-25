"""Render the per-object documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import MetadataSnapshot, ObjectInfo
from src.core.utils import html_value, safe_slug, write_text
from src.reporting.html_mermaid import (
    object_mermaid,
    validation_rule_mermaid,
)

from src.reporting.html.findings import (
    render_analyzer_tab,
    render_findings_summary,
    render_security_rows,
    security_rows,
)
from src.reporting.html.page_shell import (
    index_back_link,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_object_page(
    item: ObjectInfo,
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    object_findings: list[Finding] | None = None,
    validation_findings: list[Finding] | None = None,
) -> str:
    object_findings = object_findings or []
    validation_findings = validation_findings or []
    profiles = security_rows(snapshot.profiles, item.api_name)
    permsets = security_rows(snapshot.permission_sets, item.api_name)
    fields_rows = "".join(
        f"<tr><td>{html_value(field.api_name)}</td><td>{html_value(field.label)}</td>"
        f"<td>{html_value(field.data_type)}</td><td>{html_value(field.description)}</td>"
        f"<td>{'Oui' if field.required else 'Non'}</td></tr>"
        for field in item.fields
    ) or "<tr><td colspan='5' class='empty'>Aucun champ detecte.</td></tr>"

    record_type_rows = "".join(
        f"<tr><td>{html_value(record_type.full_name)}</td><td>{html_value(record_type.label)}</td>"
        f"<td>{html_value(record_type.description)}</td><td>{'Oui' if record_type.active else 'Non'}</td></tr>"
        for record_type in item.record_types
    ) or "<tr><td colspan='4' class='empty'>Aucun record type detecte.</td></tr>"

    description_rows = [
        ("Nom API", item.api_name),
        ("Label", item.label),
        ("Label pluriel", item.plural_label),
        ("Description", item.description),
        ("Deployment status", item.deployment_status),
        ("Sharing model", item.sharing_model),
        ("Visibilite", item.visibility),
    ]
    description_html = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value or 'Non renseigne')}</li>"
        for label, value in description_rows
    )

    mermaid = object_mermaid(item)
    validation_rows = "".join(
        f"<tr><td>{html_value(vr.full_name)}</td><td>{'Oui' if vr.active else 'Non'}</td>"
        f"<td>{html_value(vr.description)}</td><td>{html_value(vr.error_display_field)}</td>"
        f"<td>{html_value(vr.error_message)}</td></tr>"
        for vr in item.validation_rules
    ) or "<tr><td colspan='5' class='empty'>Aucune regle de validation detectee.</td></tr>"

    validation_panels = []
    for vr in item.validation_rules:
        formula_html = f"<pre style='background:#f1f5f9; padding:12px; border-radius:6px; overflow:auto;'>{html_value(vr.error_condition_formula)}</pre>"
        mermaid_tree = validation_rule_mermaid(vr)
        validation_panels.append(
            f"<div class='section'><h3>{html_value(vr.full_name)}</h3>"
            f"<p><strong>Description:</strong> {html_value(vr.description or 'Non renseignee')}</p>"
            f"<p><strong>Message d'erreur:</strong> {html_value(vr.error_message)}</p>"
            f"<h4>Arbre de decision (Mermaid)</h4>{mermaid_tree}"
            f"<h4>Formule</h4>{formula_html}</div>"
        )
    validation_content = "".join(validation_panels) or "<p class='empty'>Aucune regle de validation detaillee.</p>"

    relation_table = "".join(
        f"<tr><td>{html_value(rel.field_name)}</td><td>{html_value(rel.relationship_type)}</td>"
        f"<td>{html_value(', '.join(rel.targets))}</td></tr>"
        for rel in item.relationships
    ) or "<tr><td colspan='3' class='empty'>Aucune relation detectee.</td></tr>"

    profile_rows = render_security_rows(profiles, "Aucun profil avec acces detecte.")
    permset_rows = render_security_rows(permsets, "Aucun permission set avec acces detecte.")

    combined_findings = list(object_findings) + list(validation_findings)
    analyzer_summary_inline = render_findings_summary(combined_findings)
    analyzer_content = render_analyzer_tab(combined_findings)

    synthesis_html = (
        "<ul>" + description_html + "</ul>"
        + "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_summary_inline
        + "</div>"
    )

    tabs = tabbed_sections(
        f"object-{safe_slug(item.api_name)}",
        [
            ("Synthese", synthesis_html),
            ("Fields", f"<table><thead><tr><th>Name</th><th>Label</th><th>Type</th><th>Description</th><th>Required</th></tr></thead><tbody>{fields_rows}</tbody></table>"),
            ("Profiles", f"<table><thead><tr><th>Profile</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{profile_rows}</tbody></table>"),
            ("Permission Sets", f"<table><thead><tr><th>Permission Set</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{permset_rows}</tbody></table>"),
            ("Record Types", f"<table><thead><tr><th>Nom</th><th>Label</th><th>Description</th><th>Actif</th></tr></thead><tbody>{record_type_rows}</tbody></table>"),
            ("Validation Rules", f"<table><thead><tr><th>Nom</th><th>Actif</th><th>Description</th><th>Champ d'erreur</th><th>Message d'erreur</th></tr></thead><tbody>{validation_rows}</tbody></table><hr/>{validation_content}"),
            ("Relations", f"{mermaid}<table><thead><tr><th>Champ</th><th>Type</th><th>Cible</th></tr></thead><tbody>{relation_table}</tbody></table>"),
            ("Analyseur", analyzer_content),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "objets")}
<h1>{html_value(item.api_name)}</h1>
<div class="cards">
  <div class="card"><span>Champs</span><span class="value">{len(item.fields)}</span></div>
  <div class="card"><span>Record types</span><span class="value">{len(item.record_types)}</span></div>
  <div class="card"><span>Regles de validation</span><span class="value">{len(item.validation_rules)}</span></div>
  <div class="card"><span>Relations</span><span class="value">{len(item.relationships)}</span></div>
</div>
{tabs}
"""
    return render_page(item.api_name, body, current_path, assets_dir)


def write_object_pages(
    snapshot: MetadataSnapshot,
    objects_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, Path]:
    output: dict[str, Path] = {}
    object_findings = getattr(analyzer_report, "objects", {}) if analyzer_report else {}
    validation_findings = getattr(analyzer_report, "validation_rules", {}) if analyzer_report else {}
    for item in snapshot.objects:
        path = objects_dir / f"{item.api_name}.html"
        vr_findings_for_object: list[Finding] = []
        for vr in item.validation_rules:
            key = f"{item.api_name}.{vr.full_name}"
            vr_findings_for_object.extend(validation_findings.get(key, []))
        content = render_object_page(
            item,
            snapshot,
            path,
            output_dir,
            assets_dir,
            object_findings.get(item.api_name, []),
            vr_findings_for_object,
        )
        write_text(path, content)
        output[item.api_name] = path
    log(f"{len(output)} page(s) objet generee(s).")
    return output
