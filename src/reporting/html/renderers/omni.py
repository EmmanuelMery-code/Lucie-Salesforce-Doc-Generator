"""Render the per-OmniStudio component documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import MetadataSnapshot
from src.core.utils import html_value, safe_slug, write_text
from src.reporting.html_mermaid import (
    data_transform_mermaid,
    data_transform_meta,
    mermaid_label,
    wrap_mermaid_block,
)

from src.reporting.html.findings import (
    render_analyzer_tab,
    render_findings_summary,
)
from src.reporting.html.page_shell import (
    index_back_link,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


OMNI_SCORING_FOLDERS: dict[str, str] = {
    "omniscripts": "OmniScripts",
    "omniintegrationprocedures": "Integration Procedures",
    "omniuicard": "Omni UI Cards",
    "omnidatatransforms": "Data Transforms",
}


def render_omni_page(
    *,
    name: str,
    subcategory: str,
    row: dict[str, object],
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    source_rel = str(row.get("Source") or "")
    file_type = str(row.get("TypeFichier") or "")
    category_label = str(row.get("Categorie") or "OmniStudio")

    meta_rows = [
        ("Nom", name),
        ("Categorie", category_label),
        ("Sous-categorie", subcategory),
        ("Type de fichier", file_type),
        ("Source", source_rel or "Non renseigne"),
    ]
    meta_html = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value or 'Non renseigne')}</li>"
        for label, value in meta_rows
    )

    preview_html = "<p class='empty'>Aucun contenu source exploitable.</p>"
    if source_rel:
        candidate = snapshot.source_dir / source_rel
        if candidate.exists() and candidate.is_file():
            try:
                raw_text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                raw_text = ""
            if raw_text:
                lines = raw_text.splitlines()
                preview_lines = lines[:200]
                truncated = len(lines) > len(preview_lines)
                preview_body = "\n".join(preview_lines)
                suffix = "\n..." if truncated else ""
                preview_html = f"<pre>{html_value(preview_body + suffix)}</pre>"

    folder = str(row.get("Dossier") or "").lower()
    is_data_transform = (
        "omnidatatransform" in folder
        or file_type.lower().endswith(".rpt-meta.xml")
        or subcategory.lower().replace("-", " ").strip() == "data transforms"
    )

    data_transform_payload: tuple[str, dict[str, str]] | None = None
    if is_data_transform and source_rel:
        candidate = snapshot.source_dir / source_rel
        if candidate.exists() and candidate.is_file():
            try:
                xml_text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                xml_text = ""
            if xml_text:
                diagram_src = data_transform_mermaid(xml_text, name)
                if diagram_src:
                    data_transform_payload = (
                        diagram_src,
                        data_transform_meta(xml_text),
                    )

    if data_transform_payload is not None:
        diagram_src, dt_meta = data_transform_payload
        wrapped = wrap_mermaid_block(diagram_src)
        mermaid_graph = (
            "<div class=\"section\">"
            f"<h3>Transformation de donnees : {html_value(name)}</h3>"
            "<p class='empty'>"
            f"Type : <strong>{html_value(dt_meta.get('type') or 'Non renseigne')}</strong> - "
            f"entrees <strong>{html_value(dt_meta.get('inputType') or '-')}</strong> "
            f"=&gt; sorties <strong>{html_value(dt_meta.get('outputType') or '-')}</strong>"
            "</p>"
            f"{wrapped}"
            "</div>"
        )
    else:
        msg_name = mermaid_label(name) or "Composant"
        msg_type = mermaid_label(file_type) or "Type"
        msg_sub = mermaid_label(subcategory) or "Sous-categorie"
        msg_cat = mermaid_label(category_label) or "Categorie"

        diagram_lines = [
            "flowchart LR",
            f'    Comp["{msg_name}"]',
            f'    Type["Type : {msg_type}"]',
            f'    Sub["Sous-categorie : {msg_sub}"]',
            f'    Cat["Categorie : {msg_cat}"]',
            "    Comp --> Type",
            "    Comp --> Sub",
            "    Comp --> Cat",
        ]
        omni_diagram = "\n".join(diagram_lines)
        wrapped = wrap_mermaid_block(omni_diagram)
        mermaid_graph = (
            "<div class=\"section\">"
            "<h3>Representation Graphique (OmniStudio)</h3>"
            f"{wrapped}"
            "</div>"
        )

    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    synthesis_html = (
        f"<ul>{meta_html}</ul>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )

    tabs = tabbed_sections(
        f"omni-{safe_slug(subcategory)}-{safe_slug(name)}",
        [
            ("Synthese", synthesis_html),
            ("Graphique", mermaid_graph),
            ("Analyseur", analyzer_tab),
            ("Contenu", preview_html),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "omni")}
<h1>{html_value(name)}</h1>
<span class="badge">{html_value(category_label)}</span>
<span class="badge">{html_value(subcategory)}</span>
{tabs}
"""
    return render_page(name, body, current_path, assets_dir, include_mermaid=True)


def write_omni_pages(
    snapshot: MetadataSnapshot,
    omni_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, list[dict[str, object]]]:
    rows = snapshot.inventory.get("omnistudio") or []
    dt_findings = getattr(analyzer_report, "data_transforms", {}) if analyzer_report else {}
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        subcategory_raw = str(row.get("Dossier") or "").strip()
        label = OMNI_SCORING_FOLDERS.get(subcategory_raw.lower())
        if not label:
            continue
        grouped.setdefault(label, []).append(row)

    output: dict[str, list[dict[str, object]]] = {}
    total = 0
    for subcategory in sorted(grouped.keys(), key=lambda value: value.lower()):
        sub_slug = safe_slug(subcategory) or "autres"
        entries: list[dict[str, object]] = []
        used_slugs: set[str] = set()
        for row in sorted(grouped[subcategory], key=lambda item: str(item.get("Nom") or "").lower()):
            name = str(row.get("Nom") or "").strip() or "Sans nom"
            base_slug = safe_slug(name) or "composant"
            candidate_slug = base_slug
            counter = 2
            while candidate_slug in used_slugs:
                candidate_slug = f"{base_slug}-{counter}"
                counter += 1
            used_slugs.add(candidate_slug)

            page_path = omni_dir / sub_slug / f"{candidate_slug}.html"
            source_rel = str(row.get("Source") or "")
            content = render_omni_page(
                name=name,
                subcategory=subcategory,
                row=row,
                snapshot=snapshot,
                current_path=page_path,
                output_dir=output_dir,
                assets_dir=assets_dir,
                findings=dt_findings.get(name, []),
            )
            write_text(page_path, content)
            entries.append(
                {
                    "name": name,
                    "page": page_path,
                    "source": source_rel,
                    "type": str(row.get("TypeFichier") or ""),
                }
            )
            total += 1
        output[subcategory] = entries

    log(f"{total} page(s) OmniStudio generee(s).")
    return output
