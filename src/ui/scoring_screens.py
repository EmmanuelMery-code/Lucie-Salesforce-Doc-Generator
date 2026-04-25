"""Tk windows for the scoring and Adopt-vs-Adapt configuration screens.

Both screens share the same layout (scrollable container, weight table with
live preview, Save/Reset/Close buttons). They previously lived in
:mod:`src.ui.application` as two ~250-line near-duplicate methods. This
module factorises the shared scaffolding behind a small ``WeightScreenSpec``
descriptor so each screen reduces to a few lines of configuration.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable

from src.core.models import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_ADOPT_ADAPT_WEIGHTS,
    DEFAULT_SCORING_THRESHOLDS,
    DEFAULT_SCORING_WEIGHTS,
    CustomizationMetrics,
)
from src.ui.scrollable_window import build_scrollable_window

if TYPE_CHECKING:
    from src.ui.application import Application


# ---------------------------------------------------------------------------
# Spec / configuration descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightScreenSpec:
    """Describes one of the two scoring screens.

    The descriptor groups every value that differs between the two windows so
    the rendering logic itself stays generic.
    """

    title_key: str
    description_key: str
    formula_title_key: str
    levels_title_key: str
    score_label_key: str
    level_label_key: str
    weights_saved_key: str
    window_attr: str
    components_attr: str
    weights_attr: str
    metrics_weights_attr: str
    score_property: str
    level_property: str
    defaults: dict[str, int]
    # Translation keys for the four level labels (low / medium / high /
    # very high) shown in the "Levels" section. The thresholds attached to
    # the levels are resolved at render time from ``threshold_attr`` so the
    # screen always reflects the user's custom breakpoints.
    level_keys: tuple[str, str, str, str]
    # Application attribute holding the current 3-tuple of breakpoints.
    threshold_attr: str
    # Default thresholds used when the application has not set them yet.
    threshold_defaults: tuple[int, int, int]
    # Resolves the metric count for a given component attribute.
    count_resolver: Callable[[Any, str], int] = field(
        default=lambda metrics, attr: int(getattr(metrics, attr, 0))
    )


SCORING_SPEC = WeightScreenSpec(
    title_key="scoring_title",
    description_key="scoring_description",
    formula_title_key="scoring_formula_title",
    levels_title_key="scoring_levels_title",
    score_label_key="scoring_overall_score",
    level_label_key="scoring_level",
    weights_saved_key="scoring_weights_saved",
    window_attr="scoring_window",
    components_attr="SCORING_COMPONENTS",
    weights_attr="scoring_weights",
    metrics_weights_attr="weights",
    score_property="score",
    level_property="level",
    defaults=dict(DEFAULT_SCORING_WEIGHTS),
    level_keys=(
        "scoring_level_label_low",
        "scoring_level_label_medium",
        "scoring_level_label_high",
        "scoring_level_label_very_high",
    ),
    threshold_attr="scoring_thresholds",
    threshold_defaults=DEFAULT_SCORING_THRESHOLDS,
)


def _adopt_adapt_count(metrics: Any, attr: str) -> int:
    # Adopt-vs-Adapt aliases two of its attributes onto metric fields with
    # different names. Centralising the mapping keeps the rendering loop
    # generic.
    if attr == "lwc":
        return int(getattr(metrics, "lwc_count", 0))
    if attr == "flexipages":
        return int(getattr(metrics, "flexipage_count", 0))
    return int(getattr(metrics, attr, 0))


ADOPT_ADAPT_SPEC = WeightScreenSpec(
    title_key="adopt_adapt_title",
    description_key="adopt_adapt_description",
    formula_title_key="adopt_adapt_formula_title",
    levels_title_key="adopt_adapt_levels_title",
    score_label_key="adopt_adapt_overall_score",
    level_label_key="adopt_adapt_level",
    weights_saved_key="adopt_adapt_weights_saved",
    window_attr="adopt_adapt_window",
    components_attr="ADOPT_ADAPT_COMPONENTS",
    weights_attr="adopt_adapt_weights",
    metrics_weights_attr="adopt_adapt_weights",
    score_property="adopt_adapt_score",
    level_property="adopt_adapt_level",
    defaults=dict(DEFAULT_ADOPT_ADAPT_WEIGHTS),
    level_keys=(
        "adopt_adapt_level_label_adopt",
        "adopt_adapt_level_label_adapt_low",
        "adopt_adapt_level_label_adapt_medium",
        "adopt_adapt_level_label_adapt_high",
    ),
    threshold_attr="adopt_adapt_thresholds",
    threshold_defaults=DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    count_resolver=_adopt_adapt_count,
)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def show_scoring_screen(app: Application) -> None:
    _show_weight_screen(app, SCORING_SPEC)


def show_adopt_adapt_screen(app: Application) -> None:
    _show_weight_screen(app, ADOPT_ADAPT_SPEC)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


def _show_weight_screen(app: Application, spec: WeightScreenSpec) -> None:
    existing = getattr(app, spec.window_attr, None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return

    window, container, footer = build_scrollable_window(
        app, title=app._t(spec.title_key), geometry="820x680"
    )

    components: list[tuple[str, str, str]] = getattr(app, spec.components_attr)
    weights_dict: dict[str, int] = getattr(app, spec.weights_attr)

    ttk.Label(
        container,
        text=app._t(spec.title_key),
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=app._t(spec.description_key),
        wraplength=760,
        justify="left",
    ).pack(anchor="w", pady=(4, 4))
    ttk.Label(
        container,
        text=app._t("scoring_edit_hint"),
        wraplength=760,
        justify="left",
        foreground="#64748b",
    ).pack(anchor="w", pady=(0, 10))

    score_header = ttk.Frame(container)
    score_header.pack(fill="x", pady=(0, 10))
    score_label = ttk.Label(score_header, font=("Segoe UI", 11, "bold"))
    score_label.pack(side="left")
    level_label = ttk.Label(score_header, font=("Segoe UI", 11, "bold"))
    level_label.pack(side="left", padx=(16, 0))

    ttk.Label(
        container,
        text=app._t(spec.formula_title_key),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")

    table_frame = ttk.Frame(container)
    table_frame.pack(fill="both", expand=True, pady=(4, 10))
    for column_index, weight in enumerate((3, 1, 1, 1, 5)):
        table_frame.grid_columnconfigure(column_index, weight=weight)

    headers = (
        app._t("scoring_column_component"),
        app._t("scoring_column_weight"),
        app._t("scoring_column_count"),
        app._t("scoring_column_contribution"),
        app._t("scoring_column_description"),
    )
    for column_index, header in enumerate(headers):
        ttk.Label(
            table_frame,
            text=header,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=column_index, sticky="w", padx=4, pady=(0, 4))

    weight_vars: dict[str, tk.StringVar] = {}
    contribution_labels: dict[str, ttk.Label] = {}
    count_labels: dict[str, ttk.Label] = {}

    for row_index, (attr, label_key, desc_key) in enumerate(components, start=1):
        ttk.Label(table_frame, text=app._t(label_key)).grid(
            row=row_index, column=0, sticky="w", padx=4, pady=2
        )
        weight_var = tk.StringVar(
            value=str(weights_dict.get(attr, spec.defaults[attr]))
        )
        ttk.Entry(table_frame, textvariable=weight_var, width=6, justify="center").grid(
            row=row_index, column=1, sticky="w", padx=4, pady=2
        )
        count_lbl = ttk.Label(table_frame, text="", anchor="center")
        count_lbl.grid(row=row_index, column=2, sticky="ew", padx=4, pady=2)
        contribution_lbl = ttk.Label(table_frame, text="", anchor="center")
        contribution_lbl.grid(row=row_index, column=3, sticky="ew", padx=4, pady=2)
        ttk.Label(table_frame, text=app._t(desc_key), wraplength=320, justify="left").grid(
            row=row_index, column=4, sticky="w", padx=4, pady=2
        )
        weight_vars[attr] = weight_var
        count_labels[attr] = count_lbl
        contribution_labels[attr] = contribution_lbl

    total_row_index = len(components) + 1
    ttk.Label(
        table_frame,
        text=app._t("scoring_total_row"),
        font=("Segoe UI", 10, "bold"),
    ).grid(row=total_row_index, column=0, sticky="w", padx=4, pady=(6, 2))
    total_value_label = ttk.Label(
        table_frame, text="", font=("Segoe UI", 10, "bold"), anchor="center"
    )
    total_value_label.grid(row=total_row_index, column=3, sticky="ew", padx=4, pady=(6, 2))

    ttk.Label(
        container,
        text=app._t(spec.levels_title_key),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    levels_frame = ttk.Frame(container)
    levels_frame.pack(fill="x", pady=(2, 10))
    thresholds = (
        getattr(app, spec.threshold_attr, None) or spec.threshold_defaults
    )
    low, medium, high = thresholds
    bands = (
        app._t("thresholds_band_below", value=low),
        app._t("thresholds_band_between", low=low, high=medium),
        app._t("thresholds_band_between", low=medium, high=high),
        app._t("thresholds_band_above_or_equal", value=high),
    )
    for level_key, band in zip(spec.level_keys, bands):
        ttk.Label(
            levels_frame, text=f"- {app._t(level_key)} {band}"
        ).pack(anchor="w")

    def _read_weight(attr: str) -> int:
        try:
            return int(weight_vars[attr].get().strip())
        except (TypeError, ValueError, AttributeError):
            return weights_dict.get(attr, spec.defaults[attr])

    def refresh_display() -> None:
        metrics = app.latest_metrics
        if metrics is None:
            score_label.configure(text=app._t(spec.score_label_key) + ": -")
            level_label.configure(text=app._t(spec.level_label_key) + ": -")
            total_value_label.configure(text="")
            for attr in weight_vars:
                count_labels[attr].configure(text="")
                contribution_labels[attr].configure(text="")
            return

        total = 0
        for attr in weight_vars:
            weight = _read_weight(attr)
            count = spec.count_resolver(metrics, attr)
            contribution = count * weight
            count_labels[attr].configure(text=str(count))
            contribution_labels[attr].configure(text=str(contribution))
            total += contribution
        total_value_label.configure(text=str(total))

        # Live preview using a temporary metrics clone with the editor weights.
        temp_metrics = CustomizationMetrics()
        for k, v in metrics.__dict__.items():
            if hasattr(temp_metrics, k):
                setattr(temp_metrics, k, v)
        temp_weights = {attr: _read_weight(attr) for attr in weight_vars}
        setattr(temp_metrics, spec.metrics_weights_attr, temp_weights)

        score_label.configure(
            text=f"{app._t(spec.score_label_key)}: {getattr(temp_metrics, spec.score_property)}"
        )
        level_label.configure(
            text=f"{app._t(spec.level_label_key)}: {getattr(temp_metrics, spec.level_property)}"
        )

    def save_weights() -> None:
        new_weights: dict[str, int] = {}
        for attr in weight_vars:
            raw_value = weight_vars[attr].get().strip()
            if not raw_value.lstrip("-").isdigit():
                component_label = app._t(
                    next(
                        label_key
                        for candidate_attr, label_key, _ in components
                        if candidate_attr == attr
                    )
                )
                messagebox.showerror(
                    app._t("error_title"),
                    app._t("scoring_invalid_weight", component=component_label),
                )
                return
            new_weights[attr] = int(raw_value)
        setattr(app, spec.weights_attr, new_weights)
        if app.latest_metrics is not None:
            setattr(app.latest_metrics, spec.metrics_weights_attr, dict(new_weights))
        app._save_settings()
        refresh_display()
        app._append_log(app._t(spec.weights_saved_key))

    def reset_weights() -> None:
        for attr in weight_vars:
            weight_vars[attr].set(str(spec.defaults[attr]))
        refresh_display()

    for var in weight_vars.values():
        var.trace_add("write", lambda *_args: refresh_display())

    refresh_display()

    # Buttons live in the footer (outside the scrollable area) so they
    # remain visible no matter how tall the body grows.
    ttk.Button(
        footer,
        text=app._t("scoring_close"),
        command=window.destroy,
    ).pack(side="right")
    ttk.Button(
        footer,
        text=app._t("scoring_save"),
        command=save_weights,
    ).pack(side="right", padx=(0, 8))
    ttk.Button(
        footer,
        text=app._t("scoring_reset"),
        command=reset_weights,
    ).pack(side="right", padx=(0, 8))

    setattr(app, spec.window_attr, window)
    window.focus_set()
