from __future__ import annotations

import os
from pathlib import Path

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
        self, artifacts: list[ApexArtifact], reviews: dict[str, ReviewResult]
    ) -> dict[str, Path]:
        output: dict[str, Path] = {}
        for artifact in artifacts:
            filename = f"{safe_slug(artifact.name)}.html"
            path = self.apex_dir / filename
            write_text(path, self._render_apex_page(artifact, reviews[artifact.name], path))
            output[artifact.name] = path
        self.log(f"{len(output)} page(s) Apex/Trigger generee(s).")
        return output

    def write_flow_pages(self, flows: list[FlowInfo], reviews: dict[str, ReviewResult]) -> dict[str, Path]:
        output: dict[str, Path] = {}
        for flow in flows:
            path = self.flows_dir / f"{safe_slug(flow.name)}.html"
            write_text(path, self._render_flow_page(flow, reviews[flow.name], path))
            output[flow.name] = path
        self.log(f"{len(output)} page(s) Flow generee(s).")
        return output

    def write_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
    ) -> Path:
        path = self.output_dir / "index.html"
        write_text(path, self._render_index(snapshot, object_pages, apex_pages, flow_pages, path))
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

        body = f"""
<div class="topnav"><a href="{self._href(current_path, self.output_dir / 'index.html')}">Retour a l'index</a></div>
<h1>{html_value(item.api_name)}</h1>
<div class="cards">
  <div class="card"><span>Champs</span><span class="value">{len(item.fields)}</span></div>
  <div class="card"><span>Record types</span><span class="value">{len(item.record_types)}</span></div>
  <div class="card"><span>Regles de validation</span><span class="value">{len(item.validation_rules)}</span></div>
  <div class="card"><span>Relations</span><span class="value">{len(item.relationships)}</span></div>
</div>
<div class="section"><h2>Informations descriptives</h2><ul>{description_html}</ul></div>
<div class="section"><h2>Fields</h2><table><thead><tr><th>Name</th><th>Label</th><th>Type</th><th>Description</th><th>Required</th></tr></thead><tbody>{fields_rows}</tbody></table></div>
<div class="section"><h2>Profile</h2><table><thead><tr><th>Profile</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{profile_rows}</tbody></table></div>
<div class="section"><h2>Permission Set</h2><table><thead><tr><th>Permission Set</th><th>Lecture</th><th>Creation</th><th>Modification</th><th>Suppression</th><th>Nb champs visibles</th><th>Nb champs modifiables</th></tr></thead><tbody>{permset_rows}</tbody></table></div>
<div class="section"><h2>Record Types</h2><table><thead><tr><th>Nom</th><th>Label</th><th>Description</th><th>Actif</th></tr></thead><tbody>{record_type_rows}</tbody></table></div>
<div class="section"><h2>Relation</h2>{mermaid}</div>
<div class="section"><h2>The table(s) in relation</h2><table><thead><tr><th>Champ</th><th>Type</th><th>Cible</th></tr></thead><tbody>{relation_table}</tbody></table></div>
"""
        return self._page(item.api_name, body, current_path)

    def _render_apex_page(self, artifact: ApexArtifact, review: ReviewResult, current_path: Path) -> str:
        metrics = "".join(
            f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
            for label, value in review.metrics
        )
        positives = self._list_or_empty(review.positives, "Aucun point fort automatique detecte.")
        improvements = self._list_or_empty(review.improvements, "Aucun point d'amelioration automatique detecte.")
        code_preview = "\n".join(artifact.body.splitlines()[:120])
        body = f"""
<div class="topnav"><a href="{self._href(current_path, self.output_dir / 'index.html')}">Retour a l'index</a></div>
<h1>{html_value(artifact.name)}</h1>
<span class="badge">{html_value(artifact.kind)}</span>
<div class="section"><h2>Resume</h2><p>{html_value(review.summary)}</p></div>
<div class="section"><h2>Metriques</h2><ul>{metrics}</ul></div>
<div class="section"><h2>Ce qui est bien</h2>{positives}</div>
<div class="section"><h2>Ce qu'il faut ameliorer</h2>{improvements}</div>
<div class="section"><h2>Extrait</h2><pre>{html_value(code_preview)}</pre></div>
"""
        return self._page(artifact.name, body, current_path)

    def _render_flow_page(self, flow: FlowInfo, review: ReviewResult, current_path: Path) -> str:
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
<div class="section"><h2>Resume</h2><p>{html_value(review.summary)}</p></div>
<div class="section"><h2>Metriques</h2><ul>{metrics}</ul></div>
<div class="section"><h2>Repartition des blocs</h2><table><thead><tr><th>Type</th><th>Nombre</th></tr></thead><tbody>{count_rows}</tbody></table></div>
<div class="section"><h2>Ce qui est bien</h2>{self._list_or_empty(review.positives, "Aucun point fort automatique detecte.")}</div>
<div class="section"><h2>Ce qu'il faut ameliorer</h2>{self._list_or_empty(review.improvements, "Aucun point d'amelioration automatique detecte.")}</div>
<div class="section"><h2>Elements</h2><table><thead><tr><th>Type</th><th>Nom</th><th>Label</th><th>Description</th><th>Cible</th></tr></thead><tbody>{elements_rows}</tbody></table></div>
"""
        return self._page(flow.name, body, current_path)

    def _render_index(
        self,
        snapshot: MetadataSnapshot,
        object_pages: dict[str, Path],
        apex_pages: dict[str, Path],
        flow_pages: dict[str, Path],
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

        excel_profile = self._href(current_path, self.output_dir / "excel" / "profiles.xlsx")
        excel_permset = self._href(current_path, self.output_dir / "excel" / "permission_sets.xlsx")

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
<div class="section">
  <h2>Exports Excel</h2>
  <ul>
    <li><a href="{excel_permset}">Permission Sets</a></li>
    <li><a href="{excel_profile}">Profiles</a></li>
  </ul>
</div>
<div class="section"><h2>Objets</h2><table><thead><tr><th>Objet</th><th>Label</th><th>Nb champs</th><th>Nb relations</th></tr></thead><tbody>{object_rows}</tbody></table></div>
<div class="section"><h2>Profiles</h2><table><thead><tr><th>Profile</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{profile_rows}</tbody></table></div>
<div class="section"><h2>Permission Sets</h2><table><thead><tr><th>Permission Set</th><th>Droits objet</th><th>Droits champ</th></tr></thead><tbody>{permset_rows}</tbody></table></div>
<div class="section"><h2>Apex / Trigger</h2><table><thead><tr><th>Nom</th><th>Type</th><th>Lignes</th><th>Methodes</th></tr></thead><tbody>{apex_rows}</tbody></table></div>
<div class="section"><h2>Flows</h2><table><thead><tr><th>Nom</th><th>Type</th><th>Complexite</th><th>Score</th><th>Elements</th><th>Documentes</th></tr></thead><tbody>{flow_rows}</tbody></table></div>
"""
        return self._page("Index", body, current_path, include_mermaid=False)

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

        current_id = safe_slug(item.api_name).replace("-", "_")
        lines = ["flowchart TD", f"    {current_id}[\"{item.api_name}\"]"]
        for index, relationship in enumerate(item.relationships, start=1):
            for target in relationship.targets:
                target_id = f"{safe_slug(target).replace('-', '_')}_{index}"
                lines.append(f"    {target_id}[\"{target}\"]")
                lines.append(
                    f"    {current_id} -->|\"{relationship.field_name} ({relationship.relationship_type})\"| {target_id}"
                )
        diagram = "\n".join(lines)
        return f"""
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true }});
</script>
<div class="mermaid">{diagram}</div>
"""

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

    def _page(self, title: str, body: str, current_path: Path, include_mermaid: bool = True) -> str:
        style_href = self._href(current_path, self.assets_dir / "style.css")
        mermaid_script = "" if include_mermaid else ""
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
  </body>
</html>
"""

    def _href(self, from_path: Path, to_path: Path) -> str:
        return Path(os.path.relpath(to_path, from_path.parent)).as_posix()
