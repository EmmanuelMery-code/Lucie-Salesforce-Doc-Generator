"""Render the per-flow documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import FlowInfo, MetadataSnapshot, ReviewResult
from src.core.utils import html_value, safe_slug, write_text

from src.reporting.html.dependencies import (
    build_flow_reference_index,
    flow_dependencies,
    render_component_dependency_graph,
    render_dependency_rows,
)
from src.reporting.html.findings import (
    findings_to_review_improvements,
    render_analyzer_tab,
    render_findings_summary,
)
from src.reporting.html.page_shell import (
    complexity_badge_class,
    index_back_link,
    list_or_empty,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_flow_page(
    flow: FlowInfo,
    review: ReviewResult,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    dependencies: list[dict[str, str]],
    flow_pages: dict[str, Path],
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    metrics = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
        for label, value in review.metrics
    )
    elements_rows = "".join(
        f"<tr><td>{html_value(element.element_type)}</td><td>{html_value(element.name)}</td>"
        f"<td>{html_value(element.label)}</td><td>{html_value(element.description)}</td><td>{html_value(element.target)}</td></tr>"
        for element in flow.elements
    ) or "<tr><td colspan='5' class='empty'>Aucun element detecte.</td></tr>"
    count_rows = "".join(
        f"<tr><td>{html_value(name)}</td><td>{count}</td></tr>"
        for name, count in sorted(flow.element_counts.items())
    ) or "<tr><td colspan='2' class='empty'>Aucun bloc detecte.</td></tr>"
    relation_rows = render_dependency_rows(
        dependencies,
        current_path,
        {"Flow": flow_pages, "Objet": object_pages, "Apex": apex_pages},
    )
    relation_graph = render_component_dependency_graph(flow.name, "Flow", dependencies, safe_slug(flow.name))
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    improvements_augmented = list(review.improvements) + findings_to_review_improvements(findings)
    summary_html = (
        f"<p>{html_value(review.summary)}</p>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    tabs = tabbed_sections(
        f"flow-{safe_slug(flow.name)}",
        [
            ("Resume", summary_html),
            ("Metriques", f"<ul>{metrics}</ul>"),
            ("Repartition", f"<table><thead><tr><th>Type</th><th>Nombre</th></tr></thead><tbody>{count_rows}</tbody></table>"),
            ("Points forts", list_or_empty(review.positives, "Aucun point fort automatique detecte.")),
            ("Heuristiques", list_or_empty(improvements_augmented, "Aucun point d'amelioration automatique detecte.")),
            ("Analyseur", analyzer_tab),
            (
                "Relations",
                f"<table><thead><tr><th>Composant lie</th><th>Categorie</th><th>Sous-type</th><th>Sens</th><th>Nature du lien</th></tr></thead><tbody>{relation_rows}</tbody></table>{relation_graph}",
            ),
            ("Elements", f"<table><thead><tr><th>Type</th><th>Nom</th><th>Label</th><th>Description</th><th>Cible</th></tr></thead><tbody>{elements_rows}</tbody></table>"),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "flows")}
<h1>{html_value(flow.name)}</h1>
<span class="badge">{html_value(flow.process_type or 'Flow')}</span>
<span class="badge {complexity_badge_class(flow.complexity_level)}">{html_value(flow.complexity_level)}</span>
<div class="cards smallcards">
  <div class="card"><span>Score complexite</span><span class="value">{flow.complexity_score}</span></div>
  <div class="card"><span>Elements</span><span class="value">{flow.total_elements}</span></div>
  <div class="card"><span>Documentes</span><span class="value">{flow.described_elements}</span></div>
  <div class="card"><span>Variables</span><span class="value">{flow.variable_total}</span></div>
  <div class="card"><span>Profondeur</span><span class="value">{flow.max_depth}</span></div>
  <div class="card"><span>Largeur max</span><span class="value">{flow.max_width}</span></div>
  <div class="card"><span>Hauteur min/max</span><span class="value">{flow.min_height}/{flow.max_height}</span></div>
</div>
{tabs}
"""
    return render_page(flow.name, body, current_path, assets_dir)


def write_flow_pages(
    snapshot: MetadataSnapshot,
    reviews: dict[str, ReviewResult],
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flows_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, Path]:
    flows = snapshot.flows
    output: dict[str, Path] = {}
    for flow in flows:
        path = flows_dir / f"{safe_slug(flow.name)}.html"
        output[flow.name] = path

    flow_bodies = {
        flow.name: flow.source_path.read_text(encoding="utf-8", errors="ignore")
        if flow.source_path and flow.source_path.exists()
        else ""
        for flow in flows
    }
    flow_ref_index = build_flow_reference_index(flows, flow_bodies)
    object_names = [item.api_name for item in snapshot.objects]
    apex_names = [item.name for item in snapshot.apex_artifacts]
    flow_findings = getattr(analyzer_report, "flows", {}) if analyzer_report else {}

    for flow in flows:
        path = output[flow.name]
        dependencies = flow_dependencies(
            flow,
            flow_ref_index,
            flow_bodies.get(flow.name, ""),
            object_names,
            apex_names,
        )
        write_text(
            path,
            render_flow_page(
                flow,
                reviews[flow.name],
                path,
                output_dir,
                assets_dir,
                dependencies,
                output,
                object_pages,
                apex_pages,
                flow_findings.get(flow.name, []),
            ),
        )
    log(f"{len(output)} page(s) Flow generee(s).")
    return output
