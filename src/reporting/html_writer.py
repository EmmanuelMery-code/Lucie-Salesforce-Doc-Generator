from __future__ import annotations

import json
import os
from pathlib import Path
import re

from src.core.models import (
    ApexArtifact,
    FlowInfo,
    MetadataSnapshot,
    ObjectInfo,
    ReviewResult,
    SecurityArtifact,
)
from src.core.utils import html_value, safe_slug, write_text


class HtmlReportWriter:
    def __init__(self, output_dir: str | Path, log_callback=None) -> None:
        self.output_dir = Path(output_dir)
        self.log = log_callback or (lambda message: None)
        self.assets_dir = self.output_dir / "assets"
        self.objects_dir = self.output_dir / "objects"
        self.apex_dir = self.output_dir / "apex"
        self.flows_dir = self.output_dir / "flows"

    def write_assets(self) -> None:
        style = """
body { font-family: Arial, sans-serif; margin: 0; color: #1f2937; background: #f8fafc; }
.page { max-width: 1400px; margin: 0 auto; padding: 24px; }
.topnav { margin-bottom: 20px; }
.topnav a { text-decoration: none; color: #1d4ed8; }
h1, h2, h3 { color: #0f172a; }
.cards { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0 24px; }
.card { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; min-width: 180px; }
.card .value { display: block; font-size: 1.6rem; font-weight: bold; margin-top: 8px; }
table { width: 100%; border-collapse: collapse; background: white; margin: 12px 0 24px; }
th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; }
th { background: #dbeafe; }
tr:nth-child(even) td { background: #f8fbff; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #dbeafe; color: #1e3a8a; }
.badge.complexity-simple { background: #dcfce7; color: #166534; }
.badge.complexity-medium { background: #fef3c7; color: #92400e; }
.badge.complexity-complex { background: #fed7aa; color: #9a3412; }
.badge.complexity-very-complex { background: #fecaca; color: #991b1b; }
.section { margin-bottom: 28px; }
ul { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px 32px; }
.empty { color: #64748b; font-style: italic; }
.mermaid { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; overflow: auto; }
code { background: #e2e8f0; padding: 2px 4px; border-radius: 4px; }
.smallcards .card { min-width: 150px; }
.graph-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.graph-toolbar button { border: 1px solid #cbd5e1; background: #f8fafc; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
.graph-toolbar button:hover { background: #e2e8f0; }
.graph-filters { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 10px; }
.graph-filters label { display: inline-flex; align-items: center; gap: 6px; font-size: 0.92rem; color: #334155; }
.dependency-graph { height: 440px; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; }
.graph-legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 12px; }
.graph-legend .item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.9rem; }
.graph-legend .dot { width: 12px; height: 12px; border-radius: 999px; border: 1px solid #64748b; display: inline-block; }
.tabs { background: white; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }
.tab-buttons { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px; border-bottom: 1px solid #cbd5e1; background: #f8fafc; }
.tab-button { border: 1px solid #cbd5e1; border-radius: 999px; background: white; color: #334155; padding: 6px 12px; cursor: pointer; }
.tab-button.active { background: #dbeafe; color: #1e3a8a; border-color: #93c5fd; }
.tab-panel { display: none; padding: 14px; }
.tab-panel.active { display: block; }
        """.strip()
        write_text(self.assets_dir / "style.css", style)

    def write_object_pages(self, snapshot: MetadataSnapshot) -> dict[str, Path]:
        output: dict[str, Path] = {}
        for item in snapshot.objects:
            path = self.objects_dir / f"{item.api_name}.html"
            content = self._render_object_page(item, snapshot, path)
            write_text(path, content)
            output[item.api_name] = path
        self.log(f"{len(output)} page(s) objet generee(s).")
        return output

    def write_apex_pages(
        self, snapshot: MetadataSnapshot, reviews: dict[str, ReviewResult]
    ) -> dict[str, Path]:
        artifacts = snapshot.apex_artifacts
        output: dict[str, Path] = {}
        for artifact in artifacts:
            filename = f"{safe_slug(artifact.name)}.html"
            output[artifact.name] = self.apex_dir / filename

        reference_index = self._build_apex_reference_index(artifacts)
        trigger_objects = {artifact.name: self._trigger_object_name(artifact) for artifact in artifacts}
        object_names = [item.api_name for item in snapshot.objects]
        flow_names = [item.name for item in snapshot.flows]
        for artifact in artifacts:
            path = output[artifact.name]
            dependencies = self._apex_dependencies(
                artifact,
                artifacts,
                reference_index,
                trigger_objects,
                object_names,
                flow_names,
            )
            write_text(
                path,
                self._render_apex_page(
                    artifact,
                    reviews[artifact.name],
                    path,
                    output,
                    dependencies,
                ),
            )
        self.log(f"{len(output)} page(s) Apex/Trigger generee(s).")
        return output

    def write_flow_pages(
        self,
        snapshot: MetadataSnapshot,
        reviews: dict[str, ReviewResult],
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
    ) -> dict[str, Path]:
        flows = snapshot.flows
        output: dict[str, Path] = {}
        for flow in flows:
            path = self.flows_dir / f"{safe_slug(flow.name)}.html"
            output[flow.name] = path

        flow_bodies = {
            flow.name: flow.source_path.read_text(encoding="utf-8", errors="ignore")
            if flow.source_path and flow.source_path.exists()
            else ""
            for flow in flows
        }
        flow_ref_index = self._build_flow_reference_index(flows, flow_bodies)
        object_names = [item.api_name for item in snapshot.objects]
        apex_names = [item.name for item in snapshot.apex_artifacts]

        for flow in flows:
            path = output[flow.name]
            dependencies = self._flow_dependencies(
                flow,
                flow_ref_index,
                flow_bodies.get(flow.name, ""),
                object_names,
                apex_names,
            )
            write_text(
                path,
                self._render_flow_page(
                    flow,
                    reviews[flow.name],
                    path,
                    dependencies,
                    output,
                    object_pages,
                    apex_pages,
                ),
            )
        self.log(f"{len(output)} page(s) Flow generee(s).")
        return output

    def write_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        apex_reviews: dict[str, ReviewResult],
        flow_reviews: dict[str, ReviewResult],
    ) -> Path:
        path = self.output_dir / "index.html"
        write_text(
            path,
            self._render_index(
                snapshot,
                object_pages,
                apex_pages,
                flow_pages,
                apex_reviews,
                flow_reviews,
                path,
            ),
        )
        self.log(f"Index genere: {path}")
        return path

    def _render_object_page(self, item: ObjectInfo, snapshot: MetadataSnapshot, current_path: Path) -> str:
        profiles = self._security_rows(snapshot.profiles, item.api_name)
        permsets = self._security_rows(snapshot.permission_sets, item.api_name)
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

        mermaid = self._object_mermaid(item)
        relation_table = "".join(
            f"<tr><td>{html_value(rel.field_name)}</td><td>{html_value(rel.relationship_type)}</td>"
            f"<td>{html_value(', '.join(rel.targets))}</td></tr>"
            for rel in item.relationships
        ) or "<tr><td colspan='3' class='empty'>Aucune relation detectee.</td></tr>"

        profile_rows = self._render_security_rows(profiles, "Aucun profil avec acces detecte.")
        permset_rows = self._render_security_rows(permsets, "Aucun permission set avec acces detecte.")

        tabs = self._tabbed_sections(
            f"object-{safe_slug(item.api_name)}",
            [
                ("Synthese", "<ul>" + description_html + "</ul>"),
                ("Fields", f"<table><thead><tr><th>Name</th><th>Label</th><th>Type</th><th>Description</th><th>Required</th></tr></thead><tbody>{fields_rows}</tbody></table>"),
                ("Profiles", f"<table><thead><tr><th>Profile</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{profile_rows}</tbody></table>"),
                ("Permission Sets", f"<table><thead><tr><th>Permission Set</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{permset_rows}</tbody></table>"),
                ("Record Types", f"<table><thead><tr><th>Nom</th><th>Label</th><th>Description</th><th>Actif</th></tr></thead><tbody>{record_type_rows}</tbody></table>"),
                ("Relations", f"{mermaid}<table><thead><tr><th>Champ</th><th>Type</th><th>Cible</th></tr></thead><tbody>{relation_table}</tbody></table>"),
            ],
        )
        body = f"""
<div class="topnav"><a href="{self._href(current_path, self.output_dir / 'index.html')}">Retour a l'index</a></div>
<h1>{html_value(item.api_name)}</h1>
<div class="cards">
  <div class="card"><span>Champs</span><span class="value">{len(item.fields)}</span></div>
  <div class="card"><span>Record types</span><span class="value">{len(item.record_types)}</span></div>
  <div class="card"><span>Regles de validation</span><span class="value">{len(item.validation_rules)}</span></div>
  <div class="card"><span>Relations</span><span class="value">{len(item.relationships)}</span></div>
</div>
{tabs}
"""
        return self._page(item.api_name, body, current_path)

    def _render_apex_page(
        self,
        artifact: ApexArtifact,
        review: ReviewResult,
        current_path: Path,
        apex_pages: dict[str, Path],
        dependencies: list[dict[str, str]],
    ) -> str:
        metrics = "".join(
            f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
            for label, value in review.metrics
        )
        positives = self._list_or_empty(review.positives, "Aucun point fort automatique detecte.")
        improvements = self._list_or_empty(review.improvements, "Aucun point d'amelioration automatique detecte.")
        code_preview = "\n".join(artifact.body.splitlines()[:120])
        dependency_rows = self._render_apex_dependency_rows(dependencies, current_path, apex_pages)
        dependency_graph = self._render_apex_dependency_graph(artifact, dependencies)
        tabs = self._tabbed_sections(
            f"apex-{safe_slug(artifact.name)}",
            [
                ("Resume", f"<p>{html_value(review.summary)}</p>"),
                ("Metriques", f"<ul>{metrics}</ul>"),
                ("Points forts", positives),
                ("Ameliorations", improvements),
                (
                    "Liens",
                    f"<table><thead><tr><th>Composant lie</th><th>Categorie</th><th>Sous-type</th><th>Sens</th><th>Nature du lien</th></tr></thead><tbody>{dependency_rows}</tbody></table>",
                ),
                ("Graphe", dependency_graph),
                ("Extrait", f"<pre>{html_value(code_preview)}</pre>"),
            ],
        )
        body = f"""
<div class="topnav"><a href="{self._href(current_path, self.output_dir / 'index.html')}">Retour a l'index</a></div>
<h1>{html_value(artifact.name)}</h1>
<span class="badge">{html_value(artifact.kind)}</span>
{tabs}
"""
        return self._page(artifact.name, body, current_path)

    def _render_flow_page(
        self,
        flow: FlowInfo,
        review: ReviewResult,
        current_path: Path,
        dependencies: list[dict[str, str]],
        flow_pages: dict[str, Path],
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
    ) -> str:
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
        relation_rows = self._render_dependency_rows(
            dependencies,
            current_path,
            {"Flow": flow_pages, "Objet": object_pages, "Apex": apex_pages},
        )
        relation_graph = self._render_component_dependency_graph(flow.name, "Flow", dependencies, safe_slug(flow.name))
        tabs = self._tabbed_sections(
            f"flow-{safe_slug(flow.name)}",
            [
                ("Resume", f"<p>{html_value(review.summary)}</p>"),
                ("Metriques", f"<ul>{metrics}</ul>"),
                ("Repartition", f"<table><thead><tr><th>Type</th><th>Nombre</th></tr></thead><tbody>{count_rows}</tbody></table>"),
                ("Points forts", self._list_or_empty(review.positives, "Aucun point fort automatique detecte.")),
                ("Ameliorations", self._list_or_empty(review.improvements, "Aucun point d'amelioration automatique detecte.")),
                (
                    "Relations",
                    f"<table><thead><tr><th>Composant lie</th><th>Categorie</th><th>Sous-type</th><th>Sens</th><th>Nature du lien</th></tr></thead><tbody>{relation_rows}</tbody></table>{relation_graph}",
                ),
                ("Elements", f"<table><thead><tr><th>Type</th><th>Nom</th><th>Label</th><th>Description</th><th>Cible</th></tr></thead><tbody>{elements_rows}</tbody></table>"),
            ],
        )
        body = f"""
<div class="topnav"><a href="{self._href(current_path, self.output_dir / 'index.html')}">Retour a l'index</a></div>
<h1>{html_value(flow.name)}</h1>
<span class="badge">{html_value(flow.process_type or 'Flow')}</span>
<span class="badge {self._complexity_badge_class(flow.complexity_level)}">{html_value(flow.complexity_level)}</span>
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
        return self._page(flow.name, body, current_path)

    def _render_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
        apex_reviews: dict[str, ReviewResult],
        flow_reviews: dict[str, ReviewResult],
        current_path: Path,
    ) -> str:
        metrics = snapshot.metrics
        object_rows = "".join(
            f"<tr><td><a href='{self._href(current_path, object_pages[item.api_name])}'>{html_value(item.api_name)}</a></td>"
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
            f"<tr><td><a href='{self._href(current_path, apex_pages[item.name])}'>{html_value(item.name)}</a></td>"
            f"<td>{html_value(item.kind)}</td><td>{item.line_count}</td><td>{item.method_count}</td></tr>"
            for item in snapshot.apex_artifacts
            if item.name in apex_pages
        ) or "<tr><td colspan='4' class='empty'>Aucun artefact Apex analyse.</td></tr>"

        flow_rows = "".join(
            f"<tr><td><a href='{self._href(current_path, flow_pages[item.name])}'>{html_value(item.name)}</a></td>"
            f"<td>{html_value(item.process_type)}</td><td>{html_value(item.complexity_level)}</td><td>{item.complexity_score}</td><td>{item.total_elements}</td><td>{item.described_elements}</td></tr>"
            for item in snapshot.flows
            if item.name in flow_pages
        ) or "<tr><td colspan='6' class='empty'>Aucun flow analyse.</td></tr>"

        improvements_rows = self._render_index_improvements(
            snapshot,
            apex_reviews,
            flow_reviews,
            current_path,
            apex_pages,
            flow_pages,
        )
        excel_links = self._render_excel_exports(current_path)

        tabs = self._tabbed_sections(
            "index",
            [
                (
                    "Exports Excel",
                    excel_links,
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
                    "Ameliorations",
                    f"<table><thead><tr><th>Type</th><th>Composant</th><th>Amelioration</th></tr></thead><tbody>{improvements_rows}</tbody></table>",
                ),
            ],
        )
        body = f"""
<h1>Documentation Salesforce</h1>
<p>Source analysee: <code>{html_value(snapshot.source_dir)}</code></p>
<div class="cards">
  <div class="card"><span>Niveau de customisation</span><span class="value">{html_value(metrics.level)}</span></div>
  <div class="card"><span>Score</span><span class="value">{metrics.score}</span></div>
  <div class="card"><span>Objets custom</span><span class="value">{metrics.custom_objects}</span></div>
  <div class="card"><span>Champs custom</span><span class="value">{metrics.custom_fields}</span></div>
  <div class="card"><span>Flows</span><span class="value">{metrics.flows}</span></div>
  <div class="card"><span>Classes / Triggers</span><span class="value">{metrics.apex_classes + metrics.apex_triggers}</span></div>
</div>
{tabs}
"""
        return self._page("Index", body, current_path, include_mermaid=False)

    def _render_excel_exports(self, current_path: Path) -> str:
        excel_dir = self.output_dir / "excel"
        if not excel_dir.exists():
            return "<p class='empty'>Aucun export Excel detecte.</p>"

        files = sorted(excel_dir.glob("*.xlsx"), key=lambda path: path.name.lower())
        if not files:
            return "<p class='empty'>Aucun export Excel detecte.</p>"

        items = []
        for file_path in files:
            href = self._href(current_path, file_path)
            items.append(f"<li><a href='{href}'>{html_value(file_path.name)}</a></li>")
        return "<ul>" + "".join(items) + "</ul>"

    def _render_index_improvements(
        self,
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
                component = f"<a href='{self._href(current_path, page)}'>{html_value(artifact.name)}</a>"
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
                component = f"<a href='{self._href(current_path, page)}'>{html_value(flow.name)}</a>"
            else:
                component = html_value(flow.name)
            for improvement in review.improvements:
                rows.append(
                    f"<tr><td>Flow</td><td>{component}</td><td>{html_value(improvement)}</td></tr>"
                )

        return "".join(rows) or "<tr><td colspan='3' class='empty'>Aucune amelioration detectee.</td></tr>"

    def _security_rows(self, artifacts: list[SecurityArtifact], object_name: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        prefix = f"{object_name}."
        for artifact in artifacts:
            permission = next(
                (item for item in artifact.object_permissions if item.object_name == object_name),
                None,
            )
            visible_fields = sum(1 for item in artifact.field_permissions if item.field_name.startswith(prefix) and item.readable)
            editable_fields = sum(1 for item in artifact.field_permissions if item.field_name.startswith(prefix) and item.editable)
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

    def _render_security_rows(self, rows: list[dict[str, object]], empty_text: str) -> str:
        if not rows:
            return f"<tr><td colspan='7' class='empty'>{html_value(empty_text)}</td></tr>"
        return "".join(
            f"<tr><td>{html_value(row['name'])}</td><td>{html_value(row['read'])}</td>"
            f"<td>{html_value(row['create'])}</td><td>{html_value(row['edit'])}</td>"
            f"<td>{html_value(row['delete'])}</td><td>{html_value(row['visible_fields'])}</td>"
            f"<td>{html_value(row['editable_fields'])}</td></tr>"
            for row in rows
        )

    def _object_mermaid(self, item: ObjectInfo) -> str:
        if not item.relationships:
            return "<p class='empty'>Aucune relation detectee.</p>"

        root_id = "n0"
        lines = ["flowchart TD", f'    {root_id}["{self._mermaid_label(item.api_name)}"]']
        target_ids: dict[str, str] = {}
        node_counter = 1

        for relationship in item.relationships:
            for target in relationship.targets:
                label = self._mermaid_label(target or "Cible inconnue")
                if label not in target_ids:
                    target_ids[label] = f"n{node_counter}"
                    node_counter += 1
                    lines.append(f'    {target_ids[label]}["{label}"]')
                # Keep edges simple for Mermaid robustness; details remain in relation table.
                lines.append(f"    {root_id} --> {target_ids[label]}")
        diagram = "\n".join(lines)
        return f"""
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true }});
</script>
<div class="mermaid">{diagram}</div>
"""

    def _mermaid_id(self, value: str) -> str:
        slug = safe_slug(value).replace("-", "_")
        if not slug:
            slug = "node"
        if not slug[0].isalpha():
            slug = f"n_{slug}"
        return slug

    def _mermaid_label(self, value: str) -> str:
        return (
            str(value)
            .replace('"', "'")
            .replace("|", "/")
            .replace("<", "(")
            .replace(">", ")")
            .replace("&", "et")
            .replace("\n", " ")
        )

    def _list_or_empty(self, items: list[str], empty_text: str) -> str:
        if not items:
            return f"<p class='empty'>{html_value(empty_text)}</p>"
        return "<ul>" + "".join(f"<li>{html_value(item)}</li>" for item in items) + "</ul>"

    def _complexity_badge_class(self, level: str) -> str:
        mapping = {
            "Simple": "complexity-simple",
            "Moyen": "complexity-medium",
            "Complexe": "complexity-complex",
            "Tres complexe": "complexity-very-complex",
        }
        return mapping.get(level, "")

    def _build_apex_reference_index(self, artifacts: list[ApexArtifact]) -> dict[str, set[str]]:
        references: dict[str, set[str]] = {}
        patterns = {
            artifact.name: re.compile(rf"\b{re.escape(artifact.name)}\b", re.IGNORECASE)
            for artifact in artifacts
        }
        for source in artifacts:
            linked: set[str] = set()
            for target in artifacts:
                if target.name == source.name:
                    continue
                if patterns[target.name].search(source.body):
                    linked.add(target.name)
            references[source.name] = linked
        return references

    def _trigger_object_name(self, artifact: ApexArtifact) -> str:
        if artifact.kind != "trigger":
            return ""
        match = re.search(r"(?im)^\s*trigger\s+\w+\s+on\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", artifact.body)
        return match.group(1) if match else ""

    def _apex_dependencies(
        self,
        artifact: ApexArtifact,
        artifacts: list[ApexArtifact],
        reference_index: dict[str, set[str]],
        trigger_objects: dict[str, str],
        object_names: list[str],
        flow_names: list[str],
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        by_name = {item.name: item for item in artifacts}
        seen: set[tuple[str, str, str, str]] = set()

        for target_name in sorted(reference_index.get(artifact.name, set()), key=str.lower):
            target = by_name.get(target_name)
            if target is None:
                continue
            key = (target_name, "Sortant", "Reference code", "Apex")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": target_name,
                    "category": "Apex",
                    "subtype": target.kind,
                    "direction": "Sortant",
                    "relation": "Reference code",
                }
            )

        for source_name, targets in reference_index.items():
            if source_name == artifact.name or artifact.name not in targets:
                continue
            source = by_name.get(source_name)
            if source is None:
                continue
            key = (source_name, "Entrant", "Reference code", "Apex")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": source_name,
                    "category": "Apex",
                    "subtype": source.kind,
                    "direction": "Entrant",
                    "relation": "Reference code",
                }
            )

        if artifact.kind == "trigger":
            current_object = trigger_objects.get(artifact.name, "")
            if current_object:
                for target in artifacts:
                    if target.name == artifact.name or target.kind != "trigger":
                        continue
                    if trigger_objects.get(target.name) != current_object:
                        continue
                    key = (target.name, "Sortant", f"Meme objet trigger ({current_object})", "Apex")
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "name": target.name,
                            "category": "Apex",
                            "subtype": target.kind,
                            "direction": "Sortant",
                            "relation": f"Meme objet trigger ({current_object})",
                        }
                    )

        for object_name in sorted(object_names, key=str.lower):
            if not re.search(rf"\b{re.escape(object_name)}\b", artifact.body):
                continue
            key = (object_name, "Sortant", "Usage objet", "Objet")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": object_name,
                    "category": "Objet",
                    "subtype": "sObject",
                    "direction": "Sortant",
                    "relation": "Usage objet",
                }
            )

        for flow_name in sorted(flow_names, key=str.lower):
            if not re.search(rf"\b{re.escape(flow_name)}\b", artifact.body):
                continue
            key = (flow_name, "Sortant", "Reference flow", "Flow")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": flow_name,
                    "category": "Flow",
                    "subtype": "Flow",
                    "direction": "Sortant",
                    "relation": "Reference flow",
                }
            )

        metadata_matches = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*__mdt)\b", artifact.body)))
        for metadata_name in metadata_matches:
            key = (metadata_name, "Sortant", "Reference metadata", "Metadata")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": metadata_name,
                    "category": "Metadata",
                    "subtype": "CustomMetadata",
                    "direction": "Sortant",
                    "relation": "Reference metadata",
                }
            )

        rows.sort(key=lambda item: (item["category"], item["direction"], item["name"].lower()))
        return rows

    def _render_apex_dependency_rows(
        self,
        rows: list[dict[str, str]],
        current_path: Path,
        apex_pages: dict[str, Path],
    ) -> str:
        return self._render_dependency_rows(rows, current_path, {"Apex": apex_pages})

    def _render_apex_dependency_graph(
        self,
        artifact: ApexArtifact,
        rows: list[dict[str, str]],
    ) -> str:
        return self._render_component_dependency_graph(artifact.name, "Apex", rows, safe_slug(artifact.name))

    def _render_dependency_rows(
        self,
        rows: list[dict[str, str]],
        current_path: Path,
        link_maps: dict[str, dict[str, Path]],
    ) -> str:
        if not rows:
            return "<tr><td colspan='5' class='empty'>Aucun lien detecte.</td></tr>"

        rendered_rows: list[str] = []
        for row in rows:
            target_path = link_maps.get(row["category"], {}).get(row["name"])
            if target_path:
                name_html = (
                    f"<a href='{self._href(current_path, target_path)}'>{html_value(row['name'])}</a>"
                )
            else:
                name_html = html_value(row["name"])
            rendered_rows.append(
                f"<tr><td>{name_html}</td><td>{html_value(row['category'])}</td><td>{html_value(row['subtype'])}</td>"
                f"<td>{html_value(row['direction'])}</td><td>{html_value(row['relation'])}</td></tr>"
            )
        return "".join(rendered_rows)

    def _render_component_dependency_graph(
        self,
        center_name: str,
        center_category: str,
        rows: list[dict[str, str]],
        key_suffix: str,
    ) -> str:
        if not rows:
            return "<p class='empty'>Aucun graphe a afficher, aucun lien n'a ete detecte.</p>"

        nodes: dict[str, dict[str, object]] = {
            center_name: {
                "id": center_name,
                "label": center_name,
                "title": f"{center_category}: {center_name}",
                "color": {"background": "#bfdbfe", "border": "#2563eb"},
                "shape": "box",
                "componentKind": center_category,
                "category": center_category,
            }
        }
        edges: list[dict[str, str]] = []
        edge_seen: set[tuple[str, str, str]] = set()
        for row in rows:
            target_name = row["name"]
            if target_name not in nodes:
                nodes[target_name] = {
                    "id": target_name,
                    "label": target_name,
                    "title": f"{row['category']} - {row['subtype']}: {target_name}",
                    "shape": "box",
                    "componentKind": row["subtype"],
                    "category": row["category"],
                    "color": self._dependency_node_color(row["category"]),
                }
            if row["direction"] == "Entrant":
                source = target_name
                destination = center_name
            else:
                source = center_name
                destination = target_name
            edge_key = (source, destination, row["relation"])
            if edge_key in edge_seen:
                continue
            edge_seen.add(edge_key)
            edges.append(
                {
                    "from": source,
                    "to": destination,
                    "label": row["relation"],
                    "arrows": "to",
                    "direction": row["direction"],
                }
            )

        network_id = f"dep-network-{key_suffix}"
        zoom_in_id = f"{network_id}-zoom-in"
        zoom_out_id = f"{network_id}-zoom-out"
        fit_id = f"{network_id}-fit"
        incoming_id = f"{network_id}-filter-incoming"
        outgoing_id = f"{network_id}-filter-outgoing"
        class_id = f"{network_id}-filter-class"
        trigger_id = f"{network_id}-filter-trigger"
        object_id = f"{network_id}-filter-object"
        flow_id = f"{network_id}-filter-flow"
        metadata_id = f"{network_id}-filter-metadata"
        return f"""
<div class="graph-toolbar">
  <button id="{zoom_in_id}" type="button">Zoom +</button>
  <button id="{zoom_out_id}" type="button">Zoom -</button>
  <button id="{fit_id}" type="button">Centrer</button>
</div>
<div class="graph-filters">
  <label><input id="{incoming_id}" type="checkbox" checked>Afficher entrants</label>
  <label><input id="{outgoing_id}" type="checkbox" checked>Afficher sortants</label>
  <label><input id="{class_id}" type="checkbox" checked>Afficher classes</label>
  <label><input id="{trigger_id}" type="checkbox" checked>Afficher triggers</label>
  <label><input id="{object_id}" type="checkbox" checked>Afficher objets</label>
  <label><input id="{flow_id}" type="checkbox" checked>Afficher flows</label>
  <label><input id="{metadata_id}" type="checkbox" checked>Afficher metadata</label>
</div>
<div class="graph-legend">
  <span class="item"><span class="dot" style="background:#bfdbfe"></span>Apex/Trigger central</span>
  <span class="item"><span class="dot" style="background:#dbeafe"></span>Autres Apex/Trigger</span>
  <span class="item"><span class="dot" style="background:#dcfce7"></span>Objets</span>
  <span class="item"><span class="dot" style="background:#ffedd5"></span>Flows</span>
  <span class="item"><span class="dot" style="background:#f3e8ff"></span>Metadata</span>
</div>
<div id="{network_id}" class="dependency-graph"></div>
<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
<script>
(() => {{
  const container = document.getElementById({json.dumps(network_id)});
  if (!container || typeof vis === "undefined") return;
  const centerId = {json.dumps(center_name)};
  const fullNodes = {json.dumps(list(nodes.values()))};
  const fullEdges = {json.dumps(edges)};
  const nodeMap = new Map(fullNodes.map((node) => [node.id, node]));
  const nodes = new vis.DataSet(fullNodes);
  const edges = new vis.DataSet(fullEdges);
  const network = new vis.Network(container, {{ nodes, edges }}, {{
    nodes: {{ borderWidth: 1, font: {{ face: "Arial", size: 13 }} }},
    edges: {{ color: "#64748b", arrows: "to", smooth: {{ type: "dynamic" }}, font: {{ align: "middle", size: 10 }} }},
    physics: {{ stabilization: true }},
    interaction: {{ hover: true, zoomView: true, dragView: true }}
  }});

  const zoomStep = 1.2;
  const zoomIn = document.getElementById({json.dumps(zoom_in_id)});
  const zoomOut = document.getElementById({json.dumps(zoom_out_id)});
  const fit = document.getElementById({json.dumps(fit_id)});
  const filterIncoming = document.getElementById({json.dumps(incoming_id)});
  const filterOutgoing = document.getElementById({json.dumps(outgoing_id)});
  const filterClass = document.getElementById({json.dumps(class_id)});
  const filterTrigger = document.getElementById({json.dumps(trigger_id)});
  const filterObject = document.getElementById({json.dumps(object_id)});
  const filterFlow = document.getElementById({json.dumps(flow_id)});
  const filterMetadata = document.getElementById({json.dumps(metadata_id)});

  const isKindEnabled = (kind) => {{
    const lowered = String(kind || "").toLowerCase();
    if (lowered === "class") return !filterClass || filterClass.checked;
    if (lowered === "trigger") return !filterTrigger || filterTrigger.checked;
    if (lowered === "apex") return (!filterClass || filterClass.checked) || (!filterTrigger || filterTrigger.checked);
    return true;
  }};
  const isCategoryEnabled = (category) => {{
    const lowered = String(category || "").toLowerCase();
    if (lowered === "objet") return !filterObject || filterObject.checked;
    if (lowered === "flow") return !filterFlow || filterFlow.checked;
    if (lowered === "metadata") return !filterMetadata || filterMetadata.checked;
    return true;
  }};

  const applyFilters = () => {{
    const allowIncoming = !filterIncoming || filterIncoming.checked;
    const allowOutgoing = !filterOutgoing || filterOutgoing.checked;
    const filteredEdges = [];
    const visibleNodeIds = new Set([centerId]);

    for (const edge of fullEdges) {{
      if (edge.direction === "Entrant" && !allowIncoming) continue;
      if (edge.direction === "Sortant" && !allowOutgoing) continue;

      const sourceNode = nodeMap.get(edge.from);
      const targetNode = nodeMap.get(edge.to);
      if (!sourceNode || !targetNode) continue;

      const linkedNode = edge.from === centerId ? targetNode : sourceNode;
      if (!isKindEnabled(linkedNode.componentKind)) continue;
      if (!isCategoryEnabled(linkedNode.category)) continue;

      filteredEdges.push(edge);
      visibleNodeIds.add(sourceNode.id);
      visibleNodeIds.add(targetNode.id);
    }}

    const filteredNodes = fullNodes.filter((node) => visibleNodeIds.has(node.id));
    nodes.clear();
    edges.clear();
    nodes.add(filteredNodes);
    edges.add(filteredEdges);
    network.fit({{ animation: false }});
  }};

  [filterIncoming, filterOutgoing, filterClass, filterTrigger, filterObject, filterFlow, filterMetadata].forEach((input) => {{
    if (input) input.addEventListener("change", applyFilters);
  }});

  if (zoomIn) {{
    zoomIn.addEventListener("click", () => {{
      const scale = network.getScale();
      network.moveTo({{ scale: scale * zoomStep }});
    }});
  }}
  if (zoomOut) {{
    zoomOut.addEventListener("click", () => {{
      const scale = network.getScale();
      network.moveTo({{ scale: scale / zoomStep }});
    }});
  }}
  if (fit) {{
    fit.addEventListener("click", () => network.fit({{ animation: true }}));
  }}
  network.once("stabilizationIterationsDone", () => {{
    network.setOptions({{ physics: false }});
  }});
  applyFilters();
}})();
</script>
"""

    def _build_flow_reference_index(
        self,
        flows: list[FlowInfo],
        flow_bodies: dict[str, str],
    ) -> dict[str, set[str]]:
        references: dict[str, set[str]] = {}
        patterns = {
            flow.name: re.compile(rf"\b{re.escape(flow.name)}\b", re.IGNORECASE)
            for flow in flows
        }
        for source in flows:
            body = flow_bodies.get(source.name, "")
            linked: set[str] = set()
            for target in flows:
                if target.name == source.name:
                    continue
                if patterns[target.name].search(body):
                    linked.add(target.name)
            references[source.name] = linked
        return references

    def _flow_dependencies(
        self,
        flow: FlowInfo,
        flow_ref_index: dict[str, set[str]],
        body: str,
        object_names: list[str],
        apex_names: list[str],
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()

        for target_name in sorted(flow_ref_index.get(flow.name, set()), key=str.lower):
            key = (target_name, "Sortant", "Reference flow", "Flow")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": target_name,
                    "category": "Flow",
                    "subtype": "Flow",
                    "direction": "Sortant",
                    "relation": "Reference flow",
                }
            )

        for source_name, targets in flow_ref_index.items():
            if source_name == flow.name or flow.name not in targets:
                continue
            key = (source_name, "Entrant", "Reference flow", "Flow")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": source_name,
                    "category": "Flow",
                    "subtype": "Flow",
                    "direction": "Entrant",
                    "relation": "Reference flow",
                }
            )

        if flow.start_object:
            key = (flow.start_object, "Sortant", "Objet de depart", "Objet")
            if key not in seen:
                seen.add(key)
                rows.append(
                    {
                        "name": flow.start_object,
                        "category": "Objet",
                        "subtype": "sObject",
                        "direction": "Sortant",
                        "relation": "Objet de depart",
                    }
                )

        for object_name in sorted(object_names, key=str.lower):
            if not re.search(rf"\b{re.escape(object_name)}\b", body):
                continue
            key = (object_name, "Sortant", "Usage objet", "Objet")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": object_name,
                    "category": "Objet",
                    "subtype": "sObject",
                    "direction": "Sortant",
                    "relation": "Usage objet",
                }
            )

        for apex_name in sorted(apex_names, key=str.lower):
            if not re.search(rf"\b{re.escape(apex_name)}\b", body):
                continue
            key = (apex_name, "Sortant", "Reference Apex", "Apex")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": apex_name,
                    "category": "Apex",
                    "subtype": "class",
                    "direction": "Sortant",
                    "relation": "Reference Apex",
                }
            )

        metadata_matches = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*__mdt)\b", body)))
        for metadata_name in metadata_matches:
            key = (metadata_name, "Sortant", "Reference metadata", "Metadata")
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": metadata_name,
                    "category": "Metadata",
                    "subtype": "CustomMetadata",
                    "direction": "Sortant",
                    "relation": "Reference metadata",
                }
            )

        rows.sort(key=lambda item: (item["category"], item["direction"], item["name"].lower()))
        return rows

    def _dependency_node_color(self, category: str) -> dict[str, str]:
        palette = {
            "Apex": {"background": "#dbeafe", "border": "#3b82f6"},
            "Objet": {"background": "#dcfce7", "border": "#22c55e"},
            "Flow": {"background": "#ffedd5", "border": "#f97316"},
            "Metadata": {"background": "#f3e8ff", "border": "#a855f7"},
        }
        return palette.get(category, {"background": "#e2e8f0", "border": "#64748b"})

    def _tabbed_sections(self, group_id: str, sections: list[tuple[str, str]]) -> str:
        button_html: list[str] = []
        panel_html: list[str] = []
        for index, (label, content) in enumerate(sections):
            tab_id = f"{group_id}-tab-{index}"
            panel_id = f"{group_id}-panel-{index}"
            active_class = " active" if index == 0 else ""
            button_html.append(
                f"<button class='tab-button{active_class}' type='button' data-tab-group='{group_id}' data-tab-target='{panel_id}' id='{tab_id}'>{html_value(label)}</button>"
            )
            panel_html.append(
                f"<div class='tab-panel{active_class}' id='{panel_id}' data-tab-panel='{group_id}'>{content}</div>"
            )
        return (
            "<div class='tabs'>"
            f"<div class='tab-buttons'>{''.join(button_html)}</div>"
            f"{''.join(panel_html)}"
            "</div>"
        )

    def _page(self, title: str, body: str, current_path: Path, include_mermaid: bool = True) -> str:
        style_href = self._href(current_path, self.assets_dir / "style.css")
        mermaid_script = "" if include_mermaid else ""
        tabs_script = """
<script>
(() => {
  document.querySelectorAll("[data-tab-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const group = button.getAttribute("data-tab-group");
      const target = button.getAttribute("data-tab-target");
      if (!group || !target) return;
      document.querySelectorAll(`[data-tab-group="${group}"]`).forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(`[data-tab-panel="${group}"]`).forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      const panel = document.getElementById(target);
      if (panel) panel.classList.add("active");
    });
  });
})();
</script>
""".strip()
        return f"""<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_value(title)}</title>
    <link rel="stylesheet" href="{style_href}">
    {mermaid_script}
  </head>
  <body>
    <div class="page">
      {body}
    </div>
    {tabs_script}
  </body>
</html>
"""

    def _href(self, from_path: Path, to_path: Path) -> str:
        return Path(os.path.relpath(to_path, from_path.parent)).as_posix()
