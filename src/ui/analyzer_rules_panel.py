"""Configuration tab listing the static-analysis rules.

The panel lets the user enable/disable rules and persist the choice back to
``rules.xml``. It used to live inline in :class:`src.ui.application.Application`
as roughly twenty private methods. This module exposes only two entry points
(``build_panel`` and ``persist_changes``); the rest of the logic is internal.
"""

from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.analyzer.models import Rule
from src.analyzer.rule_catalog import RuleCatalog

if TYPE_CHECKING:
    from src.ui.application import Application


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_panel(app: Application, parent: ttk.Frame) -> None:
    """Render the analyzer-rules tab into ``parent``."""

    _build_header(app, parent)
    _build_file_row(app, parent)
    _build_controls(app, parent)
    filters = ttk.Frame(parent)
    filters.pack(fill="x", pady=(0, 8))
    scope_combo = _build_filters(app, filters)

    list_inner = _build_list_pane(app, parent)

    rules = _load_rules_for_editor(app)
    app._analyzer_rules_cache = rules

    scopes_seen = sorted({rule.scope for rule in rules})
    scope_combo.configure(
        values=[app._t("configuration_rules_filter_all")]
        + [_scope_display(app, scope) for scope in scopes_seen]
    )

    _render_rule_rows(app, list_inner, rules)
    _refresh_rule_count(app)


def persist_changes(app: Application) -> None:
    """Persist enabled/disabled state of every rule to ``rules.xml``."""

    if not app._analyzer_rule_vars:
        return
    path = app._analyzer_rules_file
    if not path.exists():
        app._append_log(app._t("configuration_rules_file_missing", path=str(path)))
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return

    changes = 0
    updated = raw
    for rule in app._analyzer_rules_cache:
        var = app._analyzer_rule_vars.get(rule.id)
        if var is None:
            continue
        desired = bool(var.get())
        if desired == rule.enabled:
            continue
        new_value = "true" if desired else "false"
        pattern = re.compile(
            r'(<rule\s+id="' + re.escape(rule.id) + r'"[^>]*?)enabled="(?:true|false)"',
            re.DOTALL,
        )
        updated, count = pattern.subn(
            lambda m, value=new_value: m.group(1) + f'enabled="{value}"',
            updated,
            count=1,
        )
        if count:
            changes += count
    if changes == 0:
        return
    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        app._append_log(app._t("configuration_rules_write_error", error=str(exc)))
        return
    app._append_log(
        app._t("configuration_rules_saved", path=str(path), count=changes)
    )


def reset_state(app: Application) -> None:
    """Clear panel state held on the app instance.

    Called after the configuration window closes to release Tk widget
    references that would otherwise outlive the window.
    """

    app._analyzer_rule_vars = {}
    app._analyzer_rules_cache = []
    app._analyzer_rule_rows = []
    app._analyzer_rule_count_var = None
    app._analyzer_rule_detail_widget = None
    app._analyzer_rule_filter_severity = None
    app._analyzer_rule_filter_category = None
    app._analyzer_rule_filter_scope = None


# ---------------------------------------------------------------------------
# Header / controls
# ---------------------------------------------------------------------------


def _build_header(app: Application, parent: ttk.Frame) -> None:
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(0, 6))
    ttk.Label(
        header,
        text=app._t("configuration_rules_title"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        header,
        text=app._t("configuration_rules_description"),
        wraplength=880,
        justify="left",
    ).pack(anchor="w", pady=(2, 6))


def _build_file_row(app: Application, parent: ttk.Frame) -> None:
    file_row = ttk.Frame(parent)
    file_row.pack(fill="x", pady=(0, 8))
    ttk.Label(
        file_row,
        text=app._t("configuration_rules_file_label"),
        font=("Segoe UI", 9, "bold"),
    ).pack(side="left")
    ttk.Label(
        file_row,
        text=str(app._analyzer_rules_file),
        foreground="#334155",
    ).pack(side="left", padx=(6, 0))


def _build_controls(app: Application, parent: ttk.Frame) -> None:
    controls = ttk.Frame(parent)
    controls.pack(fill="x", pady=(0, 6))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_enable_all"),
        command=lambda: _set_all_rules(app, True),
    ).pack(side="left")
    ttk.Button(
        controls,
        text=app._t("configuration_rules_disable_all"),
        command=lambda: _set_all_rules(app, False),
    ).pack(side="left", padx=(6, 0))
    ttk.Button(
        controls,
        text=app._t("configuration_rules_reload"),
        command=lambda: _reload_rules(app),
    ).pack(side="left", padx=(6, 0))

    count_var = tk.StringVar(value="")
    app._analyzer_rule_count_var = count_var
    ttk.Label(controls, textvariable=count_var, foreground="#475569").pack(side="right")


def _build_filters(app: Application, filters: ttk.Frame) -> ttk.Combobox:
    severities = [app._t("configuration_rules_filter_all")] + [
        _severity_display(app, level) for level in app.ANALYZER_SEVERITY_ORDER
    ]
    app._analyzer_rule_filter_severity = tk.StringVar(value=severities[0])
    _filter_combo_row(
        filters,
        app._t("configuration_rules_filter_severity"),
        app._analyzer_rule_filter_severity,
        severities,
    )

    categories = [app._t("configuration_rules_filter_all"), "Trusted", "Easy", "Adaptable"]
    app._analyzer_rule_filter_category = tk.StringVar(value=categories[0])
    _filter_combo_row(
        filters,
        app._t("configuration_rules_filter_category"),
        app._analyzer_rule_filter_category,
        categories,
    )

    scopes_labels = [app._t("configuration_rules_filter_all")]
    app._analyzer_rule_filter_scope = tk.StringVar(value=scopes_labels[0])
    scope_combo_container = ttk.Frame(filters)
    scope_combo_container.pack(side="left", padx=(8, 0))
    ttk.Label(
        scope_combo_container,
        text=app._t("configuration_rules_filter_scope"),
    ).pack(side="left")
    scope_combo = ttk.Combobox(
        scope_combo_container,
        textvariable=app._analyzer_rule_filter_scope,
        values=scopes_labels,
        state="readonly",
        width=22,
    )
    scope_combo.pack(side="left", padx=(4, 0))

    for var in (
        app._analyzer_rule_filter_severity,
        app._analyzer_rule_filter_category,
        app._analyzer_rule_filter_scope,
    ):
        var.trace_add("write", lambda *_args: _apply_filters(app))

    return scope_combo


def _filter_combo_row(
    parent: ttk.Frame,
    label_text: str,
    variable: tk.Variable,
    values: list[str],
) -> None:
    container = ttk.Frame(parent)
    container.pack(side="left", padx=(0, 8))
    ttk.Label(container, text=label_text).pack(side="left")
    combo = ttk.Combobox(
        container,
        textvariable=variable,
        values=values,
        state="readonly",
        width=18,
    )
    combo.pack(side="left", padx=(4, 0))


# ---------------------------------------------------------------------------
# List + detail panes
# ---------------------------------------------------------------------------


def _build_list_pane(app: Application, parent: ttk.Frame) -> ttk.Frame:
    paned = ttk.PanedWindow(parent, orient="vertical")
    paned.pack(fill="both", expand=True)

    list_frame = ttk.Frame(paned)
    paned.add(list_frame, weight=3)

    detail_frame = ttk.LabelFrame(
        paned,
        text=app._t("configuration_rules_detail_title"),
        padding=8,
    )
    paned.add(detail_frame, weight=2)

    list_canvas = tk.Canvas(list_frame, highlightthickness=0, height=280)
    list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=list_canvas.yview)
    list_inner = ttk.Frame(list_canvas)
    list_inner.bind(
        "<Configure>",
        lambda _e: list_canvas.configure(scrollregion=list_canvas.bbox("all")),
    )
    list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
    list_canvas.configure(yscrollcommand=list_scrollbar.set)
    list_canvas.pack(side="left", fill="both", expand=True)
    list_scrollbar.pack(side="right", fill="y")

    list_canvas.bind(
        "<Enter>",
        lambda _e: list_canvas.bind_all(
            "<MouseWheel>",
            lambda event: list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"),
        ),
    )
    list_canvas.bind("<Leave>", lambda _e: list_canvas.unbind_all("<MouseWheel>"))

    detail_widget = scrolledtext.ScrolledText(
        detail_frame,
        wrap="word",
        height=9,
        font=("Segoe UI", 9),
        state="disabled",
    )
    detail_widget.pack(fill="both", expand=True)
    app._analyzer_rule_detail_widget = detail_widget
    _set_detail_text(app, app._t("configuration_rules_detail_empty"))

    ref_row = ttk.Frame(detail_frame)
    ref_row.pack(fill="x", pady=(6, 0))
    app._analyzer_rule_selected_reference = ""
    ttk.Button(
        ref_row,
        text=app._t("configuration_rules_detail_open_reference"),
        command=lambda: _open_selected_reference(app),
    ).pack(side="right")

    app._analyzer_rule_vars = {}
    app._analyzer_rule_rows = []
    return list_inner


# ---------------------------------------------------------------------------
# Severity & scope display helpers
# ---------------------------------------------------------------------------


def _severity_display(app: Application, severity: str) -> str:
    return app._t(f"configuration_rules_severity_{severity.lower()}")


def _severity_code_from_display(app: Application, display: str) -> str | None:
    for level in app.ANALYZER_SEVERITY_ORDER:
        if _severity_display(app, level) == display:
            return level
    return None


def _scope_display(app: Application, scope: str) -> str:
    key = f"configuration_rules_scope_{scope}"
    translated = app._t(key)
    if translated == key:
        return scope
    return translated


def _scope_code_from_display(app: Application, display: str) -> str | None:
    for rule in app._analyzer_rules_cache:
        if _scope_display(app, rule.scope) == display:
            return rule.scope
    return None


# ---------------------------------------------------------------------------
# Loading & rendering
# ---------------------------------------------------------------------------


def _load_rules_for_editor(app: Application) -> list[Rule]:
    try:
        catalog = RuleCatalog.load(app._analyzer_rules_file)
    except OSError as exc:
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return []
    except Exception as exc:  # parse errors
        app._append_log(app._t("configuration_rules_load_error", error=str(exc)))
        return []
    if not app._analyzer_rules_file.exists():
        app._append_log(
            app._t("configuration_rules_file_missing", path=str(app._analyzer_rules_file))
        )
    return catalog.all


def _render_rule_rows(app: Application, parent: ttk.Frame, rules: list[Rule]) -> None:
    for child in parent.winfo_children():
        child.destroy()
    app._analyzer_rule_rows = []
    app._analyzer_rule_vars = {}

    grouped: dict[str, list[Rule]] = {}
    for rule in rules:
        grouped.setdefault(rule.scope, []).append(rule)
    for scope_rules in grouped.values():
        scope_rules.sort(
            key=lambda r: (
                app.ANALYZER_SEVERITY_ORDER.index(r.severity)
                if r.severity in app.ANALYZER_SEVERITY_ORDER
                else 99,
                r.id,
            )
        )

    ordered_scopes = sorted(
        grouped.keys(), key=lambda s: _scope_display(app, s).lower()
    )
    for scope in ordered_scopes:
        section = ttk.LabelFrame(parent, text=_scope_display(app, scope), padding=6)
        section.pack(fill="x", pady=(2, 4), padx=2)
        for rule in grouped[scope]:
            _render_single_rule_row(app, section, rule)


def _render_single_rule_row(app: Application, parent: ttk.Frame, rule: Rule) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=1)

    var = tk.BooleanVar(value=rule.enabled)
    app._analyzer_rule_vars[rule.id] = var
    var.trace_add("write", lambda *_args: _refresh_rule_count(app))

    check = ttk.Checkbutton(row, variable=var)
    check.pack(side="left", padx=(0, 4))

    severity_color = app.ANALYZER_SEVERITY_COLORS.get(rule.severity, "#1e293b")
    severity_label = tk.Label(
        row,
        text=_severity_display(app, rule.severity),
        foreground="white",
        background=severity_color,
        font=("Segoe UI", 8, "bold"),
        padx=6,
        pady=1,
    )
    severity_label.pack(side="left", padx=(0, 4))

    id_label = ttk.Label(row, text=rule.id, font=("Consolas", 9), foreground="#334155")
    id_label.pack(side="left", padx=(0, 6))

    title_label = ttk.Label(row, text=rule.title, font=("Segoe UI", 9))
    title_label.pack(side="left", fill="x", expand=True)

    category_text = rule.category
    if rule.subcategory:
        category_text = f"{rule.category} / {rule.subcategory}"
    category_label = ttk.Label(
        row, text=category_text, foreground="#475569", font=("Segoe UI", 8, "italic")
    )
    category_label.pack(side="right", padx=(6, 0))

    def _select(_event=None, _rule: Rule = rule) -> None:
        _select_rule(app, _rule)

    for widget in (row, severity_label, id_label, title_label, category_label):
        widget.bind("<Button-1>", _select)

    app._analyzer_rule_rows.append({"rule": rule, "row": row})


# ---------------------------------------------------------------------------
# Selection / filtering
# ---------------------------------------------------------------------------


def _select_rule(app: Application, rule: Rule) -> None:
    app._analyzer_rule_selected_reference = rule.reference or ""
    lines: list[str] = [f"{rule.id} - {rule.title}", ""]
    lines.append(
        f"{app._t('configuration_rules_column_severity')}: "
        f"{_severity_display(app, rule.severity)}"
    )
    category_text = rule.category
    if rule.subcategory:
        category_text = f"{rule.category} / {rule.subcategory}"
    lines.append(f"{app._t('configuration_rules_column_category')}: {category_text}")
    lines.append("")
    if rule.description:
        lines.append(app._t("configuration_rules_detail_description") + ":")
        lines.append(rule.description)
        lines.append("")
    if rule.rationale:
        lines.append(app._t("configuration_rules_detail_rationale") + ":")
        lines.append(rule.rationale)
        lines.append("")
    if rule.remediation:
        lines.append(app._t("configuration_rules_detail_remediation") + ":")
        lines.append(rule.remediation)
        lines.append("")
    if rule.source:
        lines.append(app._t("configuration_rules_detail_source") + ": " + rule.source)
    if rule.reference:
        lines.append(
            app._t("configuration_rules_detail_reference") + ": " + rule.reference
        )
    _set_detail_text(app, "\n".join(lines))


def _set_detail_text(app: Application, text: str) -> None:
    widget = app._analyzer_rule_detail_widget
    if widget is None:
        return
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")


def _open_selected_reference(app: Application) -> None:
    reference = app._analyzer_rule_selected_reference
    if not reference:
        return
    try:
        webbrowser.open(reference)
    except Exception as exc:  # pragma: no cover - browser-dependent
        app._append_log(f"{exc}")


def _set_all_rules(app: Application, enabled: bool) -> None:
    for rule_id, var in app._analyzer_rule_vars.items():
        rule = next(
            (r for r in app._analyzer_rules_cache if r.id == rule_id), None
        )
        if rule is None:
            continue
        if _rule_visible(app, rule):
            var.set(enabled)


def _apply_filters(app: Application) -> None:
    for entry in app._analyzer_rule_rows:
        rule: Rule = entry["rule"]  # type: ignore[assignment]
        row = entry["row"]
        if _rule_visible(app, rule):
            row.pack(fill="x", pady=1)
        else:
            row.pack_forget()


def _rule_visible(app: Application, rule: Rule) -> bool:
    all_label = app._t("configuration_rules_filter_all")
    if app._analyzer_rule_filter_severity is not None:
        chosen = app._analyzer_rule_filter_severity.get()
        if chosen and chosen != all_label:
            code = _severity_code_from_display(app, chosen)
            if code and rule.severity != code:
                return False
    if app._analyzer_rule_filter_category is not None:
        chosen = app._analyzer_rule_filter_category.get()
        if chosen and chosen != all_label and rule.category != chosen:
            return False
    if app._analyzer_rule_filter_scope is not None:
        chosen = app._analyzer_rule_filter_scope.get()
        if chosen and chosen != all_label:
            code = _scope_code_from_display(app, chosen)
            if code and rule.scope != code:
                return False
    return True


def _refresh_rule_count(app: Application) -> None:
    var = app._analyzer_rule_count_var
    if var is None:
        return
    total = len(app._analyzer_rule_vars)
    enabled = sum(1 for v in app._analyzer_rule_vars.values() if v.get())
    var.set(
        app._t("configuration_rules_enabled_count", enabled=enabled, total=total)
    )


def _reload_rules(app: Application) -> None:
    if app.configuration_window is None or not app.configuration_window.winfo_exists():
        return
    app.configuration_window.destroy()
    app._append_log(
        app._t("configuration_rules_reloaded", path=str(app._analyzer_rules_file))
    )
    app._show_configuration_screen()
