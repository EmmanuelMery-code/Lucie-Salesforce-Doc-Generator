"""Render the dedicated ``ai_usage.html`` page.

Lists every metadata element flagged by one of the configured AI tags
(``@IAgenerated``, ``@IAassisted``, custom tags configured by the user).
Each row records the element type, its qualified name, the matched tag
value, the source file and the matched line so reviewers can audit AI
contributions across the org.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.ai_usage import (
    AIUsageEntry,
    AIUsageStats,
    CustomElement,
    count_unique_elements,
)
from src.core.utils import html_value, write_text

from src.reporting.html.page_shell import index_back_link, render_page


LogCallback = Callable[[str], None]


def write_ai_usage_page(
    entries: list[AIUsageEntry],
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    tags: list[str] | None = None,
    stats: AIUsageStats | None = None,
) -> Path:
    """Write ``ai_usage.html`` and return its path.

    The file is generated even when ``entries`` is empty so the index card
    always has a valid hyperlink. The page lists the configured tags in a
    short header, the with/without-tag breakdown of the customisation
    universe and the detail of every tagged occurrence so reviewers can
    audit AI contributions across the org.
    """

    path = output_dir / "ai_usage.html"
    write_text(
        path,
        _render_page(entries, path, output_dir, assets_dir, tags or [], stats),
    )
    log(f"Page Usage IA generee: {path}")
    return path


def _render_coverage_cards(stats: AIUsageStats | None) -> list[str]:
    """Return the with/without-tag overview cards for the detail page."""

    if stats is None:
        return []
    return [
        '<div class="card ai-usage-stat ai-usage-stat--with">'
        '<span class="ai-usage-label">Avec tag IA</span>'
        f'<span class="value">{stats.with_tag_count}</span>'
        f'<span class="ai-usage-percent">{stats.percent_with_tag:.1f} %</span>'
        "</div>",
        '<div class="card ai-usage-stat ai-usage-stat--without">'
        '<span class="ai-usage-label">Sans tag IA</span>'
        f'<span class="value">{stats.without_tag_count}</span>'
        f'<span class="ai-usage-percent">{stats.percent_without_tag:.1f} %</span>'
        "</div>",
        '<div class="card"><span>Total customs / code / lowcode</span>'
        f'<span class="value">{stats.total}</span></div>',
    ]


def _render_universe_breakdown(stats: AIUsageStats | None) -> str:
    """Render a small table summarising tag coverage per element type."""

    if stats is None or not stats.universe:
        return ""

    per_type: dict[str, dict[str, int]] = {}
    for element in stats.universe:
        bucket = per_type.setdefault(
            element.element_type, {"total": 0, "with": 0, "without": 0}
        )
        bucket["total"] += 1
    tagged_keys = {(item.element_type, item.element_name) for item in stats.with_tag}
    for element in stats.universe:
        bucket = per_type[element.element_type]
        if (element.element_type, element.element_name) in tagged_keys:
            bucket["with"] += 1
        else:
            bucket["without"] += 1

    rows: list[str] = []
    for kind, bucket in sorted(per_type.items(), key=lambda kv: kv[0].lower()):
        total = bucket["total"]
        with_count = bucket["with"]
        without_count = bucket["without"]
        with_pct = (with_count / total * 100.0) if total else 0.0
        without_pct = (without_count / total * 100.0) if total else 0.0
        rows.append(
            "<tr>"
            f"<td>{html_value(kind)}</td>"
            f"<td>{total}</td>"
            f"<td>{with_count} <small>({with_pct:.1f} %)</small></td>"
            f"<td>{without_count} <small>({without_pct:.1f} %)</small></td>"
            "</tr>"
        )
    return (
        "<h2>Couverture par type d'element</h2>"
        "<table><thead><tr>"
        "<th>Type d'element</th>"
        "<th>Total</th>"
        "<th>Avec tag IA</th>"
        "<th>Sans tag IA</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_untagged_table(without_tag: list[CustomElement]) -> str:
    """Render the list of customisation items missing an AI tag."""

    if not without_tag:
        return (
            "<p class='empty'>Tous les elements customs portent un tag IA.</p>"
        )
    rows: list[str] = []
    for element in without_tag:
        rows.append(
            "<tr>"
            f"<td>{html_value(element.element_type)}</td>"
            f"<td>{html_value(element.element_name)}</td>"
            f"<td>{html_value(element.source)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Type d'element</th>"
        "<th>Element</th>"
        "<th>Source</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_page(
    entries: list[AIUsageEntry],
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    tags: list[str],
    stats: AIUsageStats | None,
) -> str:
    back_link = index_back_link(current_path, output_dir, "usage-ia")
    occurrences = len(entries)
    unique_elements = count_unique_elements(entries)
    tag_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for entry in entries:
        tag_counts[entry.tag] = tag_counts.get(entry.tag, 0) + 1
        type_counts[entry.element_type] = type_counts.get(entry.element_type, 0) + 1

    coverage_cards = _render_coverage_cards(stats)
    detail_cards: list[str] = [
        f'<div class="card"><span>Elements distincts</span>'
        f'<span class="value">{unique_elements}</span></div>',
        f'<div class="card"><span>Occurrences totales</span>'
        f'<span class="value">{occurrences}</span></div>',
    ]
    if tags:
        detail_cards.append(
            '<div class="card"><span>Tags suivis</span>'
            f'<span class="value">{html_value(", ".join(tags))}</span></div>'
        )

    type_breakdown = ""
    if type_counts:
        chips = "".join(
            f"<span class='chip'>{html_value(kind)} <strong>{count}</strong></span>"
            for kind, count in sorted(
                type_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())
            )
        )
        type_breakdown = (
            "<div class='findings-summary'>" + chips + "</div>"
        )

    if not entries:
        table = "<p class='empty'>Aucun element ne porte de tag IA.</p>"
    else:
        rows: list[str] = []
        for entry in entries:
            line_value = entry.line_number if entry.line_number else ""
            source_value = entry.source or ""
            rows.append(
                "<tr>"
                f"<td>{html_value(entry.element_type)}</td>"
                f"<td>{html_value(entry.element_name)}</td>"
                f"<td><code>{html_value(entry.tag)}</code></td>"
                f"<td>{html_value(entry.location)}</td>"
                f"<td>{html_value(source_value)}</td>"
                f"<td>{html_value(line_value)}</td>"
                f"<td>{html_value(entry.excerpt)}</td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr>"
            "<th>Type d'element</th>"
            "<th>Element</th>"
            "<th>Tag</th>"
            "<th>Emplacement</th>"
            "<th>Source</th>"
            "<th>Ligne</th>"
            "<th>Extrait</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    tag_summary = ""
    if entries and tag_counts:
        chips = "".join(
            f"<span class='chip'><code>{html_value(tag)}</code> "
            f"<strong>{count}</strong></span>"
            for tag, count in sorted(
                tag_counts.items(), key=lambda kv: (-kv[1], kv[0].lower())
            )
        )
        tag_summary = (
            "<h2>Repartition par tag</h2>"
            "<div class='findings-summary'>" + chips + "</div>"
        )

    coverage_section = ""
    untagged_section = ""
    if stats is not None:
        coverage_section = (
            '<h2>Couverture IA des elements customs</h2>'
            '<p>L\'univers evalue regroupe les objets customs, les champs '
            'customs, les record types des objets customs, les validation '
            'rules, les flows et les classes / triggers Apex.</p>'
            '<div class="cards smallcards">'
            f"{''.join(coverage_cards)}"
            '</div>'
            f'{_render_universe_breakdown(stats)}'
        )
        untagged_section = (
            '<h2>Elements customs sans tag IA</h2>'
            f'{_render_untagged_table(stats.without_tag)}'
        )

    body = f"""
{back_link}
<h1>Usage IA</h1>
<p>Cette page liste les elements de metadata dont la description ou les
commentaires contiennent l'un des tags configures dans l'ecran
<em>Configuration de l'application &gt; Tag : IA</em>, ainsi que la part
des elements customs qui n'ont pas encore ete annotes.</p>
{coverage_section}
<h2>Detail des occurrences</h2>
<div class="cards smallcards">
  {''.join(detail_cards)}
</div>
{type_breakdown}
{tag_summary}
{table}
{untagged_section}
"""
    return render_page(
        "Usage IA",
        body,
        current_path,
        assets_dir,
        include_mermaid=False,
    )
