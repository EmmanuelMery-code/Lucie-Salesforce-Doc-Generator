"""Build and render the dependency tables / vis-network graphs.

The functions here scan Apex bodies and Flow XML for inter-component
references (Apex<->Apex, Apex/Flow<->Object, custom metadata, etc.) and
turn the results into the small HTML fragments embedded under the
"Liens" / "Graphe" tabs of each Apex and Flow page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.core.models import ApexArtifact, FlowInfo
from src.core.utils import html_value, safe_slug

from src.reporting.html.page_shell import href_relative


_METADATA_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*__mdt)\b")


def build_apex_reference_index(
    artifacts: list[ApexArtifact],
) -> dict[str, set[str]]:
    """Return, for each Apex artifact, the set of other artifacts mentioned in its body."""

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


def trigger_object_name(artifact: ApexArtifact) -> str:
    """Extract the sObject name a trigger fires on, or ``""`` for non-triggers."""

    if artifact.kind != "trigger":
        return ""
    match = re.search(
        r"(?im)^\s*trigger\s+\w+\s+on\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        artifact.body,
    )
    return match.group(1) if match else ""


def apex_dependencies(
    artifact: ApexArtifact,
    artifacts: list[ApexArtifact],
    reference_index: dict[str, set[str]],
    trigger_objects: dict[str, str],
    object_names: list[str],
    flow_names: list[str],
) -> list[dict[str, str]]:
    """Compute the (sorted, de-duplicated) dependency rows for a single Apex artifact."""

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

    metadata_matches = sorted(set(_METADATA_RE.findall(artifact.body)))
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


def build_flow_reference_index(
    flows: list[FlowInfo],
    flow_bodies: dict[str, str],
) -> dict[str, set[str]]:
    """Return, for each flow, the set of other flow names mentioned in its source XML."""

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


def flow_dependencies(
    flow: FlowInfo,
    flow_ref_index: dict[str, set[str]],
    body: str,
    object_names: list[str],
    apex_names: list[str],
) -> list[dict[str, str]]:
    """Compute the (sorted, de-duplicated) dependency rows for a single flow."""

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

    metadata_matches = sorted(set(_METADATA_RE.findall(body)))
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


def dependency_node_color(category: str) -> dict[str, str]:
    """Return the vis-network background/border palette for a node ``category``."""

    palette = {
        "Apex": {"background": "#dbeafe", "border": "#3b82f6"},
        "Objet": {"background": "#dcfce7", "border": "#22c55e"},
        "Flow": {"background": "#ffedd5", "border": "#f97316"},
        "Metadata": {"background": "#f3e8ff", "border": "#a855f7"},
    }
    return palette.get(category, {"background": "#e2e8f0", "border": "#64748b"})


def render_dependency_rows(
    rows: list[dict[str, str]],
    current_path: Path,
    link_maps: dict[str, dict[str, Path]],
) -> str:
    """Render dependency ``rows`` as ``<tr>`` cells, linking known components."""

    if not rows:
        return "<tr><td colspan='5' class='empty'>Aucun lien detecte.</td></tr>"

    rendered_rows: list[str] = []
    for row in rows:
        target_path = link_maps.get(row["category"], {}).get(row["name"])
        if target_path:
            name_html = (
                f"<a href='{href_relative(current_path, target_path)}'>{html_value(row['name'])}</a>"
            )
        else:
            name_html = html_value(row["name"])
        rendered_rows.append(
            f"<tr><td>{name_html}</td><td>{html_value(row['category'])}</td><td>{html_value(row['subtype'])}</td>"
            f"<td>{html_value(row['direction'])}</td><td>{html_value(row['relation'])}</td></tr>"
        )
    return "".join(rendered_rows)


def render_apex_dependency_rows(
    rows: list[dict[str, str]],
    current_path: Path,
    apex_pages: dict[str, Path],
) -> str:
    """Convenience wrapper around :func:`render_dependency_rows` for Apex pages."""

    return render_dependency_rows(rows, current_path, {"Apex": apex_pages})


def render_apex_dependency_graph(
    artifact: ApexArtifact,
    rows: list[dict[str, str]],
) -> str:
    """Render the vis-network graph centred on an Apex artifact."""

    return render_component_dependency_graph(
        artifact.name, "Apex", rows, safe_slug(artifact.name)
    )


def render_component_dependency_graph(
    center_name: str,
    center_category: str,
    rows: list[dict[str, str]],
    key_suffix: str,
) -> str:
    """Render the interactive vis-network dependency graph for any component."""

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
                "color": dependency_node_color(row["category"]),
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
  network.on("doubleClick", (params) => {{
    const scale = network.getScale();
    const evt = params && params.event && params.event.srcEvent;
    const shift = !!(evt && evt.shiftKey);
    const factor = shift ? (1 / zoomStep) : zoomStep;
    network.moveTo({{ scale: scale * factor, animation: {{ duration: 150 }} }});
  }});
  network.once("stabilizationIterationsDone", () => {{
    network.setOptions({{ physics: false }});
  }});
  applyFilters();
}})();
</script>
"""
