"""Configuration window for the Salesforce documentation generator."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.ai import build_system_prompt
from src.analyzer.rule_catalog import DEFAULT_RULES_PATH
from src.ui import (
    ai_tags_panel,
    analyzer_rules_panel,
    posture_capability_panel,
)
from src.ui.settings import (
    DEFAULT_AI_USAGE_TAGS,
    serialize_posture_config,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def show_configuration_screen(app: Application) -> None:
    """Create and show the configuration management window."""
    existing = app.configuration_window
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return

    window = tk.Toplevel(app)
    window.title(app._t("configuration_title"))
    window.geometry("980x720")
    app._configure_secondary_window(window)

    # Add scrollbar support
    container = ttk.Frame(window)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding=16)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Mouse wheel support
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    ttk.Label(
        scrollable_frame,
        text=app._t("configuration_title"),
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w", pady=(0, 8))

    notebook = ttk.Notebook(scrollable_frame)
    notebook.pack(fill="both", expand=True)

    doc_tab = ttk.Frame(notebook, padding=12)
    discussion_tab = ttk.Frame(notebook, padding=12)
    rules_tab = ttk.Frame(notebook, padding=12)
    ai_tags_tab = ttk.Frame(notebook, padding=12)
    index_cards_tab = ttk.Frame(notebook, padding=12)
    posture_tab = ttk.Frame(notebook, padding=12)
    notebook.add(doc_tab, text=app._t("configuration_tab_documentation"))
    notebook.add(discussion_tab, text=app._t("configuration_tab_discussion"))
    notebook.add(rules_tab, text=app._t("configuration_tab_rules"))
    notebook.add(ai_tags_tab, text=app._t("configuration_tab_ai_tags"))
    notebook.add(index_cards_tab, text=app._t("configuration_tab_index_cards"))
    notebook.add(posture_tab, text=app._t("configuration_tab_posture"))

    edit_vars = {
        "language": tk.StringVar(value=app._language_display(app.language)),
        "login_target": tk.StringVar(value=app._login_target_display(app.login_target_key)),
        "instance_url": tk.StringVar(value=app.instance_url_var.get()),
        "alias": tk.StringVar(value=app.alias_var.get()),
        "source": tk.StringVar(value=app.source_var.get()),
        "output": tk.StringVar(value=app.output_var.get()),
        "exclusion_file": tk.StringVar(value=app.exclusion_file_var.get()),
        "pmd_enabled": tk.BooleanVar(value=bool(app.pmd_enabled_var.get())),
        "pmd_ruleset": tk.StringVar(value=app.pmd_ruleset_var.get()),
        "org_check_type": tk.StringVar(value=app.org_check_choice_var.get()),
        "ai_provider": tk.StringVar(value=app.ai_provider_var.get()),
        "claude_key": tk.StringVar(value=app.claude_api_key_var.get()),
        "gemini_key": tk.StringVar(value=app.gemini_api_key_var.get()),
        "claude_model": tk.StringVar(value=app.claude_model_var.get()),
        "gemini_model": tk.StringVar(value=app.gemini_model_var.get()),
        "generate_excels": tk.BooleanVar(value=bool(app.generate_excels_var.get())),
        "generate_org_check_reports": tk.BooleanVar(
            value=bool(app.generate_org_check_reports_var.get())
        ),
        "generate_data_dictionary_word": tk.BooleanVar(
            value=bool(app.generate_data_dictionary_word_var.get())
        ),
        "generate_summary_word": tk.BooleanVar(
            value=bool(app.generate_summary_word_var.get())
        ),
        "show_card_customization_level": tk.BooleanVar(
            value=bool(app.show_card_customization_level_var.get())
        ),
        "show_card_score": tk.BooleanVar(
            value=bool(app.show_card_score_var.get())
        ),
        "show_card_adopt_vs_adapt": tk.BooleanVar(
            value=bool(app.show_card_adopt_vs_adapt_var.get())
        ),
        "show_card_adopt_adapt_score": tk.BooleanVar(
            value=bool(app.show_card_adopt_adapt_score_var.get())
        ),
        "show_card_custom_objects": tk.BooleanVar(
            value=bool(app.show_card_custom_objects_var.get())
        ),
        "show_card_custom_fields": tk.BooleanVar(
            value=bool(app.show_card_custom_fields_var.get())
        ),
        "show_card_flows": tk.BooleanVar(
            value=bool(app.show_card_flows_var.get())
        ),
        "show_card_apex_classes_triggers": tk.BooleanVar(
            value=bool(app.show_card_apex_classes_triggers_var.get())
        ),
        "show_card_omni_components": tk.BooleanVar(
            value=bool(app.show_card_omni_components_var.get())
        ),
        "show_card_findings": tk.BooleanVar(
            value=bool(app.show_card_findings_var.get())
        ),
        "show_card_ai_usage": tk.BooleanVar(
            value=bool(app.show_card_ai_usage_var.get())
        ),
        "show_card_data_model_footprint": tk.BooleanVar(
            value=bool(app.show_card_data_model_footprint_var.get())
        ),
        "show_card_adopt_adapt_posture": tk.BooleanVar(
            value=bool(app.show_card_adopt_adapt_posture_var.get())
        ),
        "show_card_agents": tk.BooleanVar(
            value=bool(app.show_card_agents_var.get())
        ),
        "show_card_gen_ai_prompts": tk.BooleanVar(
            value=bool(app.show_card_gen_ai_prompts_var.get())
        ),
    }

    _build_documentation_tab(app, doc_tab, edit_vars)
    _build_discussion_tab(app, discussion_tab, edit_vars)
    analyzer_rules_panel.build_panel(app, rules_tab)
    ai_tags_panel.build_panel(app, ai_tags_tab)
    _build_index_cards_tab(app, index_cards_tab, edit_vars)
    posture_capability_panel.build_panel(app, posture_tab)

    buttons_row = ttk.Frame(scrollable_frame)
    buttons_row.pack(fill="x", pady=(12, 0))
    ttk.Button(
        buttons_row,
        text=app._t("configuration_cancel"),
        command=window.destroy,
    ).pack(side="right")
    ttk.Button(
        buttons_row,
        text=app._t("configuration_save"),
        command=lambda: _apply_configuration_changes(app, edit_vars, window),
    ).pack(side="right", padx=(0, 8))

    app.configuration_window = window
    window.focus_set()


def _build_documentation_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    general = ttk.LabelFrame(parent, text=app._t("configuration_section_general"), padding=10)
    general.pack(fill="x", pady=(0, 8))
    _config_combo_row(
        general,
        app._t("language"),
        edit_vars["language"],
        [app._language_display(code) for code in app.LANGUAGES],
    )

    salesforce = ttk.LabelFrame(parent, text=app._t("configuration_section_salesforce"), padding=10)
    salesforce.pack(fill="x", pady=(0, 8))
    _config_entry_row(salesforce, app._t("alias"), edit_vars["alias"])
    _config_combo_row(
        salesforce,
        app._t("environment"),
        edit_vars["login_target"],
        [app._login_target_display(key) for key in app.LOGIN_TARGETS],
    )
    _config_entry_row(salesforce, app._t("instance_url"), edit_vars["instance_url"])

    paths = ttk.LabelFrame(parent, text=app._t("configuration_section_paths"), padding=10)
    paths.pack(fill="x", pady=(0, 8))
    _config_entry_row(paths, app._t("source_folder"), edit_vars["source"])
    _config_entry_row(paths, app._t("output_folder"), edit_vars["output"])
    _config_entry_row(paths, app._t("exclusion_file"), edit_vars["exclusion_file"])

    analysis = ttk.LabelFrame(parent, text=app._t("configuration_section_analysis"), padding=10)
    analysis.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        analysis, text=app._t("pmd_enabled"), variable=edit_vars["pmd_enabled"]
    ).pack(anchor="w", pady=(0, 4))
    _config_entry_row(analysis, app._t("pmd_ruleset_file"), edit_vars["pmd_ruleset"])
    _config_combo_row(
        analysis,
        app._t("org_check_type"),
        edit_vars["org_check_type"],
        list(app.ORG_CHECK_CHOICES),
    )

    reports = ttk.LabelFrame(parent, text=app._t("configuration_section_reports"), padding=10)
    reports.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_excels"),
        variable=edit_vars["generate_excels"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_org_check_reports"),
        variable=edit_vars["generate_org_check_reports"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_data_dictionary_word"),
        variable=edit_vars["generate_data_dictionary_word"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_summary_word"),
        variable=edit_vars["generate_summary_word"],
    ).pack(anchor="w", pady=(2, 2))


def _build_discussion_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ai_frame = ttk.LabelFrame(parent, text=app._t("configuration_section_ai"), padding=10)
    ai_frame.pack(fill="x", pady=(0, 8))
    _config_combo_row(
        ai_frame,
        app._t("configuration_ai_provider"),
        edit_vars["ai_provider"],
        list(app.AI_PROVIDERS),
    )
    _config_entry_row(
        ai_frame, app._t("configuration_claude_key"), edit_vars["claude_key"], show="*"
    )
    _config_combo_row(
        ai_frame,
        app._t("configuration_claude_model"),
        edit_vars["claude_model"],
        list(app.CLAUDE_MODEL_CHOICES),
    )
    _config_entry_row(
        ai_frame, app._t("configuration_gemini_key"), edit_vars["gemini_key"], show="*"
    )
    _config_combo_row(
        ai_frame,
        app._t("configuration_gemini_model"),
        edit_vars["gemini_model"],
        list(app.GEMINI_MODEL_CHOICES),
    )
    ttk.Label(
        ai_frame,
        text=app._t("configuration_model_hint"),
        wraplength=640,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(6, 0))

    prompt_frame = ttk.LabelFrame(
        parent, text=app._t("configuration_section_prompt"), padding=10
    )
    prompt_frame.pack(fill="both", expand=True, pady=(0, 8))

    ttk.Label(
        prompt_frame,
        text=app._t("configuration_system_prompt_description"),
        wraplength=640,
        justify="left",
    ).pack(anchor="w", pady=(0, 6))

    prompt_widget = scrolledtext.ScrolledText(
        prompt_frame, wrap="word", height=10, font=("Segoe UI", 10)
    )
    prompt_widget.pack(fill="both", expand=True)
    prompt_widget.insert("1.0", app.system_prompt)
    app._config_system_prompt_widget = prompt_widget

    button_row = ttk.Frame(prompt_frame)
    button_row.pack(fill="x", pady=(6, 0))
    
    def reset_prompt():
        default_prompt = build_system_prompt(app.language)
        prompt_widget.delete("1.0", "end")
        prompt_widget.insert("1.0", default_prompt)

    ttk.Button(
        button_row,
        text=app._t("configuration_system_prompt_reset"),
        command=reset_prompt,
    ).pack(side="right")


def _build_index_cards_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_title"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_description"),
        wraplength=640,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 10))

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "configuration_index_cards_section_synthesis",
            [
                ("show_card_customization_level", "configuration_card_customization_level"),
                ("show_card_score", "configuration_card_score"),
                ("show_card_adopt_vs_adapt", "configuration_card_adopt_vs_adapt"),
                ("show_card_adopt_adapt_score", "configuration_card_adopt_adapt_score"),
            ],
        ),
        (
            "configuration_index_cards_section_volume",
            [
                ("show_card_custom_objects", "configuration_card_custom_objects"),
                ("show_card_custom_fields", "configuration_card_custom_fields"),
                ("show_card_flows", "configuration_card_flows"),
                ("show_card_apex_classes_triggers", "configuration_card_apex_classes_triggers"),
                ("show_card_omni_components", "configuration_card_omni_components"),
            ],
        ),
        (
            "configuration_index_cards_section_quality",
                [
                    ("show_card_findings", "configuration_card_findings"),
                    ("show_card_ai_usage", "configuration_card_ai_usage"),
                    ("show_card_agents", "configuration_card_agents"),
                    ("show_card_gen_ai_prompts", "configuration_card_gen_ai_prompts"),
                    ("show_card_data_model_footprint", "configuration_card_data_model_footprint"),
                    ("show_card_adopt_adapt_posture", "configuration_card_adopt_adapt_posture"),
                ],
            ),
        ]

    for section_key, toggles in groups:
        container = ttk.LabelFrame(
            parent,
            text=app._t(section_key),
            padding=10,
        )
        container.pack(fill="x", pady=(0, 8))
        for var_key, label_key in toggles:
            ttk.Checkbutton(
                container,
                text=app._t(label_key),
                variable=edit_vars[var_key],
            ).pack(anchor="w", pady=(2, 2))


def _config_entry_row(parent: ttk.Frame, label_text: str, variable: tk.Variable, show: str | None = None) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text=label_text, width=22).pack(side="left")
    entry = ttk.Entry(row, textvariable=variable)
    if show is not None:
        entry.configure(show=show)
    entry.pack(side="left", fill="x", expand=True)


def _config_combo_row(parent: ttk.Frame, label_text: str, variable: tk.Variable, values: list[str]) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=3)
    ttk.Label(row, text=label_text, width=22).pack(side="left")
    combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
    combo.pack(side="left", fill="x", expand=True)


def _apply_configuration_changes(app: Application, edit_vars: dict[str, tk.Variable], window: tk.Toplevel) -> None:
    new_language = app._language_code_from_display(edit_vars["language"].get())
    language_changed = new_language != app.language
    app.language = new_language

    new_login_target = app._login_target_key_from_display(edit_vars["login_target"].get())
    app.login_target_key = new_login_target

    app.instance_url_var.set(edit_vars["instance_url"].get().strip())
    app.alias_var.set(edit_vars["alias"].get().strip())
    app.source_var.set(edit_vars["source"].get().strip())
    app.output_var.set(edit_vars["output"].get().strip())
    app.exclusion_file_var.set(edit_vars["exclusion_file"].get().strip())
    app.pmd_enabled_var.set(bool(edit_vars["pmd_enabled"].get()))
    app.pmd_ruleset_var.set(edit_vars["pmd_ruleset"].get().strip())

    org_check_choice = edit_vars["org_check_type"].get().strip()
    if org_check_choice:
        app.org_check_choice_var.set(org_check_choice)

    provider = edit_vars["ai_provider"].get().strip()
    if provider in app.AI_PROVIDERS:
        app.ai_provider_var.set(provider)

    app.claude_api_key_var.set(edit_vars["claude_key"].get())
    app.gemini_api_key_var.set(edit_vars["gemini_key"].get())

    claude_model_choice = edit_vars["claude_model"].get().strip()
    if claude_model_choice in app.CLAUDE_MODEL_CHOICES:
        app.claude_model_var.set(claude_model_choice)
    gemini_model_choice = edit_vars["gemini_model"].get().strip()
    if gemini_model_choice in app.GEMINI_MODEL_CHOICES:
        app.gemini_model_var.set(gemini_model_choice)
    app.generate_excels_var.set(bool(edit_vars["generate_excels"].get()))
    app.generate_org_check_reports_var.set(
        bool(edit_vars["generate_org_check_reports"].get())
    )
    app.generate_data_dictionary_word_var.set(
        bool(edit_vars["generate_data_dictionary_word"].get())
    )
    app.generate_summary_word_var.set(
        bool(edit_vars["generate_summary_word"].get())
    )
    app.show_card_customization_level_var.set(
        bool(edit_vars["show_card_customization_level"].get())
    )
    app.show_card_score_var.set(
        bool(edit_vars["show_card_score"].get())
    )
    app.show_card_adopt_vs_adapt_var.set(
        bool(edit_vars["show_card_adopt_vs_adapt"].get())
    )
    app.show_card_adopt_adapt_score_var.set(
        bool(edit_vars["show_card_adopt_adapt_score"].get())
    )
    app.show_card_custom_objects_var.set(
        bool(edit_vars["show_card_custom_objects"].get())
    )
    app.show_card_custom_fields_var.set(
        bool(edit_vars["show_card_custom_fields"].get())
    )
    app.show_card_flows_var.set(
        bool(edit_vars["show_card_flows"].get())
    )
    app.show_card_apex_classes_triggers_var.set(
        bool(edit_vars["show_card_apex_classes_triggers"].get())
    )
    app.show_card_omni_components_var.set(
        bool(edit_vars["show_card_omni_components"].get())
    )
    app.show_card_findings_var.set(
        bool(edit_vars["show_card_findings"].get())
    )
    app.show_card_ai_usage_var.set(
        bool(edit_vars["show_card_ai_usage"].get())
    )
    app.show_card_data_model_footprint_var.set(
        bool(edit_vars["show_card_data_model_footprint"].get())
    )
    app.show_card_adopt_adapt_posture_var.set(
        bool(edit_vars["show_card_adopt_adapt_posture"].get())
    )
    app.show_card_agents_var.set(
        bool(edit_vars["show_card_agents"].get())
    )
    app.show_card_gen_ai_prompts_var.set(
        bool(edit_vars["show_card_gen_ai_prompts"].get())
    )

    if app._config_system_prompt_widget is not None:
        prompt_text = app._config_system_prompt_widget.get("1.0", "end").strip()
        app.system_prompt = prompt_text or build_system_prompt(app.language)
    app._config_system_prompt_widget = None

    analyzer_rules_panel.persist_changes(app)
    analyzer_rules_panel.reset_state(app)

    raw_tags = ai_tags_panel.collect_tags(app)
    cleaned_tags: list[str] = []
    seen_tags: set[str] = set()
    for value in raw_tags:
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen_tags:
            continue
        seen_tags.add(key)
        cleaned_tags.append(text)
    app.ai_usage_tags = cleaned_tags or list(DEFAULT_AI_USAGE_TAGS)
    ai_tags_panel.reset_state(app)

    app.posture_config = posture_capability_panel.collect_config(app)
    posture_capability_panel.reset_state(app)

    app._save_settings()

    if language_changed:
        app._apply_language()
    else:
        app._apply_pmd_state()
        app._on_login_target_changed()

    app._append_log(app._t("configuration_saved"))
    window.destroy()
