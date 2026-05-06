"""Renderer for history-based reports (dashboards and comparisons)."""

from __future__ import annotations

import os
from pathlib import Path
from src.core.history_service import HistoryEntry
from src.core.utils import html_value, write_text
from src.reporting.html.page_shell import render_page


def render_dashboard(
    selected: HistoryEntry,
    history: list[HistoryEntry],
    current_path: Path,
    assets_dir: Path,
) -> str:
    """Render a printable A4 dashboard with current status and evolution trend."""

    def _get_pie_css(val1: float, color1: str, color2: str) -> str:
        """Generate CSS for a simple pie chart using conic-gradient."""
        return f"background: conic-gradient({color1} 0% {val1}%, {color2} {val1}% 100%);"

    # Calculations for Status (Selected Generation)
    adoption_pct = selected.adoption_pct
    adaptation_pct = selected.adaptation_pct
    dm_standard_pct = selected.data_model_standard_pct
    dm_custom_pct = selected.data_model_custom_pct
    ai_with_pct = selected.ai_usage_pct
    ai_without_pct = 100.0 - ai_with_pct

    # Findings totals
    f_total = selected.findings_total
    f_crit = selected.findings_critical
    f_maj = selected.findings_major
    f_min = selected.findings_minor
    f_inf = selected.findings_info
    
    # Max finding for bar scaling
    max_f = max(f_crit, f_maj, f_min, f_inf, 1)

    # Evolution data: sort history by generation number ascending
    sorted_history = sorted(history, key=lambda e: e.generation_number)
    
    # Heuristic: if we have more than 5 releases, the tables might make the page too long
    # especially when printing on A4.
    show_evolution_tables = len(sorted_history) <= 5

    def _render_evolution_chart(title: str, data_points: list[dict], colors: dict) -> str:
        bars = ""
        # Filter out non-numeric values (like 'label') before finding max
        numeric_values = []
        for p in data_points:
            numeric_values.extend([v for k, v in p.items() if k != "label" and isinstance(v, (int, float))])
        max_val = max(numeric_values + [1])
        
        for p in data_points:
            label = p.get("label", "")
            bar_group = ""
            for key, val in p.items():
                if key == "label" or not isinstance(val, (int, float)):
                    continue
                height = (val / max_val) * 100 if max_val > 0 else 0
                color = colors.get(key, "#cbd5e0")
                bar_group += f'<div class="bar" style="background-color: {color}; height: {height}%; width: 15px;" title="{key}: {val}"></div>'
            
            bars += f"""
                <div class="bar-group" style="flex-direction: row; gap: 2px; align-items: flex-end; justify-content: center;">
                    {bar_group}
                    <div class="bar-label">{label}</div>
                </div>
            """
        return bars

    # Adoption Evolution
    adoption_data = []
    for e in sorted_history:
        adoption_data.append({
            "label": f"R{e.generation_number}",
            "adoption": e.adoption_pct,
            "adaptation": e.adaptation_pct
        })
    
    adoption_evolution_bars = _render_evolution_chart(
        "Adoption vs Adaptation", 
        [dict(d) for d in adoption_data], 
        {"adoption": "#68b36b", "adaptation": "#e5534b"}
    )

    adoption_table = ""
    if show_evolution_tables:
        rows = ""
        for d in adoption_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['adoption']:.1f}%</td><td>{d['adaptation']:.1f}%</td></tr>"
        adoption_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>adoption</th><th>adaptation</th></tr>
                {rows}
            </table>
        """

    # Data Model Evolution
    dm_data = []
    for e in sorted_history:
        dm_data.append({
            "label": f"R{e.generation_number}",
            "standard": e.data_model_standard_pct,
            "custom": e.data_model_custom_pct
        })
    
    dm_evolution_bars = _render_evolution_chart(
        "Data Model standard vs custom", 
        [dict(d) for d in dm_data], 
        {"standard": "#68b36b", "custom": "#e5534b"}
    )

    dm_table = ""
    if show_evolution_tables:
        rows = ""
        for d in dm_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['standard']:.1f}%</td><td>{d['custom']:.1f}%</td></tr>"
        dm_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>standard</th><th>custom</th></tr>
                {rows}
            </table>
        """

    # AI Usage Evolution
    ai_data = []
    for e in sorted_history:
        ai_data.append({
            "label": f"R{e.generation_number}",
            "avec IA": e.ai_usage_pct,
            "sans IA": 100.0 - e.ai_usage_pct
        })
    
    ai_evolution_bars = _render_evolution_chart(
        "Usage de l'IA", 
        [dict(d) for d in ai_data], 
        {"avec IA": "#68b36b", "sans IA": "#e5534b"}
    )

    ai_table = ""
    if show_evolution_tables:
        rows = ""
        for d in ai_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['avec IA']:.1f}%</td><td>{d['sans IA']:.1f}%</td></tr>"
        ai_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>avec IA</th><th>sans IA</th></tr>
                {rows}
            </table>
        """

    # Findings Evolution
    findings_data = []
    max_total_f = max([e.findings_total for e in sorted_history] + [1])
    for e in sorted_history:
        findings_data.append({
            "label": f"R{e.generation_number}",
            "Critique": e.findings_critical,
            "Majeur": e.findings_major,
            "Mineur": e.findings_minor,
            "Info": e.findings_info
        })
    
    findings_evolution_bars = _render_evolution_chart(
        "Analyzer Findings", 
        [dict(d) for d in findings_data], 
        {"Critique": "#e53e3e", "Majeur": "#ed8936", "Mineur": "#ecc94b", "Info": "#48bb78"}
    )

    findings_table = ""
    if show_evolution_tables:
        rows = ""
        for d in findings_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['Critique']}</td><td>{d['Majeur']}</td><td>{d['Mineur']}</td><td>{d['Info']}</td></tr>"
        findings_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th></tr>
                {rows}
            </table>
        """

    html_content = f"""
    <style>
        /* Inlined CSS for Dashboard to ensure it works even if assets fail */
        .dashboard-page {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1a202c;
            line-height: 1.4;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        .dashboard-header {{
            text-align: center;
            border-bottom: 2px solid #2d3748;
            margin-bottom: 20px;
            padding-bottom: 10px;
        }}
        .dashboard-header h1 {{ margin: 0; font-size: 24px; color: #2d3748; }}
        .dashboard-header p {{ margin: 5px 0 0; color: #718096; font-size: 14px; }}
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }}
        .dashboard-card {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .dashboard-card h3 {{
            margin: 0 0 15px 0;
            font-size: 16px;
            text-align: center;
            color: #4a5568;
            border-bottom: 1px solid #edf2f7;
            padding-bottom: 8px;
        }}
        .chart-container {{
            height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .pie-chart {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            position: relative;
        }}
        .chart-legend {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 10px;
            font-size: 12px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .dashboard-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 12px;
        }}
        .dashboard-table th, .dashboard-table td {{
            border: 1px solid #e2e8f0;
            padding: 6px 8px;
            text-align: center;
        }}
        .dashboard-table th {{ background: #f7fafc; font-weight: 600; }}
        .bar-chart {{
            display: flex;
            align-items: flex-end;
            gap: 10px;
            height: 120px;
            padding-bottom: 20px;
            border-bottom: 1px solid #cbd5e0;
            margin: 0 20px;
            width: 100%;
        }}
        .bar-group {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
            justify-content: flex-end;
            position: relative;
        }}
        .bar {{
            width: 30px;
            border-radius: 4px 4px 0 0;
            transition: height 0.3s;
        }}
        .bar-label {{
            position: absolute;
            bottom: -20px;
            font-size: 10px;
            white-space: nowrap;
        }}
        .bar-value {{ font-size: 10px; margin-bottom: 2px; }}
        .color-adoption {{ background-color: #68b36b; }}
        .color-adaptation {{ background-color: #e5534b; }}
        .color-standard {{ background-color: #68b36b; }}
        .color-custom {{ background-color: #e5534b; }}
        .color-ai-with {{ background-color: #68b36b; }}
        .color-ai-without {{ background-color: #e5534b; }}
        .color-critique {{ background-color: #e53e3e; }}
        .color-majeur {{ background-color: #ed8936; }}
        .color-mineur {{ background-color: #ecc94b; }}
        .color-info {{ background-color: #48bb78; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ background: white !important; }}
            .dashboard-page {{ padding: 0; width: 100%; }}
            .page-break {{ page-break-before: always; }}
        }}
    </style>
    <div class="dashboard-page">
        <div class="topnav no-print" style="margin-bottom: 20px;"><a href="index.html" style="text-decoration: none; color: #1d4ed8;">&larr; Retour à l'index</a></div>
        
        <div class="dashboard-header">
            <h1>Status de la release : {html_value(selected.alias)}</h1>
            <p>Génération #{selected.generation_number} - {selected.timestamp}</p>
        </div>

        <div class="dashboard-grid">
            <!-- Adoption vs Adaptation -->
            <div class="dashboard-card">
                <h3>Adoption vs Adaptation</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(adoption_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-adoption"></div> Adoption {adoption_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-adaptation"></div> Adaptation {adaptation_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Adoption</th><td>{adoption_pct:.1f}%</td></tr>
                    <tr><th>Adaptation</th><td>{adaptation_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- Data Model -->
            <div class="dashboard-card">
                <h3>Data Model Adoption vs Adaptation</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(dm_standard_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-standard"></div> Standard {dm_standard_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-custom"></div> Custom {dm_custom_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Standard</th><td>{dm_standard_pct:.1f}%</td></tr>
                    <tr><th>Custom</th><td>{dm_custom_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- AI Usage -->
            <div class="dashboard-card">
                <h3>Usage de l'IA</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(ai_with_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-ai-with"></div> Construit avec IA {ai_with_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-ai-without"></div> Construit sans IA {ai_without_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Avec IA</th><td>{ai_with_pct:.1f}%</td></tr>
                    <tr><th>Sans IA</th><td>{ai_without_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- Findings -->
            <div class="dashboard-card">
                <h3>Analyzer Findings</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        <div class="bar-group">
                            <div class="bar-value">{f_crit}</div>
                            <div class="bar color-critique" style="height: {(f_crit/max_f)*100}%;"></div>
                            <div class="bar-label">Critique</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_maj}</div>
                            <div class="bar color-majeur" style="height: {(f_maj/max_f)*100}%;"></div>
                            <div class="bar-label">Majeur</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_min}</div>
                            <div class="bar color-mineur" style="height: {(f_min/max_f)*100}%;"></div>
                            <div class="bar-label">Mineur</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_inf}</div>
                            <div class="bar color-info" style="height: {(f_inf/max_f)*100}%;"></div>
                            <div class="bar-label">Info</div>
                        </div>
                    </div>
                </div>
                <table class="dashboard-table">
                    <thead>
                        <tr><th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>{f_crit}</td><td>{f_maj}</td><td>{f_min}</td><td>{f_inf}</td></tr>
                        <tr><th colspan="2">Total</th><td colspan="2"><strong>{f_total}</strong></td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="page-break"></div>

        <div class="dashboard-header" style="margin-top: 20px;">
            <h1>Evolution des releases : {html_value(selected.alias)}</h1>
        </div>

        <div class="dashboard-grid">
            <!-- Evolution Adoption -->
            <div class="dashboard-card">
                <h3>Adoption and Adaptation</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {adoption_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-adoption"></div> adoption</div>
                    <div class="legend-item"><div class="legend-dot color-adaptation"></div> adaptation</div>
                </div>
                {adoption_table}
            </div>

            <!-- Evolution Data Model -->
            <div class="dashboard-card">
                <h3>Data Model standard vs custom</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {dm_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-standard"></div> standard</div>
                    <div class="legend-item"><div class="legend-dot color-custom"></div> custom</div>
                </div>
                {dm_table}
            </div>

            <!-- Evolution AI -->
            <div class="dashboard-card">
                <h3>Construit Avec ou Sans IA</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {ai_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-ai-with"></div> avec IA</div>
                    <div class="legend-item"><div class="legend-dot color-ai-without"></div> sans IA</div>
                </div>
                {ai_table}
            </div>

            <!-- Evolution Findings -->
            <div class="dashboard-card">
                <h3>Analyzer Findings</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {findings_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-critique"></div> Critique</div>
                    <div class="legend-item"><div class="legend-dot color-majeur"></div> Majeur</div>
                    <div class="legend-item"><div class="legend-dot color-mineur"></div> Mineur</div>
                    <div class="legend-item"><div class="legend-dot color-info"></div> Info</div>
                </div>
                {findings_table}
            </div>
        </div>
    </div>
    """
    # We use a custom shell for the dashboard to avoid the standard page overhead
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Dashboard {html_value(selected.alias)}</title>
    <style>
        @page {{ size: A4; margin: 0; }}
        body {{ margin: 0; padding: 0; background: #f0f2f5; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""


def render_comparison(
    new: HistoryEntry,
    old: HistoryEntry,
    current_path: Path,
    assets_dir: Path,
) -> str:
    """Render a metadata comparison between two generations."""
    
    # 1. Scan directories to find added, modified, deleted files
    new_dir = Path(new.source_dir)
    old_dir = Path(old.source_dir)
    
    new_files = {p.relative_to(new_dir): p for p in new_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}
    old_files = {p.relative_to(old_dir): p for p in old_dir.rglob("*") if p.is_file() and ".vs" not in p.parts}
    
    added = sorted([rel for rel in new_files if rel not in old_files])
    deleted = sorted([rel for rel in old_files if rel not in new_files])
    modified = []
    for rel in new_files:
        if rel in old_files:
            # Simple size/mtime check for "modified" or could do hash, but let's stay simple
            if new_files[rel].stat().st_size != old_files[rel].stat().st_size or \
               new_files[rel].stat().st_mtime != old_files[rel].stat().st_mtime:
                modified.append(rel)
    modified.sort()

    def _get_metadata_type(rel_path: Path) -> str:
        parts = rel_path.parts
        if "objects" in parts: return "Object/Field"
        if "classes" in parts: return "Apex Class"
        if "triggers" in parts: return "Apex Trigger"
        if "flows" in parts: return "Flow"
        if "profiles" in parts: return "Profile"
        if "permissionsets" in parts: return "Permission Set"
        if "lwc" in parts: return "LWC"
        if "aura" in parts: return "Aura"
        if "flexipages" in parts: return "Lightning Page"
        if "omniIntegrationProcedures" in parts: return "Omni IP"
        if "omniScripts" in parts: return "OmniScript"
        if "omniUiCard" in parts: return "Omni FlexCard"
        if "omniDataTransforms" in parts: return "Omni Data Transform"
        return "Autre"

    diff_rows = ""
    type_counts = {} # (type, action) -> count

    for rel in added:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Ajouté")] = type_counts.get((mtype, "Ajouté"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: green; font-weight: bold;'>Ajouté</span></td></tr>\n"
    
    for rel in modified:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Modifié")] = type_counts.get((mtype, "Modifié"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: orange; font-weight: bold;'>Modifié</span></td></tr>\n"
    
    for rel in deleted:
        mtype = _get_metadata_type(rel)
        type_counts[(mtype, "Supprimé")] = type_counts.get((mtype, "Supprimé"), 0) + 1
        diff_rows += f"<tr><td>{html_value(str(rel))}</td><td>{mtype}</td><td><span style='color: red; font-weight: bold;'>Supprimé</span></td></tr>\n"

    # Summary by type
    all_types = sorted(list(set(t for t, a in type_counts.keys())))
    type_summary_rows = ""
    for t in all_types:
        a_count = type_counts.get((t, "Ajouté"), 0)
        m_count = type_counts.get((t, "Modifié"), 0)
        d_count = type_counts.get((t, "Supprimé"), 0)
        total_t = a_count - d_count
        type_summary_rows += f"""
            <tr>
                <td>{t}</td>
                <td><span style="color: green;">+{a_count}</span></td>
                <td><span style="color: orange;">{m_count}</span></td>
                <td><span style="color: red;">-{d_count}</span></td>
                <td>{total_t:+d}</td>
            </tr>
        """

    # Volumetry summary based on actual file diff
    body = f"""
    <style>
        .resizable-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }}
        .resizable-table th {{
            position: relative;
            padding: 10px;
            border: 1px solid #ddd;
            background: #f9f9f9;
        }}
        .resizable-table td {{
            padding: 8px;
            border: 1px solid #ddd;
            word-break: break-all;
        }}
        /* Column resizing handle */
        .resizer {{
            position: absolute;
            top: 0;
            right: 0;
            width: 5px;
            cursor: col-resize;
            user-select: none;
            height: 100%;
        }}
        .resizer:hover {{
            background: #aaa;
        }}
    </style>

    <div class="topnav"><a href="index.html">Retour à l'index</a></div>
    <h1>Comparaison de métadonnées : {html_value(new.alias)}</h1>
    <p>Comparaison entre la génération #{new.generation_number} ({new.timestamp}) et la génération #{old.generation_number} ({old.timestamp}).</p>
    
    <div class="section">
        <h2>Résumé des changements par type</h2>
        <table>
            <thead>
                <tr><th>Type de métadonnée</th><th>Ajouts</th><th>Modifs</th><th>Suppr.</th><th>Diff nette</th></tr>
            </thead>
            <tbody>
                {type_summary_rows if type_summary_rows else '<tr><td colspan="5" class="empty">Aucun changement.</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Résumé global (fichiers)</h2>
        <table>
            <thead>
                <tr><th>Indicateur</th><th>#{old.generation_number}</th><th>#{new.generation_number}</th><th>Ajouts</th><th>Modifs</th><th>Suppr.</th><th>Total Diff</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>Total Fichiers</td>
                    <td>{len(old_files)}</td>
                    <td>{len(new_files)}</td>
                    <td><span style="color: green;">+{len(added)}</span></td>
                    <td><span style="color: orange;">{len(modified)}</span></td>
                    <td><span style="color: red;">-{len(deleted)}</span></td>
                    <td>{len(added) - len(deleted):+d}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Détail des fichiers modifiés</h2>
        <p><small><i>Astuce : Vous pouvez redimensionner les colonnes en glissant les bordures des en-têtes.</i></small></p>
        <div style="max-height: 600px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px;">
            <table id="diffTable" class="resizable-table">
                <thead>
                    <tr>
                        <th style="width: 70%;">Chemin du fichier<div class="resizer"></div></th>
                        <th style="width: 15%;">Type<div class="resizer"></div></th>
                        <th style="width: 15%;">Action<div class="resizer"></div></th>
                    </tr>
                </thead>
                <tbody>
                    {diff_rows if diff_rows else '<tr><td colspan="3" class="empty">Aucun changement détecté.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <script>
    // Simple table resizer logic
    document.addEventListener('DOMContentLoaded', function() {{
        const table = document.getElementById('diffTable');
        const cols = table.querySelectorAll('th');
        
        cols.forEach(col => {{
            const resizer = col.querySelector('.resizer');
            if (!resizer) return;
            
            let x = 0;
            let w = 0;
            
            const mouseDownHandler = function(e) {{
                x = e.clientX;
                const styles = window.getComputedStyle(col);
                w = parseInt(styles.width, 10);
                
                document.addEventListener('mousemove', mouseMoveHandler);
                document.addEventListener('mouseup', mouseUpHandler);
                resizer.classList.add('resizing');
            }};
            
            const mouseMoveHandler = function(e) {{
                const dx = e.clientX - x;
                col.style.width = `${{w + dx}}px`;
            }};
            
            const mouseUpHandler = function() {{
                document.removeEventListener('mousemove', mouseMoveHandler);
                document.removeEventListener('mouseup', mouseUpHandler);
                resizer.classList.remove('resizing');
            }};
            
            resizer.addEventListener('mousedown', mouseDownHandler);
        }});
    }});
    </script>

    <div class="section">
        <h2>Répertoires sources</h2>
        <dl>
            <dt>Source #{old.generation_number}:</dt><dd><code>{html_value(old.source_dir)}</code></dd>
            <dt>Source #{new.generation_number}:</dt><dd><code>{html_value(new.source_dir)}</code></dd>
        </dl>
    </div>
    """
    return render_page(f"Comparaison {new.alias}", body, current_path, assets_dir, include_mermaid=False)


def write_history_report(
    entry: HistoryEntry,
    report_type: str,
    content: str,
    filename: str,
) -> Path:
    """Write a history report to the output directory of the entry."""
    output_dir = Path(entry.output_dir) / "html"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    write_text(path, content)
    return path
