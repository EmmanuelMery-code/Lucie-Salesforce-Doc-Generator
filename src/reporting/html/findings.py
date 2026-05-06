"""Render analyzer findings, PMD violations and per-object security tables.

These helpers turn the typed dataclasses produced by the analyzer and the
metadata parser into the small HTML fragments embedded in the per-page
"Analyseur" / "PMD" / "Profiles" tabs.
"""

from __future__ import annotations

from src.analyzer.models import Finding
from src.core.models import PmdViolation, SecurityArtifact
from src.core.utils import html_value

from src.reporting.html.assets import SEVERITY_CSS_CLASS, SEVERITY_LABEL


def security_rows(
    artifacts: list[SecurityArtifact],
    object_name: str,
) -> list[dict[str, object]]:
    """Compute the read/create/edit/delete + visible/editable field counts
    granted by each ``artifact`` (profile or permission set) on ``object_name``.
    Returns one row per artifact that actually grants something.
    """

    rows: list[dict[str, object]] = []
    prefix = f"{object_name}."
    for artifact in artifacts:
        permission = next(
            (item for item in artifact.object_permissions if item.object_name == object_name),
            None,
        )
        visible_fields = sum(
            1
            for item in artifact.field_permissions
            if item.field_name.startswith(prefix) and item.readable
        )
        editable_fields = sum(
            1
            for item in artifact.field_permissions
            if item.field_name.startswith(prefix) and item.editable
        )
        if permission or visible_fields or editable_fields:
            rows.append(
                {
                    "name": artifact.name,
                    "read": "Oui" if permission and permission.allow_read else "Non",
                    "create": "Oui" if permission and permission.allow_create else "Non",
                    "edit": "Oui" if permission and permission.allow_edit else "Non",
                    "delete": "Oui" if permission and permission.allow_delete else "Non",
                    "visible_fields": visible_fields,
                    "editable_fields": editable_fields,
                }
            )
    return rows


def render_security_rows(rows: list[dict[str, object]], empty_text: str) -> str:
    """Render the rows produced by :func:`security_rows` as a ``<tr>`` list."""

    if not rows:
        return f"<tr><td colspan='7' class='empty'>{html_value(empty_text)}</td></tr>"
    return "".join(
        f"<tr><td>{html_value(row['name'])}</td><td>{html_value(row['read'])}</td>"
        f"<td>{html_value(row['create'])}</td><td>{html_value(row['edit'])}</td>"
        f"<td>{html_value(row['delete'])}</td><td>{html_value(row['visible_fields'])}</td>"
        f"<td>{html_value(row['editable_fields'])}</td></tr>"
        for row in rows
    )


def render_pmd_rows(violations: list[PmdViolation]) -> str:
    """Render PMD ``violations`` as a per-rule ``<tr>`` list."""

    if not violations:
        return "<tr><td colspan='5' class='empty'>Aucune violation PMD detectee.</td></tr>"
    rows = []
    for violation in violations:
        line_display = (
            f"{violation.begin_line}-{violation.end_line}"
            if violation.begin_line and violation.end_line and violation.end_line != violation.begin_line
            else str(violation.begin_line or "")
        )
        rows.append(
            f"<tr><td>{html_value(violation.rule)}</td><td>{html_value(violation.ruleset)}</td>"
            f"<td>{html_value(violation.priority)}</td><td>{html_value(line_display)}</td>"
            f"<td>{html_value(violation.message)}</td></tr>"
        )
    return "".join(rows)


def render_findings_summary(findings: list[Finding]) -> str:
    """Render the per-severity chip summary above each "Analyseur" tab."""

    if not findings:
        return "<p class='empty'>Aucun point d'alerte detecte par l'analyseur.</p>"
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.rule.severity] = counts.get(finding.rule.severity, 0) + 1
    chips = []
    for severity in ("Critical", "Major", "Minor", "Info"):
        if counts.get(severity):
            css = SEVERITY_CSS_CLASS.get(severity, "")
            label = SEVERITY_LABEL.get(severity, severity)
            chips.append(
                f"<span class='chip {css}'><strong>{counts[severity]}</strong> {html_value(label)}</span>"
            )
    return "<div class='findings-summary'>" + "".join(chips) + "</div>"


def render_findings_list(findings: list[Finding]) -> str:
    """Render the long-form ``<ul>`` of findings used inside "Analyseur" tabs."""

    if not findings:
        return "<p class='empty'>Aucun point d'alerte detecte par l'analyseur.</p>"
    items: list[str] = []
    for finding in findings:
        rule = finding.rule
        severity_css = SEVERITY_CSS_CLASS.get(rule.severity, "sev-info")
        severity_label = SEVERITY_LABEL.get(rule.severity, rule.severity)
        reference = ""
        if rule.reference:
            reference = (
                f"<dt>Reference:</dt><dd><a href='{html_value(rule.reference)}' target='_blank' rel='noopener'>{html_value(rule.reference)}</a></dd>"
            )
        details_html = ""
        if finding.details:
            detail_items = "".join(
                f"<li>{html_value(detail)}</li>" for detail in finding.details
            )
            details_html = f"<ul class='details'>{detail_items}</ul>"
        subcat = f" - {html_value(rule.subcategory)}" if rule.subcategory else ""
        items.append(
            "<li class='finding'>"
            "<div class='head'>"
            f"<span class='sev-badge {severity_css}'>{html_value(severity_label)}</span>"
            f"<span class='category-badge'>{html_value(rule.category)}{subcat}</span>"
            f"<span class='rule-id'>{html_value(rule.id)}</span>"
            f"<span class='title'>{html_value(rule.title)}</span>"
            "</div>"
            f"<div class='message'>{html_value(finding.message or rule.description)}</div>"
            "<dl class='metadata'>"
            f"<dt>Justification:</dt><dd>{html_value(rule.rationale)}</dd>"
            f"<dt>Remediation:</dt><dd>{html_value(rule.remediation)}</dd>"
            f"<dt>Source:</dt><dd>{html_value(rule.source)}</dd>"
            f"{reference}"
            "</dl>"
            f"{details_html}"
            "</li>"
        )
    return "<ul class='findings-list'>" + "".join(items) + "</ul>"


def findings_to_review_improvements(findings: list[Finding]) -> list[str]:
    """Convert ``findings`` into one-line strings suitable for the review tab."""

    lines: list[str] = []
    for finding in findings:
        severity_label = SEVERITY_LABEL.get(finding.rule.severity, finding.rule.severity)
        lines.append(
            f"[{severity_label}] {finding.rule.id} - {finding.rule.title} : {finding.message or finding.rule.description}"
        )
    return lines


def render_analyzer_tab(findings: list[Finding]) -> str:
    """Render the full Analyseur tab body (summary + long list + footer note)."""

    summary = render_findings_summary(findings)
    body = render_findings_list(findings)
    note = (
        "<p class='empty'>Regles inspirees de PMD Apex, du Salesforce Well-Architected Framework et des guides "
        "Salesforce Architects / Admins. Chaque regle peut etre activee ou desactivee dans "
        "<code>src/analyzer/rules.xml</code>.</p>"
    )
    return summary + body + note
