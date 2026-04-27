"""Render the dedicated ``adoption.html`` page.

Detailed view backing the *Posture Adopt vs Adapt* card on the index.
The page lists every capability of :data:`CAPABILITY_CATALOG`, the level
detected for the snapshot (Adopt / Adapt-Low / Adapt-High), the weight
and the evidence that drove the classification so the reader can audit
or contest the verdict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.customization_metrics import (
    AdoptionStats,
    CAPABILITY_CATALOG,
    CapabilityLevel,
)
from src.core.models import MetadataSnapshot
from src.core.utils import html_value, write_text

from src.reporting.html.page_shell import index_back_link, render_page


LogCallback = Callable[[str], None]


_LEVEL_TO_CSS = {
    CapabilityLevel.ADOPT: "adopt-level adopt-level--adopt",
    CapabilityLevel.ADAPT_LOW: "adopt-level adopt-level--low",
    CapabilityLevel.ADAPT_HIGH: "adopt-level adopt-level--high",
}


def write_adoption_page(
    snapshot: MetadataSnapshot,
    stats: AdoptionStats | None,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path:
    path = output_dir / "adoption.html"
    write_text(path, _render_page(stats, path, output_dir, assets_dir))
    log(f"Page Posture Adopt vs Adapt generee: {path}")
    return path


def _render_overview_cards(stats: AdoptionStats | None) -> str:
    if stats is None or stats.total_count == 0:
        return (
            '<div class="cards smallcards">'
            '<div class="card"><span>Posture Adopt vs Adapt</span>'
            '<span class="value">N/A</span></div>'
            "</div>"
        )
    return (
        '<div class="cards smallcards">'
        '<div class="card adopt-card adopt-card--adopt">'
        '<span>Adopt (OOTB)</span>'
        f'<span class="value">{stats.adopt_count}</span>'
        f'<span class="adopt-percent">{stats.percent_adoption:.1f} %</span>'
        "</div>"
        '<div class="card adopt-card adopt-card--low">'
        '<span>Adapt declaratif</span>'
        f'<span class="value">{stats.adapt_low_count}</span>'
        f'<span class="adopt-percent">{stats.percent_adapt_low:.1f} %</span>'
        "</div>"
        '<div class="card adopt-card adopt-card--high">'
        '<span>Adapt code</span>'
        f'<span class="value">{stats.adapt_high_count}</span>'
        f'<span class="adopt-percent">{stats.percent_adapt_high:.1f} %</span>'
        "</div>"
        '<div class="card"><span>Capacites evaluees</span>'
        f'<span class="value">{stats.total_count}</span>'
        f'<span class="adopt-percent">poids total {stats.total_weight}</span>'
        "</div>"
        "</div>"
    )


def _render_capability_table(stats: AdoptionStats | None) -> str:
    if stats is None or not stats.assessments:
        return "<p class='empty'>Aucune capacite evaluee.</p>"

    by_id = {a.capability_id: a for a in stats.assessments}
    rows: list[str] = []
    for definition in CAPABILITY_CATALOG:
        assessment = by_id.get(definition.capability_id)
        if assessment is None:
            continue
        css_class = _LEVEL_TO_CSS.get(
            assessment.level, "adopt-level adopt-level--adopt"
        )
        evidence = "<br>".join(html_value(line) for line in assessment.evidence) or "-"
        rows.append(
            "<tr>"
            f"<td>{html_value(assessment.label)}</td>"
            f"<td><span class='{css_class}'>"
            f"{html_value(assessment.level.value)}</span></td>"
            f"<td>{assessment.weight}</td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Capacite</th>"
        "<th>Niveau</th>"
        "<th>Poids</th>"
        "<th>Indices detectes</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_page(
    stats: AdoptionStats | None,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
) -> str:
    back_link = index_back_link(current_path, output_dir, "posture-adopt-vs-adapt")
    overview = _render_overview_cards(stats)
    table = _render_capability_table(stats)

    body = f"""
{back_link}
<h1>Posture Adopt vs Adapt</h1>
<p>Cette page evalue, pour chaque capacite Salesforce du catalogue
interne, si l'org est restee proche de l'<em>out-of-the-box</em>
(<strong>Adopt</strong>), si elle l'a etendue par configuration
declarative (<strong>Adapt declaratif</strong> : flows, validation
rules, FlexiPages, permission sets, reports custom, OmniStudio data
transforms, email alerts...) ou si elle a recu de l'extension par code
(<strong>Adapt code</strong> : Apex triggers, classes avec callout ou
async, LWC, OmniScripts, profile custom, Apex avec
<code>addError</code> ou <code>Messaging.sendEmail</code>...).</p>
<p>Le pourcentage d'adoption est calcule en agregant les poids des
capacites detectees comme <em>Adopt</em>, divise par le poids total des
9 capacites du catalogue (poids total 20). C'est cette ponderation qui
permet a la <em>Securite</em> ou au <em>Modele de donnees</em> de peser
plus que par exemple <em>OmniStudio</em>.</p>
{overview}
<h2>Detail par capacite</h2>
{table}
"""
    return render_page(
        "Posture Adopt vs Adapt",
        body,
        current_path,
        assets_dir,
        include_mermaid=False,
    )
