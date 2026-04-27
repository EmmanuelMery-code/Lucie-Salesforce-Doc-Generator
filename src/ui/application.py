from __future__ import annotations

import json
import os
import re
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Callable

from src.ai import (
    AIMessage,
    CLAUDE_MODELS,
    GEMINI_MODELS,
    build_system_prompt,
)
from src.analyzer.models import Rule
from src.analyzer.rule_catalog import DEFAULT_RULES_PATH, RuleCatalog
from src.core.models import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_SCORING_THRESHOLDS,
    DEFAULT_SCORING_WEIGHTS,
)
from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator
from src.core.sf_cli_service import OrgSummary, SalesforceCliService
from src.ui.constants import (
    AI_PROVIDERS as UI_AI_PROVIDERS,
    LANGUAGES as UI_LANGUAGES,
    LOGIN_TARGETS as UI_LOGIN_TARGETS,
    ORG_CHECK_CHOICES as UI_ORG_CHECK_CHOICES,
    PMD_DOWNLOAD_URL as UI_PMD_DOWNLOAD_URL,
    SF_CLI_DOWNLOAD_URL as UI_SF_CLI_DOWNLOAD_URL,
    ORG_CHECK_APP_URL as UI_ORG_CHECK_APP_URL,
    ORG_CHECK_GITHUB_URL as UI_ORG_CHECK_GITHUB_URL,
)
from src.ui import ai_tags_panel, analyzer_rules_panel, discussion_panel
from src.ui.scoring_screens import show_adopt_adapt_screen, show_scoring_screen
from src.ui.settings import (
    DEFAULT_AI_USAGE_TAGS,
    load_settings,
    parse_ai_tags,
    parse_thresholds,
    parse_weights,
    save_settings,
)
from src.ui.threshold_screen import show_threshold_screen
from src.ui.translations import TRANSLATIONS as UI_TRANSLATIONS


class Application(tk.Tk):
    """Main Tk window of the Salesforce documentation generator.

    This class is the user-facing entry point. It wires up:

    * the configuration UI (file pickers, AI provider, analyzer rules);
    * the Documentation menu (Generate full / Excel only / HTML / Word);
    * the scoring, Adopt-vs-Adapt and discussion windows;
    * persistent settings stored in ``app_settings.json``.

    The heavier widgets are delegated to dedicated modules so the class
    itself stays focused on orchestration:

    * :mod:`src.ui.scoring_screens` for the two weighted-score windows;
    * :mod:`src.ui.analyzer_rules_panel` for the rules tab;
    * :mod:`src.ui.discussion_panel` for the chat tab;
    * :mod:`src.ui.settings` for load/save of ``app_settings.json``.
    """

    SF_CLI_DOWNLOAD_URL = UI_SF_CLI_DOWNLOAD_URL
    PMD_DOWNLOAD_URL = UI_PMD_DOWNLOAD_URL
    ORG_CHECK_APP_URL = UI_ORG_CHECK_APP_URL
    ORG_CHECK_GITHUB_URL = UI_ORG_CHECK_GITHUB_URL
    LOGIN_TARGETS = UI_LOGIN_TARGETS
    LANGUAGES = UI_LANGUAGES
    ORG_CHECK_CHOICES = UI_ORG_CHECK_CHOICES
    AI_PROVIDERS = UI_AI_PROVIDERS
    GEMINI_MODEL_CHOICES = GEMINI_MODELS
    CLAUDE_MODEL_CHOICES = CLAUDE_MODELS
    DEFAULT_GEMINI_MODEL = GEMINI_MODELS[0]
    DEFAULT_CLAUDE_MODEL = CLAUDE_MODELS[0]
    DISCUSSION_MIN_INTERVAL_SECONDS = 5.0  # stay safely under 15 RPM free tier
    TRANSLATIONS = UI_TRANSLATIONS

    SCORING_COMPONENTS: list[tuple[str, str, str]] = [
        ("custom_objects", "scoring_component_custom_objects", "scoring_desc_custom_objects"),
        ("custom_fields", "scoring_component_custom_fields", "scoring_desc_custom_fields"),
        ("record_types", "scoring_component_record_types", "scoring_desc_record_types"),
        ("validation_rules", "scoring_component_validation_rules", "scoring_desc_validation_rules"),
        ("layouts", "scoring_component_layouts", "scoring_desc_layouts"),
        ("custom_tabs", "scoring_component_custom_tabs", "scoring_desc_custom_tabs"),
        ("custom_apps", "scoring_component_custom_apps", "scoring_desc_custom_apps"),
        ("flows", "scoring_component_flows", "scoring_desc_flows"),
        ("apex_classes", "scoring_component_apex_classes", "scoring_desc_apex_classes"),
        ("apex_triggers", "scoring_component_apex_triggers", "scoring_desc_apex_triggers"),
        ("omni_scripts", "scoring_component_omni_scripts", "scoring_desc_omni_scripts"),
        (
            "omni_integration_procedures",
            "scoring_component_omni_integration_procedures",
            "scoring_desc_omni_integration_procedures",
        ),
        ("omni_ui_cards", "scoring_component_omni_ui_cards", "scoring_desc_omni_ui_cards"),
        ("omni_data_transforms", "scoring_component_omni_data_transforms", "scoring_desc_omni_data_transforms"),
    ]

    ADOPT_ADAPT_COMPONENTS: list[tuple[str, str, str]] = [
        ("custom_objects", "scoring_component_custom_objects", "scoring_desc_custom_objects"),
        ("custom_fields", "scoring_component_custom_fields", "scoring_desc_custom_fields"),
        ("apex_classes", "scoring_component_apex_classes", "scoring_desc_apex_classes"),
        ("flows", "scoring_component_flows", "scoring_desc_flows"),
        ("lwc", "adopt_adapt_component_lwc", "adopt_adapt_desc_lwc"),
        ("flexipages", "adopt_adapt_component_flexipages", "adopt_adapt_desc_flexipages"),
        ("omni_scripts", "scoring_component_omni_scripts", "adopt_adapt_desc_omni_scripts"),
        ("omni_integration_procedures", "scoring_component_omni_integration_procedures", "adopt_adapt_desc_omni_integration_procedures"),
        ("omni_ui_cards", "scoring_component_omni_ui_cards", "adopt_adapt_desc_omni_ui_cards"),
        ("omni_data_transforms", "scoring_component_omni_data_transforms", "adopt_adapt_desc_omni_data_transforms"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.geometry("980x760")
        self.minsize(900, 620)
        self.app_dir = Path(__file__).resolve().parent.parent.parent
        self.settings_path = self.app_dir / "app_settings.json"
        self.settings = self._load_settings()
        self.language = self.settings.get("language", "fr")

        self.source_var = tk.StringVar(value=self.settings.get("source_folder", ""))
        self.output_var = tk.StringVar(value=self.settings.get("output_folder", ""))
        self.exclusion_file_var = tk.StringVar(value=self.settings.get("exclusion_file", ""))
        self.pmd_enabled_var = tk.BooleanVar(value=bool(self.settings.get("pmd_enabled", False)))
        self.pmd_ruleset_var = tk.StringVar(value=self.settings.get("pmd_ruleset_file", ""))
        self.alias_var = tk.StringVar(value=self.settings.get("alias", ""))
        self.language_label_var = tk.StringVar(value=self.LANGUAGES.get(self.language, "Francais"))
        self.login_target_key = self.settings.get("login_target", "production")
        self.login_target_var = tk.StringVar()
        self.instance_url_var = tk.StringVar(value=self.settings.get("instance_url", self.LOGIN_TARGETS["production"]))
        self.selected_org_var = tk.StringVar()
        org_check_default = self.settings.get("org_check_type", self.ORG_CHECK_CHOICES[0])
        if org_check_default not in self.ORG_CHECK_CHOICES:
            org_check_default = self.ORG_CHECK_CHOICES[0]
        self.org_check_choice_var = tk.StringVar(value=org_check_default)
        self.status_var = tk.StringVar(value=self._t("ready"))

        default_provider = self.settings.get("ai_provider", self.AI_PROVIDERS[0])
        if default_provider not in self.AI_PROVIDERS:
            default_provider = self.AI_PROVIDERS[0]
        self.ai_provider_var = tk.StringVar(value=default_provider)
        self.claude_api_key_var = tk.StringVar(value=self.settings.get("claude_api_key", ""))
        self.gemini_api_key_var = tk.StringVar(value=self.settings.get("gemini_api_key", ""))
        stored_claude_model = str(self.settings.get("claude_model", "") or "").strip()
        if stored_claude_model not in self.CLAUDE_MODEL_CHOICES:
            stored_claude_model = self.DEFAULT_CLAUDE_MODEL
        stored_gemini_model = str(self.settings.get("gemini_model", "") or "").strip()
        # Silently migrate retired models (Google pulled gemini-1.5-* and
        # gemini-2.0-* in March 2026) to the most generous 2.5 option.
        if stored_gemini_model not in self.GEMINI_MODEL_CHOICES:
            stored_gemini_model = self.DEFAULT_GEMINI_MODEL
        self.claude_model_var = tk.StringVar(value=stored_claude_model)
        self.gemini_model_var = tk.StringVar(value=stored_gemini_model)
        stored_prompt = self.settings.get("system_prompt")
        if not isinstance(stored_prompt, str) or not stored_prompt.strip():
            stored_prompt = build_system_prompt(self.language)
        self.system_prompt = stored_prompt
        self._config_system_prompt_widget: scrolledtext.ScrolledText | None = None
        self._analyzer_rule_vars: dict[str, tk.BooleanVar] = {}
        self._analyzer_rules_cache: list[Rule] = []
        self._analyzer_rules_file: Path = DEFAULT_RULES_PATH
        self._analyzer_rule_rows: list[dict[str, object]] = []
        self._analyzer_rule_count_var: tk.StringVar | None = None
        self._analyzer_rule_detail_widget: scrolledtext.ScrolledText | None = None
        self._analyzer_rule_filter_severity: tk.StringVar | None = None
        self._analyzer_rule_filter_category: tk.StringVar | None = None
        self._analyzer_rule_filter_scope: tk.StringVar | None = None
        self._analyzer_rule_selected_reference: str = ""
        self.generate_excels_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_excels", True))
        )
        self.generate_org_check_reports_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_org_check_reports", False))
        )
        self.generate_data_dictionary_word_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_data_dictionary_word", True))
        )
        self.generate_summary_word_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_summary_word", True))
        )

        self.hero_image: tk.PhotoImage | None = None
        self.icon_image: tk.PhotoImage | None = None
        self.menu_bar: tk.Menu | None = None
        self.configuration_window: tk.Toplevel | None = None
        self.scoring_window: tk.Toplevel | None = None
        self.adopt_adapt_window: tk.Toplevel | None = None
        self.thresholds_window: tk.Toplevel | None = None
        self.latest_metrics = None
        self.latest_snapshot = None
        self.scoring_weights = self._load_scoring_weights(self.settings)
        self.adopt_adapt_weights = self._load_adopt_adapt_weights(self.settings)
        self.scoring_thresholds = self._load_scoring_thresholds(self.settings)
        self.adopt_adapt_thresholds = self._load_adopt_adapt_thresholds(self.settings)
        self.ai_usage_tags: list[str] = parse_ai_tags(self.settings)
        self._ai_tags_listbox: tk.Listbox | None = None

        self.queue: Queue[tuple[str, object]] = Queue()
        self.worker: Thread | None = None
        self.action_buttons: list[ttk.Button] = []
        self.orgs: list[OrgSummary] = []
        self.orgs_by_label: dict[str, OrgSummary] = {}
        self.cli_service = SalesforceCliService(self.app_dir, log_callback=self._queue_log)

        self.discussion_messages: list[AIMessage] = []
        self.discussion_worker: Thread | None = None
        self.discussion_pending: bool = False
        self._discussion_last_send_ts: float = 0.0

        self._build_ui()
        self._apply_language(initial=True)
        self._load_branding()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_queue)
        self.after(250, lambda: self._refresh_orgs(initial=True))

    def _build_ui(self) -> None:
        self._build_menu_bar()
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        self.main_canvas = tk.Canvas(container, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        frame = ttk.Frame(self.main_canvas, padding=16)
        canvas_window = self.main_canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(_event) -> None:
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:
            self.main_canvas.itemconfigure(canvas_window, width=event.width)

        def _on_mousewheel(event) -> None:
            self.main_canvas.yview_scroll(int(-event.delta / 120), "units")

        frame.bind("<Configure>", _on_frame_configure)
        self.main_canvas.bind("<Configure>", _on_canvas_configure)
        self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        header_frame = ttk.Frame(frame)
        header_frame.pack(fill="x")

        header_left = ttk.Frame(header_frame)
        header_left.pack(side="left", fill="x", expand=True)

        header_top = ttk.Frame(header_left)
        header_top.pack(fill="x")

        self.title_label = ttk.Label(header_top, font=("Segoe UI", 16, "bold"))
        self.title_label.pack(side="left", anchor="w")

        language_frame = ttk.Frame(header_top)
        language_frame.pack(side="right")
        self.language_title_label = ttk.Label(language_frame)
        self.language_title_label.pack(side="left", padx=(0, 8))
        self.language_combo = ttk.Combobox(
            language_frame,
            textvariable=self.language_label_var,
            state="readonly",
            width=12,
        )
        self.language_combo.pack(side="left")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        self.description_label = ttk.Label(header_left, wraplength=620, justify="left")
        self.description_label.pack(anchor="w", pady=(6, 8))

        self.hero_label = ttk.Label(header_frame)
        self.hero_label.pack(side="right", anchor="ne", padx=(16, 0))

        self.main_notebook = ttk.Notebook(frame)
        self.main_notebook.pack(fill="both", expand=True, pady=(12, 0))

        self.documentation_tab = ttk.Frame(self.main_notebook, padding=(0, 8))
        self.discussion_tab = ttk.Frame(self.main_notebook, padding=(0, 8))
        self.main_notebook.add(self.documentation_tab, text=self._t("tab_documentation"))
        self.main_notebook.add(self.discussion_tab, text=self._t("tab_discussion"))

        self.cli_frame = ttk.LabelFrame(self.documentation_tab, padding=12)
        self.cli_frame.pack(fill="x", pady=(0, 12))

        login_row = ttk.Frame(self.cli_frame)
        login_row.pack(fill="x", pady=(0, 8))
        self.alias_label = ttk.Label(login_row, width=14)
        self.alias_label.pack(side="left")
        ttk.Entry(login_row, textvariable=self.alias_var, width=24).pack(side="left", padx=(0, 12))
        self.environment_label = ttk.Label(login_row, width=14)
        self.environment_label.pack(side="left")
        self.login_target_combo = ttk.Combobox(
            login_row,
            textvariable=self.login_target_var,
            state="readonly",
            width=14,
        )
        self.login_target_combo.pack(side="left", padx=(0, 12))
        self.login_target_combo.bind("<<ComboboxSelected>>", self._on_login_target_changed)
        self.instance_url_label = ttk.Label(login_row, width=14)
        self.instance_url_label.pack(side="left")
        self.instance_url_entry = ttk.Entry(login_row, textvariable=self.instance_url_var)
        self.instance_url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.login_button = self._track_button(ttk.Button(login_row, command=self._login_web))
        self.login_button.pack(side="left")

        org_row = ttk.Frame(self.cli_frame)
        org_row.pack(fill="x")
        self.org_available_label = ttk.Label(org_row, width=14)
        self.org_available_label.pack(side="left")
        self.org_combo = ttk.Combobox(
            org_row,
            textvariable=self.selected_org_var,
            state="readonly",
        )
        self.org_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.refresh_button = self._track_button(ttk.Button(org_row, command=self._refresh_orgs))
        self.refresh_button.pack(side="left", padx=(0, 8))
        self.generate_manifest_button = self._track_button(ttk.Button(org_row, command=self._generate_manifest))
        self.generate_manifest_button.pack(side="left", padx=(0, 8))
        self.retrieve_button = self._track_button(ttk.Button(org_row, command=self._retrieve_from_selected_org))
        self.retrieve_button.pack(side="left", padx=(0, 8))
        self.full_pipeline_button = self._track_button(ttk.Button(org_row, command=self._run_full_pipeline))
        self.full_pipeline_button.pack(side="left")

        self.org_check_frame = ttk.LabelFrame(self.documentation_tab, padding=12)
        self.org_check_frame.pack(fill="x", pady=(0, 12))
        org_check_row = ttk.Frame(self.org_check_frame)
        org_check_row.pack(fill="x")
        self.org_check_type_label = ttk.Label(org_check_row, width=18)
        self.org_check_type_label.pack(side="left")
        self.org_check_combo = ttk.Combobox(
            org_check_row,
            textvariable=self.org_check_choice_var,
            values=self.ORG_CHECK_CHOICES,
            state="readonly",
            width=24,
        )
        self.org_check_combo.pack(side="left", padx=(0, 8))
        self.org_check_button = self._track_button(ttk.Button(org_check_row, command=self._run_org_check_excel))
        self.org_check_button.pack(side="left")

        self.doc_frame = ttk.LabelFrame(self.documentation_tab, padding=12)
        self.doc_frame.pack(fill="x", pady=(0, 12))

        self.source_folder_widgets = self._folder_picker(
            self.doc_frame, self.source_var, self._choose_source, self._open_source_folder
        )
        self.output_folder_widgets = self._folder_picker(
            self.doc_frame, self.output_var, self._choose_output, self._open_output_folder
        )
        self.exclusion_file_widgets = self._file_picker(
            self.doc_frame,
            self.exclusion_file_var,
            self._choose_exclusion_file,
            self._open_exclusion_file,
        )
        self.pmd_frame = ttk.LabelFrame(self.doc_frame, padding=8)
        self.pmd_frame.pack(fill="x", pady=(2, 0))
        pmd_toggle_row = ttk.Frame(self.pmd_frame)
        pmd_toggle_row.pack(fill="x", pady=(0, 4))
        self.pmd_enabled_check = ttk.Checkbutton(
            pmd_toggle_row,
            variable=self.pmd_enabled_var,
            command=self._on_pmd_toggle,
        )
        self.pmd_enabled_check.pack(side="left")
        self.pmd_file_widgets = self._file_picker(
            self.pmd_frame,
            self.pmd_ruleset_var,
            self._choose_pmd_ruleset_file,
            self._open_pmd_ruleset_file,
        )

        button_row = ttk.Frame(self.doc_frame)
        button_row.pack(fill="x", pady=(8, 0))
        self.generate_button = self._track_button(ttk.Button(button_row, command=self._start_generation))
        self.generate_button.pack(side="left")
        self.open_index_button = self._track_button(ttk.Button(button_row, command=self._open_index))
        self.open_index_button.pack(side="right")
        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(16, 0))

        self.log_widget = scrolledtext.ScrolledText(self.documentation_tab, wrap="word", height=20)
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

        self._build_discussion_tab(self.discussion_tab)

    def _build_discussion_tab(self, parent: ttk.Frame) -> None:
        discussion_panel.build_panel(self, parent)

    def _append_discussion_line(self, text: str, tag: str = "system") -> None:
        discussion_panel.append_line(self, text, tag)

    def _clear_discussion_history(self) -> None:
        discussion_panel.clear_history(self)

    def _update_discussion_context_status(self) -> None:
        discussion_panel.update_context_status(self)

    def _send_discussion_message(self) -> None:
        discussion_panel.send_message(self)

    def _handle_discussion_reply(self, payload: dict[str, str]) -> None:
        discussion_panel.handle_reply(self, payload)

    def _handle_discussion_error(self, message: str) -> None:
        discussion_panel.handle_error(self, message)

    def _handle_discussion_info(self, payload: dict[str, object]) -> None:
        discussion_panel.handle_info(self, payload)

    def _open_index(self) -> None:
        output = self._validate_output_dir()
        if output is None:
            return
        index_path = output / "index.html"
        if not index_path.exists():
            messagebox.showerror(self._t("error_title"), self._t("index_not_found"))
            return
        webbrowser.open_new_tab(index_path.as_uri())

    def _folder_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> dict[str, ttk.Widget]:
        return self._path_picker(parent, variable, browse_command, open_command)

    def _file_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> dict[str, ttk.Widget]:
        return self._path_picker(parent, variable, browse_command, open_command)

    def _path_picker(
        self,
        parent: tk.Widget,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
        open_command: Callable[[], None],
    ) -> dict[str, ttk.Widget]:
        # Folder and file pickers shared the same widget layout. The two
        # public-looking methods are kept to preserve readability of call sites
        # (folder vs. file intent) while delegating here to remove duplication.
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=6)

        label = ttk.Label(wrapper, width=18)
        label.pack(side="left")
        entry = ttk.Entry(wrapper, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        browse_button = self._track_button(ttk.Button(wrapper, command=browse_command))
        browse_button.pack(side="left", padx=(0, 8))
        open_button = self._track_button(ttk.Button(wrapper, command=open_command))
        open_button.pack(side="left")
        return {
            "label": label,
            "browse_button": browse_button,
            "open_button": open_button,
        }

    def _track_button(self, button: ttk.Button) -> ttk.Button:
        self.action_buttons.append(button)
        return button

    def _build_menu_bar(self) -> None:
        menu_bar = tk.Menu(self)

        # The Documentation menu is intentionally added first so it sits on
        # the leftmost side of the menu bar. It mirrors the main "Generate"
        # button while exposing per-output shortcuts (Excels, HTML, Word).
        documentation_menu = tk.Menu(menu_bar, tearoff=False)
        documentation_menu.add_command(
            label=self._t("menu_generate_documentation"),
            command=self._menu_generate_documentation,
        )
        documentation_menu.add_separator()
        documentation_menu.add_command(
            label=self._t("menu_generate_excels"),
            command=self._menu_generate_excels,
        )
        documentation_menu.add_command(
            label=self._t("menu_generate_html"),
            command=self._menu_generate_html,
        )
        documentation_menu.add_command(
            label=self._t("menu_generate_word"),
            command=self._menu_generate_word,
        )
        menu_bar.add_cascade(
            label=self._t("documentation_menu"), menu=documentation_menu
        )

        download_menu = tk.Menu(menu_bar, tearoff=False)
        download_menu.add_command(
            label=self._t("download_sf_cli"),
            command=lambda: self._open_external_url(self.SF_CLI_DOWNLOAD_URL),
        )
        download_menu.add_command(
            label=self._t("download_pmd"),
            command=lambda: self._open_external_url(self.PMD_DOWNLOAD_URL),
        )
        download_menu.add_command(
            label=self._t("ORG CHECK app exchange"),
            command=lambda: self._open_external_url(self.ORG_CHECK_APP_URL),
        )
        download_menu.add_command(
            label=self._t("ORG CHECK github"),
            command=lambda: self._open_external_url(self.ORG_CHECK_GITHUB_URL),
        )
        menu_bar.add_cascade(label=self._t("download_menu"), menu=download_menu)

        configuration_menu = tk.Menu(menu_bar, tearoff=False)
        configuration_menu.add_command(
            label=self._t("show_configuration_screen"),
            command=self._show_configuration_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_scoring_menu_item"),
            command=self._show_scoring_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_adopt_adapt_menu_item"),
            command=self._show_adopt_adapt_screen,
        )
        configuration_menu.add_command(
            label=self._t("view_thresholds_menu_item"),
            command=self._show_threshold_screen,
        )
        menu_bar.add_cascade(label=self._t("configuration_menu"), menu=configuration_menu)

        self.config(menu=menu_bar)
        self.menu_bar = menu_bar

    def _open_external_url(self, url: str) -> None:
        webbrowser.open_new_tab(url)

    def _configure_secondary_window(self, window: tk.Toplevel) -> None:
        # Ensure every secondary window keeps its minimize/maximize buttons
        # (calling ``transient`` on Windows turns the window into a dialog and
        # strips those controls). We also force a regular, resizable window
        # frame and reuse the application icon for visual consistency.
        window.resizable(True, True)
        try:
            window.wm_attributes("-toolwindow", False)
        except tk.TclError:
            pass
        if self.icon_image is not None:
            try:
                window.iconphoto(False, self.icon_image)
            except tk.TclError:
                pass

    def _show_configuration_screen(self) -> None:
        existing = self.configuration_window
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return

        window = tk.Toplevel(self)
        window.title(self._t("configuration_title"))
        window.geometry("980x720")
        self._configure_secondary_window(window)

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
            text=self._t("configuration_title"),
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill="both", expand=True)

        doc_tab = ttk.Frame(notebook, padding=12)
        discussion_tab = ttk.Frame(notebook, padding=12)
        rules_tab = ttk.Frame(notebook, padding=12)
        ai_tags_tab = ttk.Frame(notebook, padding=12)
        notebook.add(doc_tab, text=self._t("configuration_tab_documentation"))
        notebook.add(discussion_tab, text=self._t("configuration_tab_discussion"))
        notebook.add(rules_tab, text=self._t("configuration_tab_rules"))
        notebook.add(ai_tags_tab, text=self._t("configuration_tab_ai_tags"))

        edit_vars = {
            "language": tk.StringVar(value=self._language_display(self.language)),
            "login_target": tk.StringVar(value=self._login_target_display(self.login_target_key)),
            "instance_url": tk.StringVar(value=self.instance_url_var.get()),
            "alias": tk.StringVar(value=self.alias_var.get()),
            "source": tk.StringVar(value=self.source_var.get()),
            "output": tk.StringVar(value=self.output_var.get()),
            "exclusion_file": tk.StringVar(value=self.exclusion_file_var.get()),
            "pmd_enabled": tk.BooleanVar(value=bool(self.pmd_enabled_var.get())),
            "pmd_ruleset": tk.StringVar(value=self.pmd_ruleset_var.get()),
            "org_check_type": tk.StringVar(value=self.org_check_choice_var.get()),
            "ai_provider": tk.StringVar(value=self.ai_provider_var.get()),
            "claude_key": tk.StringVar(value=self.claude_api_key_var.get()),
            "gemini_key": tk.StringVar(value=self.gemini_api_key_var.get()),
            "claude_model": tk.StringVar(value=self.claude_model_var.get()),
            "gemini_model": tk.StringVar(value=self.gemini_model_var.get()),
            "generate_excels": tk.BooleanVar(value=bool(self.generate_excels_var.get())),
            "generate_org_check_reports": tk.BooleanVar(
                value=bool(self.generate_org_check_reports_var.get())
            ),
            "generate_data_dictionary_word": tk.BooleanVar(
                value=bool(self.generate_data_dictionary_word_var.get())
            ),
            "generate_summary_word": tk.BooleanVar(
                value=bool(self.generate_summary_word_var.get())
            ),
        }

        self._build_configuration_documentation_tab(doc_tab, edit_vars)
        self._build_configuration_discussion_tab(discussion_tab, edit_vars)
        self._build_configuration_rules_tab(rules_tab)
        self._build_configuration_ai_tags_tab(ai_tags_tab)

        buttons_row = ttk.Frame(scrollable_frame)
        buttons_row.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons_row,
            text=self._t("configuration_cancel"),
            command=window.destroy,
        ).pack(side="right")
        ttk.Button(
            buttons_row,
            text=self._t("configuration_save"),
            command=lambda: self._apply_configuration_changes(edit_vars, window),
        ).pack(side="right", padx=(0, 8))

        self.configuration_window = window
        window.focus_set()

    def _build_configuration_documentation_tab(
        self, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]
    ) -> None:
        general = ttk.LabelFrame(parent, text=self._t("configuration_section_general"), padding=10)
        general.pack(fill="x", pady=(0, 8))
        self._config_combo_row(
            general,
            self._t("language"),
            edit_vars["language"],
            [self._language_display(code) for code in self.LANGUAGES],
        )

        salesforce = ttk.LabelFrame(parent, text=self._t("configuration_section_salesforce"), padding=10)
        salesforce.pack(fill="x", pady=(0, 8))
        self._config_entry_row(salesforce, self._t("alias"), edit_vars["alias"])
        self._config_combo_row(
            salesforce,
            self._t("environment"),
            edit_vars["login_target"],
            [self._login_target_display(key) for key in self.LOGIN_TARGETS],
        )
        self._config_entry_row(salesforce, self._t("instance_url"), edit_vars["instance_url"])

        paths = ttk.LabelFrame(parent, text=self._t("configuration_section_paths"), padding=10)
        paths.pack(fill="x", pady=(0, 8))
        self._config_entry_row(paths, self._t("source_folder"), edit_vars["source"])
        self._config_entry_row(paths, self._t("output_folder"), edit_vars["output"])
        self._config_entry_row(paths, self._t("exclusion_file"), edit_vars["exclusion_file"])

        analysis = ttk.LabelFrame(parent, text=self._t("configuration_section_analysis"), padding=10)
        analysis.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(
            analysis, text=self._t("pmd_enabled"), variable=edit_vars["pmd_enabled"]
        ).pack(anchor="w", pady=(0, 4))
        self._config_entry_row(analysis, self._t("pmd_ruleset_file"), edit_vars["pmd_ruleset"])
        self._config_combo_row(
            analysis,
            self._t("org_check_type"),
            edit_vars["org_check_type"],
            list(self.ORG_CHECK_CHOICES),
        )

        reports = ttk.LabelFrame(parent, text=self._t("configuration_section_reports"), padding=10)
        reports.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(
            reports,
            text=self._t("configuration_generate_excels"),
            variable=edit_vars["generate_excels"],
        ).pack(anchor="w", pady=(2, 2))
        ttk.Checkbutton(
            reports,
            text=self._t("configuration_generate_org_check_reports"),
            variable=edit_vars["generate_org_check_reports"],
        ).pack(anchor="w", pady=(2, 2))
        ttk.Checkbutton(
            reports,
            text=self._t("configuration_generate_data_dictionary_word"),
            variable=edit_vars["generate_data_dictionary_word"],
        ).pack(anchor="w", pady=(2, 2))
        ttk.Checkbutton(
            reports,
            text=self._t("configuration_generate_summary_word"),
            variable=edit_vars["generate_summary_word"],
        ).pack(anchor="w", pady=(2, 2))

    def _build_configuration_discussion_tab(
        self, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]
    ) -> None:
        ai_frame = ttk.LabelFrame(parent, text=self._t("configuration_section_ai"), padding=10)
        ai_frame.pack(fill="x", pady=(0, 8))
        self._config_combo_row(
            ai_frame,
            self._t("configuration_ai_provider"),
            edit_vars["ai_provider"],
            list(self.AI_PROVIDERS),
        )
        self._config_entry_row(
            ai_frame, self._t("configuration_claude_key"), edit_vars["claude_key"], show="*"
        )
        self._config_combo_row(
            ai_frame,
            self._t("configuration_claude_model"),
            edit_vars["claude_model"],
            list(self.CLAUDE_MODEL_CHOICES),
        )
        self._config_entry_row(
            ai_frame, self._t("configuration_gemini_key"), edit_vars["gemini_key"], show="*"
        )
        self._config_combo_row(
            ai_frame,
            self._t("configuration_gemini_model"),
            edit_vars["gemini_model"],
            list(self.GEMINI_MODEL_CHOICES),
        )
        ttk.Label(
            ai_frame,
            text=self._t("configuration_model_hint"),
            wraplength=640,
            justify="left",
            foreground="#475569",
        ).pack(anchor="w", pady=(6, 0))

        prompt_frame = ttk.LabelFrame(
            parent, text=self._t("configuration_section_prompt"), padding=10
        )
        prompt_frame.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Label(
            prompt_frame,
            text=self._t("configuration_system_prompt_description"),
            wraplength=640,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        prompt_widget = scrolledtext.ScrolledText(
            prompt_frame, wrap="word", height=10, font=("Segoe UI", 10)
        )
        prompt_widget.pack(fill="both", expand=True)
        prompt_widget.insert("1.0", self.system_prompt)
        self._config_system_prompt_widget = prompt_widget

        button_row = ttk.Frame(prompt_frame)
        button_row.pack(fill="x", pady=(6, 0))
        ttk.Button(
            button_row,
            text=self._t("configuration_system_prompt_reset"),
            command=self._reset_system_prompt_editor,
        ).pack(side="right")

    def _config_entry_row(
        self,
        parent: ttk.Frame,
        label_text: str,
        variable: tk.Variable,
        show: str | None = None,
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label_text, width=22).pack(side="left")
        entry = ttk.Entry(row, textvariable=variable)
        if show is not None:
            entry.configure(show=show)
        entry.pack(side="left", fill="x", expand=True)

    def _config_combo_row(
        self,
        parent: ttk.Frame,
        label_text: str,
        variable: tk.Variable,
        values: list[str],
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label_text, width=22).pack(side="left")
        combo = ttk.Combobox(row, textvariable=variable, values=values, state="readonly")
        combo.pack(side="left", fill="x", expand=True)

    def _reset_system_prompt_editor(self) -> None:
        widget = self._config_system_prompt_widget
        if widget is None:
            return
        default_prompt = build_system_prompt(self.language)
        widget.delete("1.0", "end")
        widget.insert("1.0", default_prompt)

    # ----- Analyzer rules configuration -------------------------------------

    ANALYZER_SEVERITY_ORDER: tuple[str, ...] = ("Critical", "Major", "Minor", "Info")

    ANALYZER_SEVERITY_COLORS: dict[str, str] = {
        "Critical": "#991b1b",
        "Major": "#9a3412",
        "Minor": "#854d0e",
        "Info": "#1e3a8a",
    }

    def _build_configuration_rules_tab(self, parent: ttk.Frame) -> None:
        analyzer_rules_panel.build_panel(self, parent)

    def _build_configuration_ai_tags_tab(self, parent: ttk.Frame) -> None:
        ai_tags_panel.build_panel(self, parent)

    def _persist_analyzer_rules(self) -> None:
        analyzer_rules_panel.persist_changes(self)

    def _reset_analyzer_rules_state(self) -> None:
        analyzer_rules_panel.reset_state(self)

    def _collect_ai_usage_tags(self) -> list[str]:
        """Return the de-duplicated tag list edited in the configuration tab."""

        raw = ai_tags_panel.collect_tags(self)
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in raw:
            text = value.strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        return cleaned

    def _reset_ai_tags_state(self) -> None:
        ai_tags_panel.reset_state(self)

    def _apply_configuration_changes(
        self, edit_vars: dict[str, tk.Variable], window: tk.Toplevel
    ) -> None:
        new_language = self._language_code_from_display(edit_vars["language"].get())
        language_changed = new_language != self.language
        self.language = new_language

        new_login_target = self._login_target_key_from_display(edit_vars["login_target"].get())
        self.login_target_key = new_login_target

        self.instance_url_var.set(edit_vars["instance_url"].get().strip())
        self.alias_var.set(edit_vars["alias"].get().strip())
        self.source_var.set(edit_vars["source"].get().strip())
        self.output_var.set(edit_vars["output"].get().strip())
        self.exclusion_file_var.set(edit_vars["exclusion_file"].get().strip())
        self.pmd_enabled_var.set(bool(edit_vars["pmd_enabled"].get()))
        self.pmd_ruleset_var.set(edit_vars["pmd_ruleset"].get().strip())

        org_check_choice = edit_vars["org_check_type"].get().strip()
        if org_check_choice:
            self.org_check_choice_var.set(org_check_choice)

        provider = edit_vars["ai_provider"].get().strip()
        if provider in self.AI_PROVIDERS:
            self.ai_provider_var.set(provider)

        self.claude_api_key_var.set(edit_vars["claude_key"].get())
        self.gemini_api_key_var.set(edit_vars["gemini_key"].get())

        claude_model_choice = edit_vars["claude_model"].get().strip()
        if claude_model_choice in self.CLAUDE_MODEL_CHOICES:
            self.claude_model_var.set(claude_model_choice)
        gemini_model_choice = edit_vars["gemini_model"].get().strip()
        if gemini_model_choice in self.GEMINI_MODEL_CHOICES:
            self.gemini_model_var.set(gemini_model_choice)
        self.generate_excels_var.set(bool(edit_vars["generate_excels"].get()))
        self.generate_org_check_reports_var.set(
            bool(edit_vars["generate_org_check_reports"].get())
        )
        self.generate_data_dictionary_word_var.set(
            bool(edit_vars["generate_data_dictionary_word"].get())
        )
        self.generate_summary_word_var.set(
            bool(edit_vars["generate_summary_word"].get())
        )

        if self._config_system_prompt_widget is not None:
            prompt_text = self._config_system_prompt_widget.get("1.0", "end").strip()
            self.system_prompt = prompt_text or build_system_prompt(self.language)
        self._config_system_prompt_widget = None

        self._persist_analyzer_rules()
        self._reset_analyzer_rules_state()

        collected_tags = self._collect_ai_usage_tags()
        self.ai_usage_tags = collected_tags or list(DEFAULT_AI_USAGE_TAGS)
        self._reset_ai_tags_state()

        self._save_settings()

        if language_changed:
            self._apply_language()
        else:
            self._apply_pmd_state()
            self._on_login_target_changed()

        self._append_log(self._t("configuration_saved"))
        window.destroy()

    def _on_generation_result(self, result: GenerationResult) -> None:
        index_path = result.index
        if index_path is not None:
            self._append_log(self._t("index_log", path=index_path))
        snapshot = result.snapshot
        metrics = getattr(snapshot, "metrics", None)
        if metrics is not None:
            self.latest_metrics = metrics
        if snapshot is not None:
            self.latest_snapshot = snapshot
            self._update_discussion_context_status()
            self._append_discussion_line(self._t("discussion_context_loaded"))

    def _show_scoring_screen(self) -> None:
        show_scoring_screen(self)

    def _show_adopt_adapt_screen(self) -> None:
        show_adopt_adapt_screen(self)

    def _show_threshold_screen(self) -> None:
        show_threshold_screen(self)

    def _load_branding(self) -> None:
        image_path = self.app_dir / "image" / "Lucie.png"
        if not image_path.exists():
            return

        try:
            self.icon_image = tk.PhotoImage(file=str(image_path))
            self.iconphoto(True, self.icon_image)

            self.hero_image = tk.PhotoImage(file=str(image_path))
            # Target ~90 px on the longest side (half of the previous 180 px)
            # so the hero image takes less vertical space in the main window.
            width = max(1, self.hero_image.width() // 90)
            height = max(1, self.hero_image.height() // 90)
            factor = max(width, height)
            if factor > 1:
                self.hero_image = self.hero_image.subsample(factor, factor)
            self.hero_label.configure(image=self.hero_image)
        except tk.TclError:
            self._append_log(self._t("branding_error"))

    def _load_settings(self) -> dict[str, Any]:
        return load_settings(self.settings_path)

    def _load_scoring_weights(self, settings: dict[str, Any]) -> dict[str, int]:
        return parse_weights(settings, "scoring_weights", DEFAULT_SCORING_WEIGHTS)

    def _load_adopt_adapt_weights(self, settings: dict[str, Any]) -> dict[str, int]:
        from src.core.models import DEFAULT_ADOPT_ADAPT_WEIGHTS

        return parse_weights(settings, "adopt_adapt_weights", DEFAULT_ADOPT_ADAPT_WEIGHTS)

    def _load_scoring_thresholds(
        self, settings: dict[str, Any]
    ) -> tuple[int, int, int]:
        return parse_thresholds(
            settings, "scoring_thresholds", DEFAULT_SCORING_THRESHOLDS
        )

    def _load_adopt_adapt_thresholds(
        self, settings: dict[str, Any]
    ) -> tuple[int, int, int]:
        return parse_thresholds(
            settings, "adopt_adapt_thresholds", DEFAULT_ADOPT_ADAPT_THRESHOLDS
        )

    def _save_settings(self) -> None:
        payload: dict[str, Any] = {
            "language": self.language,
            "login_target": self.login_target_key,
            "instance_url": self.instance_url_var.get().strip(),
            "alias": self.alias_var.get().strip(),
            "source_folder": self.source_var.get().strip(),
            "output_folder": self.output_var.get().strip(),
            "exclusion_file": self.exclusion_file_var.get().strip(),
            "pmd_enabled": bool(self.pmd_enabled_var.get()),
            "pmd_ruleset_file": self.pmd_ruleset_var.get().strip(),
            "org_check_type": self.org_check_choice_var.get().strip(),
            "ai_provider": self.ai_provider_var.get().strip() or self.AI_PROVIDERS[0],
            "claude_api_key": self.claude_api_key_var.get(),
            "gemini_api_key": self.gemini_api_key_var.get(),
            "claude_model": self.claude_model_var.get().strip() or self.DEFAULT_CLAUDE_MODEL,
            "gemini_model": self.gemini_model_var.get().strip() or self.DEFAULT_GEMINI_MODEL,
            "system_prompt": self.system_prompt,
            "generate_excels": bool(self.generate_excels_var.get()),
            "generate_org_check_reports": bool(self.generate_org_check_reports_var.get()),
            "generate_data_dictionary_word": bool(
                self.generate_data_dictionary_word_var.get()
            ),
            "generate_summary_word": bool(self.generate_summary_word_var.get()),
            "scoring_weights": dict(self.scoring_weights),
            "adopt_adapt_weights": dict(self.adopt_adapt_weights),
            "scoring_thresholds": list(self.scoring_thresholds),
            "adopt_adapt_thresholds": list(self.adopt_adapt_thresholds),
            "ai_usage_tags": list(self.ai_usage_tags),
        }
        save_settings(self.settings_path, payload)
        self.settings = payload

    def _t(self, key: str, **kwargs) -> str:
        text = self.TRANSLATIONS.get(self.language, self.TRANSLATIONS["fr"]).get(key, key)
        return text.format(**kwargs)

    def _language_display(self, code: str) -> str:
        return self.LANGUAGES.get(code, "Francais")

    def _language_code_from_display(self, display: str) -> str:
        for code, label in self.LANGUAGES.items():
            if label == display:
                return code
        return "fr"

    def _login_target_display(self, key: str) -> str:
        return self._t(key)

    def _login_target_key_from_display(self, display: str) -> str:
        for key in self.LOGIN_TARGETS:
            if self._login_target_display(key) == display:
                return key
        return "production"

    def _apply_language(self, initial: bool = False) -> None:
        self._build_menu_bar()
        self.title(self._t("window_title"))
        self.title_label.configure(text=self._t("header_title"))
        self.description_label.configure(text=self._t("header_description"))
        self.language_title_label.configure(text=self._t("language"))
        self.cli_frame.configure(text=self._t("salesforce_cli"))
        self.alias_label.configure(text=self._t("alias"))
        self.environment_label.configure(text=self._t("environment"))
        self.instance_url_label.configure(text=self._t("instance_url"))
        self.org_available_label.configure(text=self._t("org_available"))
        self.org_check_frame.configure(text=self._t("org_check"))
        self.org_check_type_label.configure(text=self._t("org_check_type"))
        self.doc_frame.configure(text=self._t("documentation_generation"))
        self.source_folder_widgets["label"].configure(text=self._t("source_folder"))
        self.source_folder_widgets["browse_button"].configure(text=self._t("browse"))
        self.source_folder_widgets["open_button"].configure(text=self._t("open"))
        self.output_folder_widgets["label"].configure(text=self._t("output_folder"))
        self.output_folder_widgets["browse_button"].configure(text=self._t("browse"))
        self.output_folder_widgets["open_button"].configure(text=self._t("open"))
        self.exclusion_file_widgets["label"].configure(text=self._t("exclusion_file"))
        self.exclusion_file_widgets["browse_button"].configure(text=self._t("browse"))
        self.exclusion_file_widgets["open_button"].configure(text=self._t("open"))
        self.pmd_frame.configure(text=self._t("pmd_quality"))
        self.pmd_enabled_check.configure(text=self._t("pmd_enabled"))
        self.pmd_file_widgets["label"].configure(text=self._t("pmd_ruleset_file"))
        self.pmd_file_widgets["browse_button"].configure(text=self._t("browse"))
        self.pmd_file_widgets["open_button"].configure(text=self._t("open"))
        self.login_button.configure(text=self._t("web_login"))
        self.refresh_button.configure(text=self._t("refresh"))
        self.generate_manifest_button.configure(text=self._t("generate_manifest"))
        self.retrieve_button.configure(text=self._t("retrieve"))
        self.full_pipeline_button.configure(text=self._t("full_pipeline"))
        self.org_check_button.configure(text=self._t("generate_org_check_excel"))
        self.generate_button.configure(text=self._t("generate_doc"))
        self.open_index_button.configure(text=self._t("open_index"))
        self.status_var.set(self._t("ready") if initial else self.status_var.get())

        self.main_notebook.tab(self.documentation_tab, text=self._t("tab_documentation"))
        self.main_notebook.tab(self.discussion_tab, text=self._t("tab_discussion"))
        self.discussion_title_label.configure(text=self._t("discussion_title"))
        self.discussion_description_label.configure(text=self._t("discussion_description"))
        self.discussion_provider_label.configure(text=self._t("discussion_provider"))
        self.discussion_history_label.configure(text=self._t("discussion_history"))
        self.discussion_input_label.configure(text=self._t("discussion_input"))
        self.discussion_send_button.configure(text=self._t("discussion_send"))
        self.discussion_clear_button.configure(text=self._t("discussion_clear"))
        self._update_discussion_context_status()

        self.language_combo["values"] = [self._language_display(code) for code in self.LANGUAGES]
        self.language_label_var.set(self._language_display(self.language))
        self.login_target_combo["values"] = [self._login_target_display(key) for key in self.LOGIN_TARGETS]
        self.login_target_var.set(self._login_target_display(self.login_target_key))
        self._on_login_target_changed()
        self._apply_pmd_state()

    def _on_language_changed(self, _event=None) -> None:
        new_language = self._language_code_from_display(self.language_label_var.get())
        if new_language == self.language:
            return
        self.language = new_language
        self._apply_language()
        self._save_settings()
        self._append_log(self._t("language_changed"))

    def _choose_source(self) -> None:
        folder = filedialog.askdirectory(title=self._t("choose_source_folder"))
        if folder:
            self.source_var.set(folder)

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title=self._t("choose_output_folder"))
        if folder:
            self.output_var.set(folder)

    def _choose_exclusion_file(self) -> None:
        selected_path = filedialog.askopenfilename(
            title=self._t("choose_exclusion_file"),
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
        )
        if selected_path:
            self.exclusion_file_var.set(selected_path)
            self._save_settings()

    def _choose_pmd_ruleset_file(self) -> None:
        selected_path = filedialog.askopenfilename(
            title=self._t("choose_pmd_ruleset_file"),
            filetypes=[("XML", "*.xml"), ("All files", "*.*")],
        )
        if selected_path:
            self.pmd_ruleset_var.set(selected_path)
            self._save_settings()

    def _open_folder(self, variable: tk.StringVar) -> None:
        folder = variable.get().strip()
        if not folder or not Path(folder).exists():
            messagebox.showerror(self._t("error_title"), self._t("directory_missing_to_open"))
            return
        os.startfile(folder)  # type: ignore[attr-defined]

    def _open_source_folder(self) -> None:
        self._open_folder(self.source_var)

    def _open_output_folder(self) -> None:
        self._open_folder(self.output_var)

    def _open_exclusion_file(self) -> None:
        file_path = self.exclusion_file_var.get().strip()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(self._t("error_title"), self._t("directory_missing_to_open"))
            return
        os.startfile(file_path)  # type: ignore[attr-defined]

    def _open_pmd_ruleset_file(self) -> None:
        file_path = self.pmd_ruleset_var.get().strip()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror(self._t("error_title"), self._t("directory_missing_to_open"))
            return
        os.startfile(file_path)  # type: ignore[attr-defined]

    def _on_pmd_toggle(self) -> None:
        self._apply_pmd_state()
        self._save_settings()

    def _apply_pmd_state(self) -> None:
        enabled = bool(self.pmd_enabled_var.get())
        state = "normal" if enabled else "disabled"
        self.pmd_file_widgets["label"].configure(state=state)
        self.pmd_file_widgets["browse_button"].configure(state=state)
        self.pmd_file_widgets["open_button"].configure(state=state)

    def _selected_pmd_ruleset_file(self) -> Path | None:
        value = self.pmd_ruleset_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            messagebox.showerror(self._t("error_title"), self._t("directory_missing_to_open"))
            return None
        return path

    def _selected_exclusion_file(self) -> Path | None:
        value = self.exclusion_file_var.get().strip()
        if not value:
            return None
        path = Path(value)
        if not path.exists() or path.is_dir():
            messagebox.showerror(self._t("error_title"), self._t("directory_missing_to_open"))
            return None
        return path

    def _on_login_target_changed(self, _event=None) -> None:
        selected_target = self._login_target_key_from_display(self.login_target_var.get())
        self.login_target_key = selected_target
        if selected_target == "custom":
            self.instance_url_entry.configure(state="normal")
            if self.instance_url_var.get().strip() in (
                self.LOGIN_TARGETS["production"],
                self.LOGIN_TARGETS["sandbox"],
                "",
            ):
                self.instance_url_var.set("")
        else:
            self.instance_url_var.set(self.LOGIN_TARGETS[selected_target])
            self.instance_url_entry.configure(state="readonly")
        self._save_settings()

    def _login_web(self) -> None:
        alias = self.alias_var.get().strip()
        if not alias:
            messagebox.showerror(self._t("error_title"), self._t("alias_required"))
            return

        instance_url = self.instance_url_var.get().strip()
        self._start_task(
            status_text=self._t("web_login_in_progress"),
            task=lambda: self.cli_service.login_web(alias, instance_url),
            success_message=self._t("web_login_done", alias=alias),
            on_success=self._on_orgs_loaded,
        )

    def _refresh_orgs(self, initial: bool = False) -> None:
        self._start_task(
            status_text=self._t("loading_orgs"),
            task=self.cli_service.list_orgs,
            success_message=self._t("org_list_refreshed"),
            on_success=self._on_orgs_loaded,
            notify=not initial,
        )

    def _on_orgs_loaded(self, orgs: list[OrgSummary]) -> None:
        current = self.selected_org_var.get()
        self.orgs = orgs
        self.orgs_by_label = {org.display_label: org for org in orgs}
        labels = [org.display_label for org in orgs]
        self.org_combo["values"] = labels

        if current in self.orgs_by_label:
            self.selected_org_var.set(current)
        elif labels:
            self.selected_org_var.set(labels[0])
        else:
            self.selected_org_var.set("")
        self._append_log(self._t("orgs_loaded", count=len(orgs)))

    def _selected_org(self) -> OrgSummary | None:
        label = self.selected_org_var.get().strip()
        return self.orgs_by_label.get(label)

    def _validate_source_for_cli(self) -> Path | None:
        source_value = self.source_var.get().strip()
        if not source_value:
            messagebox.showerror(self._t("error_title"), self._t("source_folder_required"))
            return None

        source = Path(source_value)
        if source.exists() and source.is_file():
            messagebox.showerror(self._t("error_title"), self._t("source_must_be_dir"))
            return None
        return source

    def _generate_manifest(self) -> None:
        source = self._validate_source_for_cli()
        if source is None:
            return

        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_manifest"))
            return

        self._start_task(
            status_text=self._t("manifest_in_progress"),
            task=lambda: self.cli_service.generate_manifest(selected_org.org_ref, source),
            success_message=self._t("manifest_done"),
            on_success=lambda manifest_path: self._append_log(self._t("manifest_ready", path=manifest_path)),
        )

    def _retrieve_from_selected_org(self) -> None:
        source = self._validate_source_for_cli()
        if source is None:
            return

        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_retrieve"))
            return

        manifest_path = source / "manifest" / "package.xml"
        if manifest_path.exists():
            task = lambda: self.cli_service.retrieve_from_org(selected_org.org_ref, source, manifest_path)
            success_message = self._t("retrieve_done")
        else:
            should_generate = messagebox.askyesno(
                self._t("manifest_missing_title"),
                self._t("manifest_missing_message"),
            )
            if not should_generate:
                return

            def task() -> Path:
                generated_manifest = self.cli_service.generate_manifest(selected_org.org_ref, source)
                return self.cli_service.retrieve_from_org(selected_org.org_ref, source, generated_manifest)

            success_message = self._t("manifest_retrieve_done")

        self._start_task(
            status_text=self._t("retrieve_in_progress"),
            task=task,
            success_message=success_message,
            on_success=lambda retrieved_path: self.source_var.set(str(retrieved_path)),
        )

    def _run_full_pipeline(self) -> None:
        source = self._validate_source_for_cli()
        if source is None:
            return

        output = self._validate_output_dir()
        if output is None:
            return

        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_pipeline"))
            return

        self._append_log(self._t("pipeline_log", org=selected_org.org_ref))
        self._append_log(self._t("source_log", path=source))
        self._append_log(self._t("output_log", path=output))
        exclusion_file = self._selected_exclusion_file()
        if self.exclusion_file_var.get().strip() and exclusion_file is None:
            return
        pmd_ruleset = self._selected_pmd_ruleset_file() if self.pmd_enabled_var.get() else None
        if self.pmd_enabled_var.get() and self.pmd_ruleset_var.get().strip() and pmd_ruleset is None:
            return

        generate_excels = bool(self.generate_excels_var.get())
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()
        org_ref = selected_org.org_ref

        def task() -> GenerationResult:
            manifest_path = self.cli_service.generate_manifest(selected_org.org_ref, source)
            retrieved_path = self.cli_service.retrieve_from_org(selected_org.org_ref, source, manifest_path)
            self._run_org_check_pre_step(
                output, generate_org_check, org_check_choice, org_ref
            )
            return SalesforceDocumentationGenerator(
                retrieved_path,
                output,
                exclusion_config_path=exclusion_file,
                pmd_enabled=bool(self.pmd_enabled_var.get()),
                pmd_ruleset_path=pmd_ruleset,
                generate_excels=generate_excels,
                generate_data_dictionary_word=bool(
                    self.generate_data_dictionary_word_var.get()
                ),
                generate_summary_word=bool(self.generate_summary_word_var.get()),
                scoring_weights=dict(self.scoring_weights),
                adopt_adapt_weights=dict(self.adopt_adapt_weights),
                scoring_thresholds=tuple(self.scoring_thresholds),
                adopt_adapt_thresholds=tuple(self.adopt_adapt_thresholds),
                ai_usage_tags=list(self.ai_usage_tags),
                language=self.language,
                log_callback=self._queue_log,
            ).generate()

        self._start_task(
            status_text=self._t("pipeline_in_progress"),
            task=task,
            success_message=self._t("pipeline_done"),
            on_success=self._on_generation_result,
        )

    def _run_org_check_excel(self) -> None:
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_org_check"))
            return

        check_choice = self.org_check_choice_var.get().strip()
        if not check_choice:
            messagebox.showerror(self._t("error_title"), self._t("org_check_choice_required"))
            return

        output = self._validate_output_dir()
        if output is None:
            return

        excel_dir = output / "excel"
        excel_path = excel_dir / f"{check_choice}.xlsx"
        self._append_log(self._t("output_log", path=excel_dir))
        self._start_task(
            status_text=self._t("org_check_in_progress"),
            task=lambda: self.cli_service.generate_org_check_excel(
                check_choice, selected_org.org_ref, excel_path
            ),
            success_message=self._t("org_check_done"),
            on_success=lambda generated_path: self._append_log(
                self._t("org_check_ready", path=generated_path)
            ),
        )

    def _validate_output_dir(self) -> Path | None:
        output_value = self.output_var.get().strip()
        if not output_value:
            messagebox.showerror(self._t("error_title"), self._t("output_folder_required"))
            return None

        output = Path(output_value)
        if output.exists() and output.is_file():
            messagebox.showerror(self._t("error_title"), self._t("output_must_be_dir"))
            return None
        return output

    def _start_generation(
        self,
        *,
        generate_html_override: bool | None = None,
        generate_excels_override: bool | None = None,
        generate_data_dictionary_word_override: bool | None = None,
        generate_summary_word_override: bool | None = None,
    ) -> None:
        # Overrides are used by the Documentation menu to force a single
        # output type regardless of what the user ticked in the
        # configuration screen. ``None`` means "fall back to the configured
        # value", which is the behaviour of the main "Generate" button.
        source_value = self.source_var.get().strip()

        if not source_value:
            messagebox.showerror(self._t("error_title"), self._t("source_folder_required"))
            return

        source = Path(source_value)
        output = self._validate_output_dir()
        if output is None:
            return

        if not source.exists():
            messagebox.showerror(self._t("error_title"), self._t("source_folder_missing"))
            return
        if source.is_file():
            messagebox.showerror(self._t("error_title"), self._t("source_must_be_dir"))
            return

        self._append_log(self._t("source_log", path=source))
        self._append_log(self._t("output_log", path=output))
        exclusion_file = self._selected_exclusion_file()
        if self.exclusion_file_var.get().strip() and exclusion_file is None:
            return
        pmd_ruleset = self._selected_pmd_ruleset_file() if self.pmd_enabled_var.get() else None
        if self.pmd_enabled_var.get() and self.pmd_ruleset_var.get().strip() and pmd_ruleset is None:
            return

        generate_excels = (
            bool(self.generate_excels_var.get())
            if generate_excels_override is None
            else generate_excels_override
        )
        generate_html = (
            True if generate_html_override is None else generate_html_override
        )
        generate_dd_word = (
            bool(self.generate_data_dictionary_word_var.get())
            if generate_data_dictionary_word_override is None
            else generate_data_dictionary_word_override
        )
        generate_summary_word = (
            bool(self.generate_summary_word_var.get())
            if generate_summary_word_override is None
            else generate_summary_word_override
        )
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()
        selected_org = self._selected_org()
        org_ref = selected_org.org_ref if selected_org else self.alias_var.get().strip()

        def task() -> GenerationResult:
            self._run_org_check_pre_step(
                output, generate_org_check, org_check_choice, org_ref
            )
            return SalesforceDocumentationGenerator(
                source,
                output,
                exclusion_config_path=exclusion_file,
                pmd_enabled=bool(self.pmd_enabled_var.get()),
                pmd_ruleset_path=pmd_ruleset,
                generate_excels=generate_excels,
                generate_html=generate_html,
                generate_data_dictionary_word=generate_dd_word,
                generate_summary_word=generate_summary_word,
                scoring_weights=dict(self.scoring_weights),
                adopt_adapt_weights=dict(self.adopt_adapt_weights),
                scoring_thresholds=tuple(self.scoring_thresholds),
                adopt_adapt_thresholds=tuple(self.adopt_adapt_thresholds),
                ai_usage_tags=list(self.ai_usage_tags),
                language=self.language,
                log_callback=self._queue_log,
            ).generate()

        self._start_task(
            status_text=self._t("doc_in_progress"),
            task=task,
            success_message=self._t("doc_done"),
            on_success=self._on_generation_result,
        )

    def _menu_generate_documentation(self) -> None:
        # Same behaviour as the main "Generate documentation" button: it
        # uses whatever the user configured in the configuration screen.
        self._start_generation()

    def _menu_generate_excels(self) -> None:
        self._start_generation(
            generate_html_override=False,
            generate_excels_override=True,
            generate_data_dictionary_word_override=False,
            generate_summary_word_override=False,
        )

    def _menu_generate_html(self) -> None:
        self._start_generation(
            generate_html_override=True,
            generate_excels_override=False,
            generate_data_dictionary_word_override=False,
            generate_summary_word_override=False,
        )

    def _menu_generate_word(self) -> None:
        self._start_generation(
            generate_html_override=False,
            generate_excels_override=False,
            generate_data_dictionary_word_override=True,
            generate_summary_word_override=True,
        )

    def _run_org_check_pre_step(
        self,
        output: Path,
        enabled: bool,
        check_choice: str,
        org_ref: str,
    ) -> None:
        if not enabled:
            return
        if not check_choice:
            self._queue_log(self._t("org_check_choice_required"))
            return
        if not org_ref:
            self._queue_log(self._t("select_org_org_check"))
            return
        excel_dir = output / "excel"
        excel_path = excel_dir / f"{check_choice}.xlsx"
        try:
            self._queue_log(self._t("org_check_in_progress"))
            generated_path = self.cli_service.generate_org_check_excel(
                check_choice, org_ref, excel_path
            )
            self._queue_log(self._t("org_check_ready", path=generated_path))
        except Exception as exc:
            self._queue_log(f"Echec Org Check: {exc}")

    def _start_task(
        self,
        *,
        status_text: str,
        task: Callable[[], Any],
        success_message: str,
        on_success: Callable[[Any], None] | None = None,
        notify: bool = True,
    ) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(self._t("info_title"), self._t("action_already_running"))
            return

        self.status_var.set(status_text)
        self._set_buttons_state(False)
        self.worker = Thread(
            target=self._run_task,
            args=(task, success_message, on_success, notify),
            daemon=True,
        )
        self.worker.start()

    def _run_task(
        self,
        task: Callable[[], Any],
        success_message: str,
        on_success: Callable[[Any], None] | None,
        notify: bool,
    ) -> None:
        try:
            result = task()
            self.queue.put(("done", (success_message, result, on_success, notify)))
        except Exception as exc:  # pragma: no cover - surfaced in UI
            self.queue.put(("error", str(exc)))

    def _queue_log(self, message: str) -> None:
        self.queue.put(("log", message))

    def _poll_queue(self) -> None:
        try:
            while True:
                event_type, payload = self.queue.get_nowait()
                if event_type == "log":
                    self._append_log(str(payload))
                elif event_type == "done":
                    success_message, result, on_success, notify = payload
                    if on_success is not None:
                        on_success(result)
                    self._append_log(success_message)
                    self.status_var.set(self._t("operation_done"))
                    self._set_buttons_state(True)
                    if notify:
                        messagebox.showinfo(self._t("success_title"), success_message)
                elif event_type == "error":
                    self._append_log(f"Erreur: {payload}")
                    self.status_var.set(self._t("operation_failed"))
                    self._set_buttons_state(True)
                    messagebox.showerror(self._t("error_title"), str(payload))
                elif event_type == "discussion_reply":
                    self._handle_discussion_reply(payload)
                elif event_type == "discussion_error":
                    self._handle_discussion_error(str(payload))
                elif event_type == "discussion_info":
                    if isinstance(payload, dict):
                        self._handle_discussion_info(payload)
        except Empty:
            pass
        self.after(150, self._poll_queue)

    def _set_buttons_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons:
            button.configure(state=state)

    def _append_log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", str(message) + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def _on_close(self) -> None:
        self._save_settings()
        self.destroy()
