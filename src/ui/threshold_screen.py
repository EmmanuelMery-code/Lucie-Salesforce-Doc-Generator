"""Threshold editor window.

Lets the user tweak the score breakpoints used to derive the textual level
shown in the scoring and Adopt-vs-Adapt screens. Two specs are configured
in this module so the rendering loop stays generic; if more
threshold-based metrics show up later, just add a new
:class:`ThresholdSpec`.

The window mirrors :mod:`src.ui.scoring_screens` in spirit: it accepts the
:class:`Application` instance and reads/writes state on it directly so the
main class keeps a thin public surface.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Callable

from src.core.models import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_SCORING_THRESHOLDS,
    CustomizationMetrics,
)
from src.ui.scrollable_window import build_scrollable_window

if TYPE_CHECKING:
    from src.ui.application import Application


# ---------------------------------------------------------------------------
# Spec / configuration descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdSpec:
    """Describes one threshold ladder shown in the editor.

    The four ``level_*_key`` translation keys parameterise the user-facing
    labels (``Faible``, ``Moyen``, ...). ``level_resolver`` extracts the
    derived textual level from a metrics snapshot for the live preview, so
    the same dialog works for both the scoring score and the
    Adopt-vs-Adapt score without conditional logic in the rendering code.
    """

    title_key: str
    description_key: str
    section_label_key: str
    threshold_attr: str  # attribute name on Application
    metrics_attr: str  # attribute name on CustomizationMetrics
    score_label_key: str
    level_label_key: str
    defaults: tuple[int, int, int]
    level_low_key: str
    level_medium_key: str
    level_high_key: str
    level_very_high_key: str
    level_resolver: Callable[[CustomizationMetrics], str]
    score_resolver: Callable[[CustomizationMetrics], int]


SCORING_THRESHOLDS_SPEC = ThresholdSpec(
    title_key="thresholds_scoring_title",
    description_key="thresholds_scoring_description",
    section_label_key="thresholds_scoring_section",
    threshold_attr="scoring_thresholds",
    metrics_attr="scoring_thresholds",
    score_label_key="scoring_overall_score",
    level_label_key="scoring_level",
    defaults=DEFAULT_SCORING_THRESHOLDS,
    level_low_key="scoring_level_label_low",
    level_medium_key="scoring_level_label_medium",
    level_high_key="scoring_level_label_high",
    level_very_high_key="scoring_level_label_very_high",
    level_resolver=lambda metrics: metrics.level,
    score_resolver=lambda metrics: metrics.score,
)


ADOPT_ADAPT_THRESHOLDS_SPEC = ThresholdSpec(
    title_key="thresholds_adopt_adapt_title",
    description_key="thresholds_adopt_adapt_description",
    section_label_key="thresholds_adopt_adapt_section",
    threshold_attr="adopt_adapt_thresholds",
    metrics_attr="adopt_adapt_thresholds",
    score_label_key="adopt_adapt_overall_score",
    level_label_key="adopt_adapt_level",
    defaults=DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    level_low_key="adopt_adapt_level_label_adopt",
    level_medium_key="adopt_adapt_level_label_adapt_low",
    level_high_key="adopt_adapt_level_label_adapt_medium",
    level_very_high_key="adopt_adapt_level_label_adapt_high",
    level_resolver=lambda metrics: metrics.adopt_adapt_level,
    score_resolver=lambda metrics: metrics.adopt_adapt_score,
)


SPECS: tuple[ThresholdSpec, ThresholdSpec] = (
    SCORING_THRESHOLDS_SPEC,
    ADOPT_ADAPT_THRESHOLDS_SPEC,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def show_threshold_screen(app: Application) -> None:
    """Open (or focus) the threshold editor window."""

    existing = getattr(app, "thresholds_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return

    window, container, footer = build_scrollable_window(
        app, title=app._t("thresholds_title"), geometry="680x640"
    )

    ttk.Label(
        container,
        text=app._t("thresholds_title"),
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=app._t("thresholds_description"),
        wraplength=620,
        justify="left",
    ).pack(anchor="w", pady=(4, 12))

    section_state: list[_SectionState] = []
    for spec in SPECS:
        state = _build_threshold_section(app, container, spec)
        section_state.append(state)

    def refresh_all() -> None:
        for state in section_state:
            _refresh_section(app, state)

    def save_all() -> None:
        new_values: list[tuple[ThresholdSpec, tuple[int, int, int]]] = []
        for state in section_state:
            parsed = _read_section(app, state)
            if parsed is None:
                return
            new_values.append((state.spec, parsed))

        for spec, values in new_values:
            setattr(app, spec.threshold_attr, values)
            if app.latest_metrics is not None:
                setattr(app.latest_metrics, spec.metrics_attr, values)
        app._save_settings()
        refresh_all()
        app._append_log(app._t("thresholds_saved"))

    def reset_all() -> None:
        for state in section_state:
            for var, default in zip(state.vars, state.spec.defaults):
                var.set(str(default))
        refresh_all()

    for state in section_state:
        for var in state.vars:
            var.trace_add("write", lambda *_args: refresh_all())

    refresh_all()

    ttk.Button(
        footer,
        text=app._t("scoring_close"),
        command=window.destroy,
    ).pack(side="right")
    ttk.Button(
        footer,
        text=app._t("scoring_save"),
        command=save_all,
    ).pack(side="right", padx=(0, 8))
    ttk.Button(
        footer,
        text=app._t("scoring_reset"),
        command=reset_all,
    ).pack(side="right", padx=(0, 8))

    app.thresholds_window = window
    window.focus_set()


# ---------------------------------------------------------------------------
# Per-section state and rendering
# ---------------------------------------------------------------------------


@dataclass
class _SectionState:
    """Mutable state held for one threshold ladder while the dialog is open."""

    spec: ThresholdSpec
    vars: tuple[tk.StringVar, tk.StringVar, tk.StringVar]
    score_label: ttk.Label
    level_label: ttk.Label
    summary_labels: tuple[ttk.Label, ttk.Label, ttk.Label, ttk.Label]


def _build_threshold_section(
    app: Application, parent: ttk.Frame, spec: ThresholdSpec
) -> _SectionState:
    section = ttk.LabelFrame(parent, text=app._t(spec.section_label_key), padding=12)
    section.pack(fill="x", pady=(0, 12))

    ttk.Label(
        section,
        text=app._t(spec.description_key),
        wraplength=600,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 8))

    score_row = ttk.Frame(section)
    score_row.pack(fill="x", pady=(0, 6))
    score_label = ttk.Label(score_row, font=("Segoe UI", 10, "bold"))
    score_label.pack(side="left")
    level_label = ttk.Label(score_row, font=("Segoe UI", 10, "bold"))
    level_label.pack(side="left", padx=(16, 0))

    current_values = getattr(app, spec.threshold_attr, None) or spec.defaults
    vars_ = (
        tk.StringVar(value=str(current_values[0])),
        tk.StringVar(value=str(current_values[1])),
        tk.StringVar(value=str(current_values[2])),
    )

    grid = ttk.Frame(section)
    grid.pack(fill="x", pady=(2, 6))
    ttk.Label(
        grid,
        text=app._t("thresholds_column_threshold"),
        font=("Segoe UI", 9, "bold"),
    ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))
    ttk.Label(
        grid,
        text=app._t("thresholds_column_value"),
        font=("Segoe UI", 9, "bold"),
    ).grid(row=0, column=1, sticky="w", padx=4, pady=(0, 4))

    threshold_labels = (
        app._t("thresholds_breakpoint_low"),
        app._t("thresholds_breakpoint_medium"),
        app._t("thresholds_breakpoint_high"),
    )
    for index, (label_text, var) in enumerate(zip(threshold_labels, vars_), start=1):
        ttk.Label(grid, text=label_text).grid(
            row=index, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Entry(grid, textvariable=var, width=10, justify="center").grid(
            row=index, column=1, sticky="w", padx=4, pady=2
        )

    summary = ttk.Frame(section)
    summary.pack(fill="x", pady=(4, 0))
    summary_labels = (
        ttk.Label(summary),
        ttk.Label(summary),
        ttk.Label(summary),
        ttk.Label(summary),
    )
    for label in summary_labels:
        label.pack(anchor="w")

    return _SectionState(
        spec=spec,
        vars=vars_,
        score_label=score_label,
        level_label=level_label,
        summary_labels=summary_labels,
    )


# ---------------------------------------------------------------------------
# Refresh / read helpers
# ---------------------------------------------------------------------------


def _read_section(app: Application, state: _SectionState) -> tuple[int, int, int] | None:
    """Read & validate the three entry fields of one section.

    Pops a localized error dialog when the values are not strictly
    increasing positive integers; returns ``None`` so the caller aborts
    the save without committing partial changes.
    """

    parsed: list[int] = []
    for index, var in enumerate(state.vars):
        text = var.get().strip()
        if not text.lstrip("-").isdigit():
            messagebox.showerror(
                app._t("error_title"),
                app._t("thresholds_invalid_value", index=index + 1),
            )
            return None
        parsed.append(int(text))

    if not (parsed[0] < parsed[1] < parsed[2]):
        messagebox.showerror(
            app._t("error_title"),
            app._t("thresholds_invalid_order"),
        )
        return None

    return (parsed[0], parsed[1], parsed[2])


def _coerce_preview_thresholds(
    state: _SectionState,
) -> tuple[int, int, int]:
    """Best-effort conversion of the editor values for the live preview.

    Falls back to the spec's defaults whenever a field is empty or not yet
    a valid integer; prevents the preview from disappearing while the user
    is still typing.
    """

    values: list[int] = []
    for var, default in zip(state.vars, state.spec.defaults):
        text = var.get().strip()
        if text.lstrip("-").isdigit():
            values.append(int(text))
        else:
            values.append(default)
    sorted_values = sorted(values)
    return (sorted_values[0], sorted_values[1], sorted_values[2])


def _refresh_section(app: Application, state: _SectionState) -> None:
    spec = state.spec
    preview = _coerce_preview_thresholds(state)
    low, medium, high = preview

    keys = (
        spec.level_low_key,
        spec.level_medium_key,
        spec.level_high_key,
        spec.level_very_high_key,
    )
    bands = (
        app._t("thresholds_band_below", value=low),
        app._t("thresholds_band_between", low=low, high=medium),
        app._t("thresholds_band_between", low=medium, high=high),
        app._t("thresholds_band_above_or_equal", value=high),
    )
    for label, key, band in zip(state.summary_labels, keys, bands):
        label.configure(text=f"- {app._t(key)} {band}")

    metrics = app.latest_metrics
    if metrics is None:
        state.score_label.configure(text=app._t(spec.score_label_key) + ": -")
        state.level_label.configure(text=app._t(spec.level_label_key) + ": -")
        return

    temp = CustomizationMetrics()
    for k, v in metrics.__dict__.items():
        if hasattr(temp, k):
            setattr(temp, k, v)
    setattr(temp, spec.metrics_attr, preview)

    state.score_label.configure(
        text=f"{app._t(spec.score_label_key)}: {spec.score_resolver(temp)}"
    )
    state.level_label.configure(
        text=f"{app._t(spec.level_label_key)}: {spec.level_resolver(temp)}"
    )
