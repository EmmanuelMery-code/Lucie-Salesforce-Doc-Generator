"""Configuration tab driving the *Posture Adopt vs Adapt* calculation.

The panel mirrors the analyzer-rules and AI-tags tabs: it exposes a single
``build_panel`` entry point used by
:class:`src.ui.application.Application._show_configuration_screen` and a
companion ``collect_config`` helper that returns the edited list back to
the application when the user presses *Save*.

For each capability the user can pick a manual level
(``Adopt (OOTB)`` / ``Adopt declaratif`` / ``Adapt (declaratif)`` /
``Adapt (code)``) or fall back to the heuristic assessor (``Auto``), and
override the weight. New capabilities can be added through a small dialog
that suggests metadata counters (custom objects, flows, LWC, ...) so the
choice stays grounded in the snapshot.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from src.core.customization_metrics import (
    CAPABILITY_CATALOG,
    CAPABILITY_LEVEL_ORDER,
    CapabilityLevel,
    PostureCapabilityConfig,
    SNAPSHOT_METRIC_KEYS,
    snapshot_metric_count,
)
from src.ui.settings import default_posture_config

if TYPE_CHECKING:
    from src.ui.application import Application


_AUTO_LEVEL_TOKEN = "__auto__"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_panel(app: "Application", parent: ttk.Frame) -> None:
    """Render the Posture configuration tab into ``parent``."""

    state: dict[str, object] = {
        "rows": [],
        "table_frame": None,
        "summary_label": None,
    }
    app._posture_panel_state = state

    ttk.Label(
        parent,
        text=app._t("configuration_posture_title"),
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor="w", pady=(0, 4))

    ttk.Label(
        parent,
        text=app._t("configuration_posture_description"),
        wraplength=820,
        justify="left",
    ).pack(anchor="w", pady=(0, 8))

    legend = ttk.Label(
        parent,
        text=app._t("configuration_posture_legend"),
        wraplength=820,
        justify="left",
        foreground="#475569",
    )
    legend.pack(anchor="w", pady=(0, 10))

    table_frame = ttk.Frame(parent)
    table_frame.pack(fill="both", expand=True)
    state["table_frame"] = table_frame

    button_row = ttk.Frame(parent)
    button_row.pack(fill="x", pady=(8, 0))
    ttk.Button(
        button_row,
        text=app._t("configuration_posture_add"),
        command=lambda: _add_capability_dialog(app),
    ).pack(side="left")
    ttk.Button(
        button_row,
        text=app._t("configuration_posture_reset"),
        command=lambda: _reset_capabilities(app),
    ).pack(side="right")

    summary_label = ttk.Label(
        parent,
        text="",
        wraplength=820,
        justify="left",
        foreground="#1f2937",
    )
    summary_label.pack(anchor="w", pady=(8, 0))
    state["summary_label"] = summary_label

    _render_table(app)


def collect_config(app: "Application") -> list[PostureCapabilityConfig]:
    """Return the posture configuration currently displayed in the tab.

    Falls back to ``app.posture_config`` when the panel was not rendered.
    Invalid weight inputs (non-integer, negative) are clamped to the
    capability's previous value so saving is always non-destructive.
    """

    state = getattr(app, "_posture_panel_state", None)
    if state is None:
        return list(app.posture_config)

    rows: list[dict] = state.get("rows", [])  # type: ignore[assignment]
    config: list[PostureCapabilityConfig] = []
    for row in rows:
        weight = _read_weight(row)
        level = _read_level(row)
        config.append(
            PostureCapabilityConfig(
                capability_id=row["capability_id"],
                label=row["label"],
                weight=weight,
                level=level,
                custom=bool(row.get("custom")),
                metadata_key=str(row.get("metadata_key", "")),
            )
        )
    return config


def reset_state(app: "Application") -> None:
    """Drop widget references after the configuration window closes."""

    app._posture_panel_state = None


# ---------------------------------------------------------------------------
# Internal rendering
# ---------------------------------------------------------------------------


def _render_table(app: "Application") -> None:
    state = app._posture_panel_state
    if state is None:
        return
    table_frame: ttk.Frame = state["table_frame"]  # type: ignore[assignment]
    for child in table_frame.winfo_children():
        child.destroy()

    headers = (
        app._t("configuration_posture_column_capability"),
        app._t("configuration_posture_column_weight"),
        app._t("configuration_posture_column_level"),
        app._t("configuration_posture_column_count"),
        app._t("configuration_posture_column_actions"),
    )
    for col_index, weight in enumerate((4, 1, 3, 2, 2)):
        table_frame.grid_columnconfigure(col_index, weight=weight)
    for col_index, header in enumerate(headers):
        ttk.Label(
            table_frame,
            text=header,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=col_index, sticky="w", padx=4, pady=(0, 4))

    rows: list[dict] = []
    state["rows"] = rows

    auto_label = app._t("configuration_posture_level_auto")
    display_to_level: dict[str, CapabilityLevel | None] = {auto_label: None}
    for level in CAPABILITY_LEVEL_ORDER:
        display_to_level[_level_display(app, level)] = level
    level_choices = [auto_label] + [
        _level_display(app, level) for level in CAPABILITY_LEVEL_ORDER
    ]

    metrics = getattr(app, "latest_metrics", None)

    for row_index, entry in enumerate(app.posture_config, start=1):
        weight_var = tk.StringVar(value=str(entry.weight))
        level_var = tk.StringVar(value=_level_to_display(app, entry.level))

        capability_label = entry.label or entry.capability_id
        if entry.custom:
            capability_label = f"{capability_label}  ({app._t('configuration_posture_custom_tag')})"
        ttk.Label(
            table_frame,
            text=capability_label,
            wraplength=320,
            justify="left",
        ).grid(row=row_index, column=0, sticky="w", padx=4, pady=2)

        ttk.Entry(
            table_frame,
            textvariable=weight_var,
            width=6,
            justify="center",
        ).grid(row=row_index, column=1, sticky="w", padx=4, pady=2)

        ttk.Combobox(
            table_frame,
            textvariable=level_var,
            values=level_choices,
            state="readonly",
            width=24,
        ).grid(row=row_index, column=2, sticky="ew", padx=4, pady=2)

        count_text = ""
        if entry.metadata_key:
            label = SNAPSHOT_METRIC_KEYS.get(entry.metadata_key, entry.metadata_key)
            if metrics is not None:
                count_value = int(getattr(metrics, entry.metadata_key, 0) or 0)
                count_text = f"{label} : {count_value}"
            else:
                count_text = label
        ttk.Label(
            table_frame,
            text=count_text,
            wraplength=200,
            justify="left",
            foreground="#475569",
        ).grid(row=row_index, column=3, sticky="w", padx=4, pady=2)

        action_frame = ttk.Frame(table_frame)
        action_frame.grid(row=row_index, column=4, sticky="w", padx=4, pady=2)
        if entry.custom:
            ttk.Button(
                action_frame,
                text=app._t("configuration_posture_remove"),
                width=10,
                command=lambda cap_id=entry.capability_id: _remove_capability(app, cap_id),
            ).pack(side="left")

        rows.append(
            {
                "capability_id": entry.capability_id,
                "label": entry.label,
                "custom": entry.custom,
                "metadata_key": entry.metadata_key,
                "weight_var": weight_var,
                "level_var": level_var,
                "previous_weight": entry.weight,
                "display_to_level": display_to_level,
            }
        )

    _refresh_summary(app)


def _refresh_summary(app: "Application") -> None:
    state = app._posture_panel_state
    if state is None:
        return
    summary_label = state.get("summary_label")
    if summary_label is None:
        return
    config = collect_config(app)
    total_weight = sum(max(c.weight, 0) for c in config)
    adopt_weight = sum(
        max(c.weight, 0)
        for c in config
        if c.level in (CapabilityLevel.ADOPT, CapabilityLevel.ADOPT_DECLARATIVE)
    )
    forced = sum(1 for c in config if c.level is not None)
    auto = len(config) - forced
    if total_weight:
        ratio = adopt_weight / total_weight * 100.0
    else:
        ratio = 0.0
    summary_label.configure(  # type: ignore[union-attr]
        text=app._t(
            "configuration_posture_summary",
            count=len(config),
            forced=forced,
            auto=auto,
            ratio=f"{ratio:.1f}",
            total=total_weight,
        )
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _level_display(app: "Application", level: CapabilityLevel) -> str:
    return app._t(_LEVEL_TRANSLATION_KEYS[level])


def _level_to_display(app: "Application", level: CapabilityLevel | None) -> str:
    if level is None:
        return app._t("configuration_posture_level_auto")
    return _level_display(app, level)


_LEVEL_TRANSLATION_KEYS: dict[CapabilityLevel, str] = {
    CapabilityLevel.ADOPT: "configuration_posture_level_adopt",
    CapabilityLevel.ADOPT_DECLARATIVE: "configuration_posture_level_adopt_declarative",
    CapabilityLevel.ADAPT_LOW: "configuration_posture_level_adapt_low",
    CapabilityLevel.ADAPT_HIGH: "configuration_posture_level_adapt_high",
}


def _display_to_level(app: "Application", display: str) -> CapabilityLevel | None:
    if display.strip() == app._t("configuration_posture_level_auto"):
        return None
    for level in CAPABILITY_LEVEL_ORDER:
        if _level_display(app, level) == display:
            return level
    return None


def _read_weight(row: dict) -> int:
    raw = row["weight_var"].get().strip() if hasattr(row["weight_var"], "get") else ""
    if raw.lstrip("-").isdigit():
        value = int(raw)
        return max(value, 0)
    previous = row.get("previous_weight", 0)
    try:
        return int(previous)
    except (TypeError, ValueError):
        return 0


def _read_level(row: dict) -> CapabilityLevel | None:
    """Return the chosen level, or ``None`` for "Auto"."""

    var = row.get("level_var")
    if var is None:
        return None
    display = var.get() if hasattr(var, "get") else ""
    mapping = row.get("display_to_level") or {}
    if isinstance(mapping, dict) and display in mapping:
        return mapping[display]
    # Fallback: match the enum's stored value (the level enum values are
    # already user-facing strings).
    text = display.strip()
    for level in CAPABILITY_LEVEL_ORDER:
        if level.value == text:
            return level
    return None


# ---------------------------------------------------------------------------
# User actions
# ---------------------------------------------------------------------------


def _remove_capability(app: "Application", capability_id: str) -> None:
    app.posture_config = [
        entry
        for entry in collect_config(app)
        if entry.capability_id != capability_id
    ]
    _render_table(app)


def _reset_capabilities(app: "Application") -> None:
    if not messagebox.askyesno(
        app._t("info_title"),
        app._t("configuration_posture_reset_confirm"),
        parent=app.configuration_window or app,
    ):
        return
    app.posture_config = default_posture_config()
    _render_table(app)


def _add_capability_dialog(app: "Application") -> None:
    """Open a small modal that walks the user through adding a capability.

    The dialog suggests metadata-backed counters (custom objects, flows,
    Apex classes, LWC, ...) so the new capability is grounded in the
    snapshot. The user can also leave the metadata empty to add a
    label-only capability.
    """

    used_labels: set[str] = {
        entry.label.casefold() for entry in collect_config(app) if entry.label
    }

    parent = app.configuration_window or app
    dialog = tk.Toplevel(parent)
    dialog.title(app._t("configuration_posture_add_title"))
    dialog.geometry("520x420")
    dialog.transient(parent)
    dialog.grab_set()

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=app._t("configuration_posture_add_description"),
        wraplength=480,
        justify="left",
    ).pack(anchor="w", pady=(0, 10))

    label_frame = ttk.Frame(container)
    label_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(label_frame, text=app._t("configuration_posture_field_label"), width=22).pack(side="left")
    label_var = tk.StringVar()
    ttk.Entry(label_frame, textvariable=label_var).pack(
        side="left", fill="x", expand=True
    )

    metric_frame = ttk.Frame(container)
    metric_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(
        metric_frame, text=app._t("configuration_posture_field_metadata"), width=22
    ).pack(side="left")
    metric_choices = [app._t("configuration_posture_metadata_none")]
    metric_keys: list[str] = [""]
    metrics = getattr(app, "latest_metrics", None)
    for key, label in SNAPSHOT_METRIC_KEYS.items():
        count = snapshot_metric_count_safe(metrics, key)
        if metrics is not None:
            metric_choices.append(f"{label}  ({count})")
        else:
            metric_choices.append(label)
        metric_keys.append(key)
    metric_var = tk.StringVar(value=metric_choices[0])
    metric_combo = ttk.Combobox(
        metric_frame, textvariable=metric_var, values=metric_choices, state="readonly"
    )
    metric_combo.pack(side="left", fill="x", expand=True)

    weight_frame = ttk.Frame(container)
    weight_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(
        weight_frame, text=app._t("configuration_posture_field_weight"), width=22
    ).pack(side="left")
    weight_var = tk.StringVar(value="2")
    ttk.Entry(weight_frame, textvariable=weight_var, width=6).pack(side="left")

    level_frame = ttk.Frame(container)
    level_frame.pack(fill="x", pady=(0, 8))
    ttk.Label(
        level_frame, text=app._t("configuration_posture_field_level"), width=22
    ).pack(side="left")
    level_choices = [_level_display(app, level) for level in CAPABILITY_LEVEL_ORDER]
    level_var = tk.StringVar(value=level_choices[0])
    ttk.Combobox(
        level_frame,
        textvariable=level_var,
        values=level_choices,
        state="readonly",
    ).pack(side="left", fill="x", expand=True)

    suggestion_label = ttk.Label(
        container,
        text="",
        wraplength=480,
        justify="left",
        foreground="#475569",
    )
    suggestion_label.pack(anchor="w", pady=(4, 8))

    def _apply_suggestion(*_args: object) -> None:
        try:
            index = metric_choices.index(metric_var.get())
        except ValueError:
            return
        key = metric_keys[index]
        if not key:
            suggestion_label.configure(text="")
            return
        if not label_var.get().strip():
            label_var.set(SNAPSHOT_METRIC_KEYS[key])
        count = snapshot_metric_count_safe(metrics, key)
        if metrics is None:
            suggestion_label.configure(
                text=app._t("configuration_posture_suggestion_no_metrics")
            )
            return
        suggested = _suggest_level(count)
        level_var.set(_level_display(app, suggested))
        suggestion_label.configure(
            text=app._t(
                "configuration_posture_suggestion",
                count=count,
                level=_level_display(app, suggested),
            )
        )

    metric_var.trace_add("write", _apply_suggestion)

    button_row = ttk.Frame(container)
    button_row.pack(fill="x", pady=(8, 0))

    def _save() -> None:
        raw_label = label_var.get().strip()
        if not raw_label:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_label_required"),
                parent=dialog,
            )
            return
        if raw_label.casefold() in used_labels:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_label_duplicate"),
                parent=dialog,
            )
            return
        weight_text = weight_var.get().strip()
        if not weight_text.lstrip("-").isdigit() or int(weight_text) < 0:
            messagebox.showerror(
                app._t("error_title"),
                app._t("configuration_posture_invalid_weight"),
                parent=dialog,
            )
            return
        try:
            metric_index = metric_choices.index(metric_var.get())
        except ValueError:
            metric_index = 0
        metadata_key = metric_keys[metric_index]
        level = None
        for level_candidate in CAPABILITY_LEVEL_ORDER:
            if _level_display(app, level_candidate) == level_var.get():
                level = level_candidate
                break
        if level is None:
            level = CapabilityLevel.ADOPT
        new_id = _build_custom_id(app, raw_label)
        new_entry = PostureCapabilityConfig(
            capability_id=new_id,
            label=raw_label,
            weight=int(weight_text),
            level=level,
            custom=True,
            metadata_key=metadata_key,
        )
        app.posture_config = collect_config(app) + [new_entry]
        _render_table(app)
        dialog.destroy()

    ttk.Button(button_row, text=app._t("configuration_save"), command=_save).pack(
        side="right"
    )
    ttk.Button(button_row, text=app._t("configuration_cancel"), command=dialog.destroy).pack(
        side="right", padx=(0, 8)
    )

    dialog.focus_set()


# ---------------------------------------------------------------------------
# Suggestion / metadata helpers
# ---------------------------------------------------------------------------


def snapshot_metric_count_safe(metrics: object, key: str) -> int:
    if metrics is None:
        return 0
    value = getattr(metrics, key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _suggest_level(count: int) -> CapabilityLevel:
    if count <= 0:
        return CapabilityLevel.ADOPT
    if count <= 5:
        return CapabilityLevel.ADAPT_LOW
    return CapabilityLevel.ADAPT_HIGH


def _build_custom_id(app: "Application", label: str) -> str:
    used_ids: set[str] = {entry.capability_id for entry in collect_config(app)}
    used_ids.update(d.capability_id for d in CAPABILITY_CATALOG)
    base = "custom_" + "".join(
        ch.lower() if ch.isalnum() else "_" for ch in label
    ).strip("_") or "custom_capability"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate
