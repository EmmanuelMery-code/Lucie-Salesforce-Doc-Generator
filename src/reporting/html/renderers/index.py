"""Render the main ``index.html`` documentation home page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.ai_usage import AIUsageEntry, AIUsageStats
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import (
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)
from src.core.utils import html_value, write_text

from src.reporting.html.assets import SEVERITY_CSS_CLASS, SEVERITY_LABEL
from src.reporting.html.findings import render_findings_summary
from src.reporting.html.page_shell import (
    href_relative,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_index_omni_panel(
    omni_pages: dict[str, list[dict[str, object]]],
    current_path: Path,
) -> str:
    if not omni_pages:
        return "<p class='empty'>Aucun composant OmniStudio detecte.</p>"

    sections: list[tuple[str, str]] = []
    for subcategory in sorted(omni_pages.keys(), key=lambda value: value.lower()):
        entries = omni_pages[subcategory]
        if not entries:
            rows = "<tr><td colspan='3' class='empty'>Aucun composant dans cette categorie.</td></tr>"
        else:
            rendered_rows: list[str] = []
            for entry in entries:
                name = str(entry.get("name") or "")
                page_path = entry.get("page")
                source = str(entry.get("source") or "")
                file_type = str(entry.get("type") or "")
                if isinstance(page_path, Path):
                    link = f"<a href='{href_relative(current_path, page_path)}'>{html_value(name)}</a>"
                else:
                    link = html_value(name)
                rendered_rows.append(
                    f"<tr><td>{link}</td><td>{html_value(file_type)}</td><td>{html_value(source)}</td></tr>"
                )
            rows = "".join(rendered_rows)

        label = f"{subcategory} ({len(entries)})"
        table = (
            "<table><thead><tr><th>Composant</th><th>Type</th><th>Source</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
        sections.append((label, table))

    return tabbed_sections("index-omni", sections)


def render_index_analyzer_panel(
    analyzer_report,
    current_path: Path,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
) -> str:
    if analyzer_report is None:
        return "<p class='empty'>Analyseur non execute.</p>"

    findings = analyzer_report.all_findings()
    summary = render_findings_summary(findings)
    if not findings:
        return summary + "<p class='empty'>Aucun finding : le projet respecte toutes les regles activees.</p>"

    rule_counts = analyzer_report.rule_counts()
    rules_by_id = {rule.id: rule for rule in analyzer_report.rules_used}
    rule_rows = []
    for rule_id, count in sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        rule = rules_by_id.get(rule_id)
        if not rule:
            continue
        sev_css = SEVERITY_CSS_CLASS.get(rule.severity, "sev-info")
        sev_label = SEVERITY_LABEL.get(rule.severity, rule.severity)
        reference = ""
        if rule.reference:
            reference = f"<a href='{html_value(rule.reference)}' target='_blank' rel='noopener'>Reference</a>"
        rule_rows.append(
            f"<tr>"
            f"<td><span class='sev-badge {sev_css}'>{html_value(sev_label)}</span></td>"
            f"<td>{html_value(rule.id)}</td>"
            f"<td>{html_value(rule.title)}</td>"
            f"<td>{html_value(rule.category)} - {html_value(rule.subcategory)}</td>"
            f"<td>{count}</td>"
            f"<td>{reference}</td>"
            f"</tr>"
        )
    rule_table = (
        "<table><thead><tr><th>Severite</th><th>Identifiant</th><th>Regle</th><th>Categorie</th><th>Occurrences</th><th>Reference</th></tr></thead>"
        f"<tbody>{''.join(rule_rows)}</tbody></table>"
    )

    artifact_rows: list[str] = []

    def _artifact_row(kind: str, name: str, findings_list: list[Finding], href: str) -> str:
        if not findings_list:
            return ""
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for finding in findings_list:
            counts[finding.rule.severity] = counts.get(finding.rule.severity, 0) + 1
        sev_cells = "".join(
            f"<td>{counts.get(sev, 0)}</td>"
            for sev in ("Critical", "Major", "Minor", "Info")
        )
        name_cell = (
            f"<a href='{html_value(href)}'>{html_value(name)}</a>" if href else html_value(name)
        )
        return (
            f"<tr><td>{html_value(kind)}</td><td>{name_cell}</td>"
            f"{sev_cells}<td>{len(findings_list)}</td></tr>"
        )

    for name, flist in analyzer_report.objects.items():
        page = object_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Objet", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.apex.items():
        page = apex_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Apex", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.flows.items():
        page = flow_pages.get(name)
        href = href_relative(current_path, page) if page else ""
        row = _artifact_row("Flow", name, flist, href)
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.validation_rules.items():
        row = _artifact_row("Validation Rule", name, flist, "")
        if row:
            artifact_rows.append(row)

    for name, flist in analyzer_report.data_transforms.items():
        row = _artifact_row("Data Transform", name, flist, "")
        if row:
            artifact_rows.append(row)

    artifact_rows.sort()
    if not artifact_rows:
        artifact_table = "<p class='empty'>Aucun composant impacte.</p>"
    else:
        artifact_table = (
            "<table><thead><tr><th>Type</th><th>Composant</th>"
            "<th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th><th>Total</th></tr></thead>"
            f"<tbody>{''.join(artifact_rows)}</tbody></table>"
        )

    note = (
        "<p class='empty'>Analyseur inspire de "
        "<a href='https://docs.pmd-code.org/latest/pmd_rules_apex.html' target='_blank' rel='noopener'>PMD Apex</a>, du "
        "<a href='https://architect.salesforce.com/docs/architect/well-architected/guide/overview.html' target='_blank' rel='noopener'>Salesforce Well-Architected Framework</a>, "
        "des <a href='https://architect.salesforce.com/decision-guides' target='_blank' rel='noopener'>Decision Guides Salesforce</a> et des bonnes pratiques "
        "<a href='https://admin.salesforce.com/' target='_blank' rel='noopener'>Salesforce Admins</a>. "
        "Les regles sont declarees dans <code>src/analyzer/rules.xml</code> et peuvent etre activees / desactivees via l'attribut <code>enabled</code>.</p>"
    )

    sections = [
        ("Synthese par regle", rule_table),
        ("Par composant", artifact_table),
    ]
    return summary + tabbed_sections("index-analyzer", sections) + note


def render_excel_exports(output_dir: Path, current_path: Path) -> str:
    excel_dir = output_dir / "excel"
    if not excel_dir.exists():
        return "<p class='empty'>Aucun export Excel detecte.</p>"

    files = sorted(excel_dir.glob("*.xlsx"), key=lambda path: path.name.lower())
    if not files:
        return "<p class='empty'>Aucun export Excel detecte.</p>"

    rows: list[str] = []
    for file_path in files:
        xlsx_href = href_relative(current_path, file_path)
        preview_path = file_path.with_suffix(".html")
        if preview_path.exists():
            preview_href = href_relative(current_path, preview_path)
            preview_cell = (
                f"<a href='{preview_href}'>{html_value(file_path.stem)}</a>"
            )
        else:
            preview_cell = (
                f"<span class='empty'>{html_value(file_path.stem)}</span>"
            )
        rows.append(
            f"<tr><td>{preview_cell}</td>"
            f"<td><a href='{xlsx_href}'>{html_value(file_path.name)}</a></td></tr>"
        )
    return (
        "<table><thead><tr><th>Apercu HTML</th><th>Fichier Excel</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_index_improvements(
    snapshot: MetadataSnapshot,
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    current_path: Path,
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
) -> str:
    rows: list[str] = []
    for artifact in snapshot.apex_artifacts:
        review = apex_reviews.get(artifact.name)
        if review is None:
            continue
        page = apex_pages.get(artifact.name)
        if page:
            component = f"<a href='{href_relative(current_path, page)}'>{html_value(artifact.name)}</a>"
        else:
            component = html_value(artifact.name)
        for improvement in review.improvements:
            rows.append(
                f"<tr><td>Apex/{html_value(artifact.kind)}</td><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    for flow in snapshot.flows:
        review = flow_reviews.get(flow.name)
        if review is None:
            continue
        page = flow_pages.get(flow.name)
        if page:
            component = f"<a href='{href_relative(current_path, page)}'>{html_value(flow.name)}</a>"
        else:
            component = html_value(flow.name)
        for improvement in review.improvements:
            rows.append(
                f"<tr><td>Flow</td><td>{component}</td><td>{html_value(improvement)}</td></tr>"
            )

    return "".join(rows) or "<tr><td colspan='3' class='empty'>Aucune amelioration detectee.</td></tr>"


def render_index_pmd_rows(
    snapshot: MetadataSnapshot,
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    apex_pages: dict[str, Path],
) -> str:
    rows: list[str] = []
    for artifact in snapshot.apex_artifacts:
        violations = pmd_results.get(artifact.name, [])
        if not violations:
            continue
        target = apex_pages.get(artifact.name)
        component = (
            f"<a href='{href_relative(current_path, target)}'>{html_value(artifact.name)}</a>"
            if target
            else html_value(artifact.name)
        )
        for violation in violations:
            line_value = violation.begin_line or ""
            rows.append(
                f"<tr><td>{component}</td><td>{html_value(violation.rule)}</td>"
                f"<td>{html_value(violation.priority)}</td><td>{html_value(line_value)}</td>"
                f"<td>{html_value(violation.message)}</td></tr>"
            )
    return "".join(rows) or "<tr><td colspan='5' class='empty'>Aucune violation PMD detectee.</td></tr>"


def render_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    omni_pages: dict[str, list[dict[str, object]]],
    analyzer_report=None,
    ai_usage_entries: list[AIUsageEntry] | None = None,
    ai_usage_page: Path | None = None,
    ai_usage_stats: AIUsageStats | None = None,
    data_model_stats: DataModelCustomisationStats | None = None,
    adoption_stats: AdoptionStats | None = None,
    customisation_page: Path | None = None,
    adoption_page: Path | None = None,
    card_visibility: IndexCardVisibility | None = None,
) -> str:
    metrics = snapshot.metrics
    visibility = card_visibility or IndexCardVisibility()
    object_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, object_pages[item.api_name])}'>{html_value(item.api_name)}</a></td>"
        f"<td>{html_value(item.label)}</td><td>{len(item.fields)}</td><td>{len(item.relationships)}</td></tr>"
        for item in snapshot.objects
        if item.api_name in object_pages
    ) or "<tr><td colspan='4' class='empty'>Aucun objet analyse.</td></tr>"

    profile_rows = "".join(
        f"<tr><td>{html_value(item.name)}</td><td>{len(item.object_permissions)}</td><td>{len(item.field_permissions)}</td></tr>"
        for item in snapshot.profiles
    ) or "<tr><td colspan='3' class='empty'>Aucun profil analyse.</td></tr>"

    permset_rows = "".join(
        f"<tr><td>{html_value(item.name)}</td><td>{len(item.object_permissions)}</td><td>{len(item.field_permissions)}</td></tr>"
        for item in snapshot.permission_sets
    ) or "<tr><td colspan='3' class='empty'>Aucun permission set analyse.</td></tr>"

    apex_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, apex_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.kind)}</td><td>{item.line_count}</td><td>{item.method_count}</td></tr>"
        for item in snapshot.apex_artifacts
        if item.name in apex_pages
    ) or "<tr><td colspan='4' class='empty'>Aucun artefact Apex analyse.</td></tr>"

    flow_rows = "".join(
        f"<tr><td><a href='{href_relative(current_path, flow_pages[item.name])}'>{html_value(item.name)}</a></td>"
        f"<td>{html_value(item.process_type)}</td><td>{html_value(item.complexity_level)}</td><td>{item.complexity_score}</td><td>{item.total_elements}</td><td>{item.described_elements}</td></tr>"
        for item in snapshot.flows
        if item.name in flow_pages
    ) or "<tr><td colspan='6' class='empty'>Aucun flow analyse.</td></tr>"

    improvements_rows = render_index_improvements(
        snapshot,
        apex_reviews,
        flow_reviews,
        current_path,
        apex_pages,
        flow_pages,
    )
    pmd_rows = render_index_pmd_rows(
        snapshot,
        pmd_results,
        current_path,
        apex_pages,
    )
    excel_links = render_excel_exports(output_dir, current_path)
    omni_panel = render_index_omni_panel(omni_pages, current_path)
    analyzer_panel = render_index_analyzer_panel(
        analyzer_report,
        current_path,
        object_pages,
        apex_pages,
        flow_pages,
    )

    tabs = tabbed_sections(
        "index",
        [
            (
                "Exports Excel",
                excel_links,
            ),
            (
                "Omni",
                omni_panel,
            ),
            (
                "Objets",
                f"<table><thead><tr><th>Objet</th><th>Label</th><th>Nb champs</th><th>Nb relations</th></tr></thead><tbody>{object_rows}</tbody></table>",
            ),
            (
                "Profiles",
                f"<table><thead><tr><th>Profile</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}</tbody></table>",
            ),
            (
                "Permission Sets",
                f"<table><thead><tr><th>Permission Set</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{permset_rows}</tbody></table>",
            ),
            (
                "Apex / Trigger",
                f"<table><thead><tr><th>Nom</th><th>Type</th><th>Lignes</th><th>Methodes</th></tr></thead><tbody>{apex_rows}</tbody></table>",
            ),
            (
                "Flows",
                f"<table><thead><tr><th>Nom</th><th>Type</th><th>Complexite</th><th>Score</th><th>Elements</th><th>Documentes</th></tr></thead><tbody>{flow_rows}</tbody></table>",
            ),
            (
                "Analyseur",
                analyzer_panel,
            ),
            (
                "Ameliorations",
                f"<table><thead><tr><th>Type</th><th>Composant</th><th>Amelioration</th></tr></thead><tbody>{improvements_rows}</tbody></table>",
            ),
            (
                "Qualite PMD",
                f"<table><thead><tr><th>Composant</th><th>Regle</th><th>Priorite</th><th>Ligne</th><th>Message</th></tr></thead><tbody>{pmd_rows}</tbody></table>",
            ),
        ],
    )
    omni_total = (
        metrics.omni_scripts
        + metrics.omni_integration_procedures
        + metrics.omni_ui_cards
        + metrics.omni_data_transforms
    )
    findings_card = ""
    if analyzer_report is not None and visibility.show_findings:
        findings_total = len(analyzer_report.all_findings())
        findings_card = (
            f'  <div class="card"><span>Findings analyseur</span>'
            f'<span class="value">{findings_total}</span></div>\n'
        )

    ai_usage_card = (
        _render_ai_usage_card(ai_usage_stats, ai_usage_page, current_path)
        if visibility.show_ai_usage
        else ""
    )
    data_model_card = (
        _render_data_model_card(data_model_stats, customisation_page, current_path)
        if visibility.show_data_model_footprint
        else ""
    )
    adoption_card = (
        _render_adoption_card(adoption_stats, adoption_page, current_path)
        if visibility.show_adopt_adapt_posture
        else ""
    )

    customization_level_card = (
        f'  <div class="card"><span>Niveau de customisation</span>'
        f'<span class="value">{html_value(metrics.level)}</span></div>\n'
        if visibility.show_customization_level
        else ""
    )
    score_card = (
        f'  <div class="card"><span>Score</span>'
        f'<span class="value">{metrics.score}</span></div>\n'
        if visibility.show_score
        else ""
    )
    adopt_vs_adapt_card = (
        f'  <div class="card"><span>Adopt vs Adapt</span>'
        f'<span class="value">{html_value(metrics.adopt_adapt_level)}</span></div>\n'
        if visibility.show_adopt_vs_adapt
        else ""
    )
    adopt_adapt_score_card = (
        f'  <div class="card"><span>Score Adopt vs Adapt</span>'
        f'<span class="value">{metrics.adopt_adapt_score}</span></div>\n'
        if visibility.show_adopt_adapt_score
        else ""
    )
    custom_objects_card = (
        f'  <div class="card"><span>Objets custom</span>'
        f'<span class="value">{metrics.custom_objects}</span></div>\n'
        if visibility.show_custom_objects
        else ""
    )
    custom_fields_card = (
        f'  <div class="card"><span>Champs custom</span>'
        f'<span class="value">{metrics.custom_fields}</span></div>\n'
        if visibility.show_custom_fields
        else ""
    )
    flows_card = (
        f'  <div class="card"><span>Flows</span>'
        f'<span class="value">{metrics.flows}</span></div>\n'
        if visibility.show_flows
        else ""
    )
    apex_classes_triggers_card = (
        f'  <div class="card"><span>Classes / Triggers</span>'
        f'<span class="value">{metrics.apex_classes + metrics.apex_triggers}</span></div>\n'
        if visibility.show_apex_classes_triggers
        else ""
    )
    omni_components_card = (
        f'  <div class="card"><span>Composants Omni</span>'
        f'<span class="value">{omni_total}</span></div>\n'
        if visibility.show_omni_components
        else ""
    )

    body = f"""
<h1>Documentation Salesforce</h1>
<p>Source analysee: <code>{html_value(snapshot.source_dir)}</code></p>
<div class="cards">
{customization_level_card}{score_card}{adopt_vs_adapt_card}{adopt_adapt_score_card}{custom_objects_card}{custom_fields_card}{flows_card}{apex_classes_triggers_card}{omni_components_card}{findings_card}{ai_usage_card}{data_model_card}{adoption_card}</div>
{tabs}
"""
    return render_page("Index", body, current_path, assets_dir, include_mermaid=False)


def _render_data_model_card(
    stats: DataModelCustomisationStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the *Empreinte data model* card on the index.

    Lays out custom vs standard objects+fields side by side with their
    percentages. The "custom" figure is hyperlinked to the dedicated
    page when available so a reader can drill down.
    """

    if stats is None or stats.total_objects + stats.total_fields == 0:
        return (
            '  <div class="card adopt-card"><span>Empreinte data model</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    custom_count = stats.custom_objects + stats.custom_fields
    standard_count = stats.standard_objects + stats.standard_fields
    custom_pct = stats.percent_custom_global
    standard_pct = stats.percent_standard_global
    total = custom_count + standard_count

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        custom_html = f'<a href="{href}">{custom_count}</a>'
    else:
        custom_html = str(custom_count)

    return (
        '  <div class="card adopt-card">\n'
        '    <span>Empreinte data model</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Custom</span>\n'
        f'        <span class="value">{custom_html}</span>\n'
        f'        <span class="adopt-percent">{custom_pct:.1f} %</span>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Standard</span>\n'
        f'        <span class="value">{standard_count}</span>\n'
        f'        <span class="adopt-percent">{standard_pct:.1f} %</span>\n'
        '      </div>\n'
        '    </div>\n'
        f'    <span class="adopt-hint">Objets+champs analyses : {total}</span>\n'
        '  </div>\n'
    )


def _render_adoption_card(
    stats: AdoptionStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the *Posture Adopt vs Adapt* card on the index.

    Adopt and Adapt counters are shown side by side with the weighted
    percentage; the "Adapt" total aggregates both Adapt-Low (declarative)
    and Adapt-High (code) so the summary stays compact, while the detail
    page is the place to look at the low/high split.
    """

    if stats is None or stats.total_count == 0:
        return (
            '  <div class="card adopt-card"><span>Posture Adopt vs Adapt</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    adopt_count = stats.adopt_count
    adapt_count = stats.adapt_count
    adopt_pct = stats.percent_adoption
    adapt_pct = stats.percent_adaptation

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        adopt_html = f'<a href="{href}">{adopt_count}</a>'
    else:
        adopt_html = str(adopt_count)

    return (
        '  <div class="card adopt-card">\n'
        '    <span>Posture Adopt vs Adapt</span>\n'
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Adopt</span>\n'
        f'        <span class="value">{adopt_html}</span>\n'
        f'        <span class="adopt-percent">{adopt_pct:.1f} %</span>\n'
        '      </div>\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Adapt</span>\n'
        f'        <span class="value">{adapt_count}</span>\n'
        f'        <span class="adopt-percent">{adapt_pct:.1f} %</span>\n'
        '      </div>\n'
        '    </div>\n'
        '    <span class="adopt-hint">'
        f'Capacites : {stats.total_count} / poids {stats.total_weight}'
        '</span>\n'
        '  </div>\n'
    )


def _render_ai_usage_card(
    stats: AIUsageStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    """Render the "Usage IA" card on the index page.

    The card now exposes two figures side by side: how many customised
    elements (custom objects, custom fields, validation rules, record
    types, flows, Apex classes/triggers) carry one of the configured AI
    tags and how many do not, with the matching percentages. The "with
    tag" value links to ``ai_usage.html`` when available so reviewers can
    drill down into the detailed list.
    """

    if stats is None:
        return (
            '  <div class="card ai-usage-card"><span>Usage IA</span>'
            '<span class="value">N/A</span>'
            '<small class="ai-usage-hint">Mesure non disponible.</small></div>\n'
        )

    total = stats.total
    with_count = stats.with_tag_count
    without_count = stats.without_tag_count
    with_pct = stats.percent_with_tag
    without_pct = stats.percent_without_tag

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        with_html = f'<a href="{href}">{with_count}</a>'
    else:
        with_html = str(with_count)

    return (
        '  <div class="card ai-usage-card">\n'
        '    <span>Usage IA</span>\n'
        '    <div class="ai-usage-grid">\n'
        '      <div class="ai-usage-stat ai-usage-stat--with">\n'
        '        <span class="ai-usage-label">Avec tag</span>\n'
        f'        <span class="value">{with_html}</span>\n'
        f'        <span class="ai-usage-percent">{with_pct:.1f} %</span>\n'
        '      </div>\n'
        '      <div class="ai-usage-stat ai-usage-stat--without">\n'
        '        <span class="ai-usage-label">Sans tag</span>\n'
        f'        <span class="value">{without_count}</span>\n'
        f'        <span class="ai-usage-percent">{without_pct:.1f} %</span>\n'
        '      </div>\n'
        '    </div>\n'
        f'    <span class="ai-usage-hint">Total customs : {total}</span>\n'
        '  </div>\n'
    )


def write_index(
    snapshot: MetadataSnapshot,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    apex_reviews: dict[str, ReviewResult],
    flow_reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    omni_pages: dict[str, list[dict[str, object]]] | None = None,
    *,
    analyzer_report=None,
    ai_usage_entries: list[AIUsageEntry] | None = None,
    ai_usage_page: Path | None = None,
    ai_usage_stats: AIUsageStats | None = None,
    data_model_stats: DataModelCustomisationStats | None = None,
    adoption_stats: AdoptionStats | None = None,
    customisation_page: Path | None = None,
    adoption_page: Path | None = None,
    card_visibility: IndexCardVisibility | None = None,
) -> Path:
    path = output_dir / "index.html"
    write_text(
        path,
        render_index(
            snapshot,
            object_pages,
            apex_pages,
            flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_results,
            path,
            output_dir,
            assets_dir,
            omni_pages or {},
            analyzer_report,
            ai_usage_entries=ai_usage_entries,
            ai_usage_page=ai_usage_page,
            ai_usage_stats=ai_usage_stats,
            data_model_stats=data_model_stats,
            adoption_stats=adoption_stats,
            customisation_page=customisation_page,
            adoption_page=adoption_page,
            card_visibility=card_visibility,
        ),
    )
    log(f"Index genere: {path}")
    return path
