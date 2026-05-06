"""Render the per-Apex-class / per-trigger documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import (
    ApexArtifact,
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)
from src.core.utils import html_value, safe_slug, write_text

from src.reporting.html.dependencies import (
    apex_dependencies,
    build_apex_reference_index,
    render_apex_dependency_graph,
    render_apex_dependency_rows,
    trigger_object_name,
)
from src.reporting.html.findings import (
    findings_to_review_improvements,
    render_analyzer_tab,
    render_findings_summary,
    render_pmd_rows,
)
from src.reporting.html.page_shell import (
    index_back_link,
    list_or_empty,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_apex_page(
    artifact: ApexArtifact,
    review: ReviewResult,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    apex_pages: dict[str, Path],
    dependencies: list[dict[str, str]],
    pmd_violations: list[PmdViolation],
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    metrics = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
        for label, value in review.metrics
    )
    improvements_for_heuristics = list(review.improvements) + findings_to_review_improvements(findings)
    positives = list_or_empty(review.positives, "Aucun point fort automatique detecte.")
    improvements = list_or_empty(improvements_for_heuristics, "Aucun point d'amelioration automatique detecte.")
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    code_preview = "\n".join(artifact.body.splitlines()[:120])
    dependency_rows = render_apex_dependency_rows(dependencies, current_path, apex_pages)
    dependency_graph = render_apex_dependency_graph(artifact, dependencies)
    pmd_rows = render_pmd_rows(pmd_violations)
    summary_html = (
        f"<p>{html_value(review.summary)}</p>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    tabs = tabbed_sections(
        f"apex-{safe_slug(artifact.name)}",
        [
            ("Resume", summary_html),
            ("Metriques", f"<ul>{metrics}</ul>"),
            ("Points forts", positives),
            ("Heuristiques", improvements),
            ("Analyseur", analyzer_tab),
            (
                "PMD",
                f"<table><thead><tr><th>Regle</th><th>Ruleset</th><th>Priorite</th><th>Ligne</th><th>Message</th></tr></thead><tbody>{pmd_rows}</tbody></table>",
            ),
            (
                "Liens",
                f"<table><thead><tr><th>Composant lie</th><th>Categorie</th><th>Sous-type</th><th>Sens</th><th>Nature du lien</th></tr></thead><tbody>{dependency_rows}</tbody></table>",
            ),
            ("Graphe", dependency_graph),
            ("Extrait", f"<pre>{html_value(code_preview)}</pre>"),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "apex-trigger")}
<h1>{html_value(artifact.name)}</h1>
<span class="badge">{html_value(artifact.kind)}</span>
{tabs}
"""
    return render_page(artifact.name, body, current_path, assets_dir)


def write_apex_pages(
    snapshot: MetadataSnapshot,
    reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    apex_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, Path]:
    artifacts = snapshot.apex_artifacts
    output: dict[str, Path] = {}
    for artifact in artifacts:
        filename = f"{safe_slug(artifact.name)}.html"
        output[artifact.name] = apex_dir / filename

    reference_index = build_apex_reference_index(artifacts)
    trigger_objects = {artifact.name: trigger_object_name(artifact) for artifact in artifacts}
    object_names = [item.api_name for item in snapshot.objects]
    flow_names = [item.name for item in snapshot.flows]
    apex_findings = getattr(analyzer_report, "apex", {}) if analyzer_report else {}
    for artifact in artifacts:
        path = output[artifact.name]
        dependencies = apex_dependencies(
            artifact,
            artifacts,
            reference_index,
            trigger_objects,
            object_names,
            flow_names,
        )
        write_text(
            path,
            render_apex_page(
                artifact,
                reviews[artifact.name],
                path,
                output_dir,
                assets_dir,
                output,
                dependencies,
                pmd_results.get(artifact.name, []),
                apex_findings.get(artifact.name, []),
            ),
        )
    log(f"{len(output)} page(s) Apex/Trigger generee(s).")
    return output
