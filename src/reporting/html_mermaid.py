"""Mermaid diagram helpers for the HTML report writer.

Pure functions that turn metadata structures into Mermaid source code (or
already-wrapped HTML). They were extracted from
:mod:`src.reporting.html_writer` to keep that module focused on HTML
templating; nothing here depends on writer state.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from src.core.models import ObjectInfo, ValidationRuleInfo
from src.core.utils import SF_NS, child_text, safe_slug
from src.reporting.formula_parser import FormulaNode, parse_formula


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def wrap_mermaid_block(diagram_source: str) -> str:
    """Wrap raw Mermaid source in the toolbar/container HTML the pages expect."""

    return (
        "<div class='mermaid-container'>"
        "<div class='mermaid-toolbar'>"
        "<button type='button' class='mm-btn' data-mermaid-action='zoom-in' title='Zoom avant'>+</button>"
        "<button type='button' class='mm-btn' data-mermaid-action='zoom-out' title='Zoom arriere'>&minus;</button>"
        "<button type='button' class='mm-btn' data-mermaid-action='reset' title='Reinitialiser la vue'>&#8634;</button>"
        "<span class='mm-hint'>Glisser pour deplacer - Double-clic : zoom+ / Shift+double-clic : zoom-</span>"
        "</div>"
        f"<div class='mermaid'>\n{diagram_source}\n</div>"
        "</div>"
    )


def mermaid_condition_label(text: str) -> str:
    """Return ``text`` sanitised for use as a Mermaid node label.

    Mermaid is sensitive to several characters (``"|<>{}\\``); this helper
    strips/escapes them and truncates overly long labels.
    """

    if not text:
        return "Condition"
    compact = " ".join(text.split())
    if len(compact) > 70:
        compact = compact[:67] + "..."
    compact = compact.replace("&", "&amp;")
    compact = compact.replace('"', "'")
    compact = compact.replace("\\", "")
    compact = compact.replace("|", "/")
    compact = compact.replace("<", "&lt;")
    compact = compact.replace(">", "&gt;")
    compact = compact.replace("{", "(")
    compact = compact.replace("}", ")")
    compact = compact.replace("`", "'")
    return compact.strip() or "Condition"


def short_error_text(text: str, limit: int = 60) -> str:
    """Compact ``text`` to one line and truncate it for display in diagrams."""

    raw = " ".join((text or "").split()).strip()
    if not raw:
        return ""
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    raw = raw.replace("&", "&amp;")
    raw = raw.replace('"', "'")
    raw = raw.replace("<", "&lt;")
    raw = raw.replace(">", "&gt;")
    raw = raw.replace("|", "/")
    return raw


def mermaid_id(value: str) -> str:
    """Return a Mermaid-safe identifier derived from ``value``."""

    slug = safe_slug(value).replace("-", "_")
    if not slug:
        slug = "node"
    if not slug[0].isalpha():
        slug = f"n_{slug}"
    return slug


def mermaid_label(value: str) -> str:
    """Sanitise ``value`` so it can appear inside a Mermaid node label."""

    text = "" if value is None else str(value)
    replacements = [
        ("\r", " "),
        ("\n", " "),
        ("\t", " "),
        ("\\", " "),
        ('"', ""),
        ("'", ""),
        ("`", ""),
        ("|", " "),
        ("<", " "),
        (">", " "),
        ("&", "et"),
        ("[", "("),
        ("]", ")"),
        ("{", "("),
        ("}", ")"),
        ("#", ""),
        (";", ","),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return " ".join(text.split()).strip()


# ---------------------------------------------------------------------------
# Domain-specific diagrams
# ---------------------------------------------------------------------------


def data_transform_meta(xml_content: str) -> dict[str, str]:
    """Extract the ``type`` / ``inputType`` / ``outputType`` / ``description`` fields from a DataTransform."""

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return {}
    return {
        "type": child_text(root, "type"),
        "inputType": child_text(root, "inputType"),
        "outputType": child_text(root, "outputType"),
        "description": child_text(root, "description"),
    }


def data_transform_mermaid(xml_content: str, name: str) -> str | None:
    """Build a Mermaid flowchart describing an OmniStudio Data Transform.

    Returns ``None`` when the XML cannot be parsed or contains no items;
    callers should then render an "empty" placeholder.
    """

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    items = root.findall("sf:omniDataTransformItem", SF_NS)
    if not items:
        return None

    dt_type = child_text(root, "type") or "Data Transform"
    input_type = child_text(root, "inputType") or ""
    output_type = child_text(root, "outputType") or ""

    state = {"counter": 0}

    def new_id(prefix: str) -> str:
        state["counter"] += 1
        return f"{prefix}{state['counter']}"

    input_nodes: dict[str, str] = {}
    output_nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []
    filter_nodes: list[tuple[str, str]] = []

    def add_input(label: str) -> str:
        key = label.strip() or "(vide)"
        if key not in input_nodes:
            input_nodes[key] = new_id("I")
        return input_nodes[key]

    def add_output(label: str) -> str:
        key = label.strip() or "(vide)"
        if key not in output_nodes:
            output_nodes[key] = new_id("O")
        return output_nodes[key]

    max_items = 80
    shown = 0
    truncated = False
    disabled_ids: list[str] = []

    for item in items:
        if shown >= max_items:
            truncated = True
            break
        input_obj = child_text(item, "inputObjectName")
        input_field = child_text(item, "inputFieldName")
        output_obj = child_text(item, "outputObjectName")
        output_field = child_text(item, "outputFieldName")
        formula_expr = child_text(item, "formulaExpression")
        formula_converted = child_text(item, "formulaConverted")
        formula_path = child_text(item, "formulaResultPath")
        default_value = child_text(item, "defaultValue")
        filter_op = child_text(item, "filterOperator")
        filter_val = child_text(item, "filterValue")
        migration_value = child_text(item, "migrationValue")
        is_disabled = child_text(item, "disabled").lower() == "true"

        is_filter_only = bool(filter_op) and not output_field and not output_obj
        if is_filter_only:
            lbl = (
                f"Filtre : {filter_op} {filter_val}"
                if filter_val
                else f"Filtre : {filter_op}"
            )
            if input_obj:
                lbl = f"{input_obj} -> " + lbl
            filter_nodes.append((new_id("F"), lbl))
            continue

        if formula_expr:
            input_label = f"Formule : {formula_expr}"
        elif formula_converted:
            input_label = f"Formule : {formula_converted}"
        elif input_obj and input_field:
            input_label = f"{input_obj}.{input_field}"
        elif input_field:
            input_label = input_field
        elif default_value:
            input_label = f"Valeur par defaut : {default_value}"
        elif migration_value:
            input_label = f"Migration : {migration_value}"
        else:
            input_label = "Racine JSON d'entree"

        if output_obj and output_field:
            output_label = f"{output_obj}.{output_field}"
        elif output_field:
            output_label = output_field
        elif formula_path:
            output_label = f"Variable {formula_path}"
        elif output_obj:
            output_label = output_obj
        else:
            output_label = "(sortie implicite)"

        in_id = add_input(input_label)
        out_id = add_output(output_label)

        edge_parts: list[str] = []
        if filter_op and filter_val:
            edge_parts.append(f"filtre {filter_op} {filter_val}")
        elif filter_op and filter_val == "":
            pass
        if default_value and not formula_expr:
            edge_parts.append(f"defaut={default_value}")
        if is_disabled:
            edge_parts.append("DESACTIVE")
        edge_label = ", ".join(edge_parts)

        edges.append((in_id, out_id, edge_label))
        if is_disabled:
            disabled_ids.append(out_id)
        shown += 1

    if not input_nodes and not output_nodes and not filter_nodes:
        return None

    lines: list[str] = ["flowchart LR"]

    header_bits = [dt_type]
    if input_type:
        header_bits.append(f"in:{input_type}")
    if output_type:
        header_bits.append(f"out:{output_type}")
    header_label = mermaid_condition_label(" - ".join(header_bits))
    lines.append(f'    Header["{header_label}"]:::dtHeader')

    if input_nodes:
        lines.append('    subgraph Sources["Sources de donnees"]')
        lines.append("    direction TB")
        for label, nid in input_nodes.items():
            safe = mermaid_condition_label(label)
            lines.append(f'        {nid}["{safe}"]:::dtIn')
        lines.append("    end")

    if filter_nodes:
        lines.append('    subgraph Filtres["Filtres appliques"]')
        lines.append("    direction TB")
        for nid, label in filter_nodes:
            safe = mermaid_condition_label(label)
            lines.append(f'        {nid}["{safe}"]:::dtFilter')
        lines.append("    end")
        lines.append("    Header --> Filtres")

    if output_nodes:
        lines.append('    subgraph Cibles["Cibles produites"]')
        lines.append("    direction TB")
        for label, nid in output_nodes.items():
            safe = mermaid_condition_label(label)
            lines.append(f'        {nid}["{safe}"]:::dtOut')
        lines.append("    end")

    if input_nodes:
        lines.append("    Header --> Sources")

    for src, dst, label in edges:
        if label:
            safe_label = mermaid_condition_label(label)
            lines.append(f'    {src} -->|"{safe_label}"| {dst}')
        else:
            lines.append(f"    {src} --> {dst}")

    if truncated:
        nid = new_id("T")
        lines.append(
            f'    {nid}["... {len(items) - shown} mappings supplementaires non affiches"]:::dtTruncated'
        )

    if disabled_ids:
        for did in disabled_ids:
            lines.append(f"    class {did} dtDisabled")

    lines.append(
        "    classDef dtHeader fill:#1e293b,color:#f8fafc,stroke:#0f172a,stroke-width:2px;"
    )
    lines.append("    classDef dtIn fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a;")
    lines.append("    classDef dtOut fill:#dcfce7,stroke:#166534,color:#14532d;")
    lines.append("    classDef dtFilter fill:#fef3c7,stroke:#b45309,color:#78350f;")
    lines.append(
        "    classDef dtTruncated fill:#e2e8f0,stroke:#475569,color:#1e293b,font-style:italic;"
    )
    lines.append("    classDef dtDisabled stroke-dasharray:5 5,color:#64748b;")
    lines.append("    style Sources fill:#eff6ff,stroke:#60a5fa")
    lines.append("    style Cibles fill:#f0fdf4,stroke:#4ade80")
    if filter_nodes:
        lines.append("    style Filtres fill:#fffbeb,stroke:#f59e0b")

    return "\n".join(lines)


def validation_rule_mermaid(vr: ValidationRuleInfo) -> str:
    """Render a validation rule formula as a Mermaid decision tree (HTML wrapped)."""

    if not vr.error_condition_formula:
        return "<p class='empty'>Pas de formule pour generer l'arbre.</p>"

    tree = parse_formula(vr.error_condition_formula)

    msg = short_error_text(vr.error_message) or "Erreur levee"
    display = short_error_text(vr.error_display_field) or "Formulaire"

    state: dict[str, int] = {"c": 0}

    def new_id(prefix: str = "N") -> str:
        state["c"] += 1
        return f"{prefix}{state['c']}"

    lines: list[str] = ["flowchart TD"]
    ok_id = "NodeOK"
    err_id = "NodeERR"
    start_id = "NodeSTART"

    lines.append(f'    {start_id}(["Demande d\'enregistrement"])')
    lines.append(f'    {ok_id}(["Enregistrement autorise"])')
    lines.append(
        f'    {err_id}(["Enregistrement refuse<br/><b>{msg}</b><br/>Champ : {display}"])'
    )

    def build(node: FormulaNode, true_target: str, false_target: str) -> str:
        if node.kind == "NOT" and node.children:
            return build(node.children[0], false_target, true_target)

        if node.kind == "AND" and node.children:
            entry = true_target
            for child in reversed(node.children):
                entry = build(child, entry, false_target)
            return entry

        if node.kind == "OR" and node.children:
            entry = false_target
            for child in reversed(node.children):
                entry = build(child, true_target, entry)
            return entry

        if node.kind == "IF" and len(node.children) == 3:
            cond, t_val, f_val = node.children
            t_entry = build(t_val, true_target, false_target)
            f_entry = build(f_val, true_target, false_target)
            return build(cond, t_entry, f_entry)

        cid = new_id("C")
        label = mermaid_condition_label(node.text)
        lines.append(f'    {cid}{{"{label}"}}')
        lines.append(f'    {cid} -->|"VRAI"| {true_target}')
        lines.append(f'    {cid} -->|"FAUX"| {false_target}')
        return cid

    entry_id = build(tree, err_id, ok_id)
    lines.append(f"    {start_id} --> {entry_id}")

    cond_nodes = [f"C{i}" for i in range(1, state["c"] + 1)]
    if cond_nodes:
        lines.append(f"    class {','.join(cond_nodes)} condNode")
    lines.append(f"    class {start_id} startNode")
    lines.append(f"    class {ok_id} okNode")
    lines.append(f"    class {err_id} koNode")
    lines.append(
        "    classDef startNode fill:#e0e7ff,stroke:#4338ca,color:#1e1b4b,stroke-width:2px;"
    )
    lines.append(
        "    classDef condNode fill:#fef3c7,stroke:#d97706,color:#78350f;"
    )
    lines.append(
        "    classDef okNode fill:#bbf7d0,stroke:#15803d,color:#14532d,stroke-width:2px;"
    )
    lines.append(
        "    classDef koNode fill:#fecaca,stroke:#b91c1c,color:#7f1d1d,stroke-width:2px;"
    )

    diagram = "\n".join(lines)
    return wrap_mermaid_block(diagram)


def object_mermaid(item: ObjectInfo) -> str:
    """Render the relationships of a Salesforce object as a Mermaid flowchart."""

    if not item.relationships:
        return "<p class='empty'>Aucune relation detectee.</p>"

    root_id = "n0"
    root_label = mermaid_label(item.api_name) or "Objet"
    lines = ["flowchart LR", f'    {root_id}["{root_label}"]']
    target_ids: dict[str, str] = {root_label: root_id}
    edges: list[str] = []
    seen_edges: set[tuple[str, str, str]] = set()
    node_counter = 1

    for relationship in item.relationships:
        rel_type = mermaid_label(relationship.relationship_type or "Relation")
        field_name = mermaid_label(relationship.field_name or "")
        for target in relationship.targets:
            target_label = mermaid_label(target or "Cible inconnue") or "Cible"
            if target_label not in target_ids:
                target_ids[target_label] = f"n{node_counter}"
                node_counter += 1
                lines.append(f'    {target_ids[target_label]}["{target_label}"]')

            edge_label_parts = [part for part in (field_name, rel_type) if part]
            edge_label = " - ".join(edge_label_parts) if edge_label_parts else "Relation"
            edge_key = (root_id, target_ids[target_label], edge_label)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                f'    {root_id} -->|"{edge_label}"| {target_ids[target_label]}'
            )

    lines.extend(edges)
    diagram = "\n".join(lines)
    return wrap_mermaid_block(diagram)
