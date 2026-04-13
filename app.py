from __future__ import annotations

import json
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from src.core.orchestrator import SalesforceDocumentationGenerator
from src.core.sf_cli_service import OrgSummary, SalesforceCliService


class Application(tk.Tk):
    LOGIN_TARGETS = {
        "production": "https://login.salesforce.com",
        "sandbox": "https://test.salesforce.com",
        "custom": "",
    }
    LANGUAGES = {"fr": "Francais", "en": "English"}
    ORG_CHECK_CHOICES = ["apex-classes", "global-view", "hardcoded-urls"]
    TRANSLATIONS = {
        "fr": {
            "window_title": "Lucie : Salesforce Doc Generator",
            "header_title": "Lucie : Salesforce Doc Generator",
            "header_description": "Choisissez les dossiers de travail, pilotez Salesforce CLI, puis lancez la generation de documentation.",
            "language": "Langue",
            "salesforce_cli": "Salesforce CLI",
            "alias": "Alias",
            "environment": "Environnement",
            "instance_url": "Instance URL",
            "org_available": "Org disponible",
            "documentation_generation": "Generation de documentation",
            "exclusion_file": "Fichier exclusions",
            "org_check": "Org Check",
            "org_check_type": "Type de check",
            "source_folder": "Dossier source",
            "output_folder": "Dossier de sortie",
            "browse": "Parcourir",
            "open": "Ouvrir",
            "web_login": "Connexion web",
            "refresh": "Actualiser",
            "generate_manifest": "Generer manifest",
            "retrieve": "Faire retrieve",
            "full_pipeline": "Manifest + Retrieve + Doc",
            "generate_doc": "Generer la documentation",
            "generate_org_check_excel": "Generer l'excel",
            "ready": "Pret.",
            "operation_done": "Operation terminee.",
            "operation_failed": "Echec de l'operation.",
            "success_title": "Succes",
            "error_title": "Erreur",
            "info_title": "Information",
            "language_changed": "Langue enregistree.",
            "source_folder_required": "Le dossier source est obligatoire.",
            "output_folder_required": "Le dossier de sortie est obligatoire.",
            "source_folder_missing": "Le dossier source est introuvable.",
            "source_must_be_dir": "Le chemin source doit etre un dossier.",
            "output_must_be_dir": "Le chemin de sortie doit etre un dossier.",
            "directory_missing_to_open": "Le dossier selectionne est introuvable.",
            "alias_required": "Un alias est obligatoire pour la connexion web.",
            "select_org_manifest": "Selectionnez une org avant de generer le manifest.",
            "select_org_retrieve": "Selectionnez une org avant de lancer le retrieve.",
            "select_org_pipeline": "Selectionnez une org avant de lancer le pipeline complet.",
            "select_org_org_check": "Selectionnez une org avant de lancer un org check.",
            "org_check_choice_required": "Selectionnez un type de org check.",
            "manifest_missing_title": "Manifest absent",
            "manifest_missing_message": "Aucun manifest n'a ete trouve dans le dossier source. Voulez-vous le generer puis lancer le retrieve ?",
            "action_already_running": "Une action est deja en cours.",
            "choose_source_folder": "Choisir le dossier source",
            "choose_output_folder": "Choisir le dossier de sortie",
            "choose_exclusion_file": "Choisir le fichier de configuration",
            "loading_orgs": "Chargement des orgs Salesforce...",
            "org_list_refreshed": "Liste des orgs actualisee.",
            "orgs_loaded": "{count} org(s) chargee(s) dans l'interface.",
            "web_login_in_progress": "Connexion Salesforce en cours...",
            "web_login_done": "Connexion terminee pour l'alias `{alias}`.",
            "manifest_in_progress": "Generation du manifest...",
            "manifest_done": "Manifest genere.",
            "manifest_ready": "Manifest pret: {path}",
            "retrieve_in_progress": "Retrieve Salesforce en cours...",
            "retrieve_done": "Retrieve termine.",
            "manifest_retrieve_done": "Manifest genere puis retrieve termine.",
            "pipeline_in_progress": "Manifest + retrieve + documentation en cours...",
            "pipeline_done": "Pipeline complet termine.",
            "org_check_in_progress": "Generation Org Check en cours...",
            "org_check_done": "Org Check termine.",
            "org_check_ready": "Excel Org Check genere: {path}",
            "doc_in_progress": "Generation de la documentation en cours...",
            "doc_done": "Generation terminee.",
            "branding_error": "Impossible de charger l'image Lucie.png pour le branding.",
            "source_log": "Source: {path}",
            "output_log": "Sortie: {path}",
            "pipeline_log": "Pipeline complet sur l'org: {org}",
            "index_log": "Index genere: {path}",
            "production": "Production",
            "sandbox": "Sandbox",
            "custom": "Personnalise",
        },
        "en": {
            "window_title": "Lucie: Salesforce Doc Generator",
            "header_title": "Lucie: Salesforce Doc Generator",
            "header_description": "Choose working folders, use Salesforce CLI, then generate the documentation.",
            "language": "Language",
            "salesforce_cli": "Salesforce CLI",
            "alias": "Alias",
            "environment": "Environment",
            "instance_url": "Instance URL",
            "org_available": "Available org",
            "documentation_generation": "Documentation generation",
            "exclusion_file": "Exclusion file",
            "org_check": "Org Check",
            "org_check_type": "Check type",
            "source_folder": "Source folder",
            "output_folder": "Output folder",
            "browse": "Browse",
            "open": "Open",
            "web_login": "Web login",
            "refresh": "Refresh",
            "generate_manifest": "Generate manifest",
            "retrieve": "Run retrieve",
            "full_pipeline": "Manifest + Retrieve + Docs",
            "generate_doc": "Generate documentation",
            "generate_org_check_excel": "Generate excel",
            "ready": "Ready.",
            "operation_done": "Operation completed.",
            "operation_failed": "Operation failed.",
            "success_title": "Success",
            "error_title": "Error",
            "info_title": "Information",
            "language_changed": "Language saved.",
            "source_folder_required": "The source folder is required.",
            "output_folder_required": "The output folder is required.",
            "source_folder_missing": "The source folder was not found.",
            "source_must_be_dir": "The source path must be a folder.",
            "output_must_be_dir": "The output path must be a folder.",
            "directory_missing_to_open": "The selected folder was not found.",
            "alias_required": "An alias is required for web login.",
            "select_org_manifest": "Select an org before generating the manifest.",
            "select_org_retrieve": "Select an org before running retrieve.",
            "select_org_pipeline": "Select an org before running the full pipeline.",
            "select_org_org_check": "Select an org before running an org check.",
            "org_check_choice_required": "Select an org check type.",
            "manifest_missing_title": "Manifest missing",
            "manifest_missing_message": "No manifest was found in the source folder. Do you want to generate it and then run retrieve?",
            "action_already_running": "An action is already running.",
            "choose_source_folder": "Choose source folder",
            "choose_output_folder": "Choose output folder",
            "choose_exclusion_file": "Choose configuration file",
            "loading_orgs": "Loading Salesforce orgs...",
            "org_list_refreshed": "Org list refreshed.",
            "orgs_loaded": "{count} org(s) loaded in the interface.",
            "web_login_in_progress": "Salesforce login in progress...",
            "web_login_done": "Login completed for alias `{alias}`.",
            "manifest_in_progress": "Generating manifest...",
            "manifest_done": "Manifest generated.",
            "manifest_ready": "Manifest ready: {path}",
            "retrieve_in_progress": "Salesforce retrieve in progress...",
            "retrieve_done": "Retrieve completed.",
            "manifest_retrieve_done": "Manifest generated and retrieve completed.",
            "pipeline_in_progress": "Manifest + retrieve + documentation in progress...",
            "pipeline_done": "Full pipeline completed.",
            "org_check_in_progress": "Org check generation in progress...",
            "org_check_done": "Org check completed.",
            "org_check_ready": "Org check Excel generated: {path}",
            "doc_in_progress": "Documentation generation in progress...",
            "doc_done": "Generation completed.",
            "branding_error": "Unable to load Lucie.png for branding.",
            "source_log": "Source: {path}",
            "output_log": "Output: {path}",
            "pipeline_log": "Full pipeline for org: {org}",
            "index_log": "Generated index: {path}",
            "production": "Production",
            "sandbox": "Sandbox",
            "custom": "Custom",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self.geometry("980x760")
        self.minsize(900, 620)
        self.app_dir = Path(__file__).resolve().parent
        self.settings_path = self.app_dir / "app_settings.json"
        self.settings = self._load_settings()
        self.language = self.settings.get("language", "fr")

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.exclusion_file_var = tk.StringVar(value=self.settings.get("exclusion_file", ""))
        self.alias_var = tk.StringVar()
        self.language_label_var = tk.StringVar(value=self.LANGUAGES.get(self.language, "Francais"))
        self.login_target_key = self.settings.get("login_target", "production")
        self.login_target_var = tk.StringVar()
        self.instance_url_var = tk.StringVar(value=self.settings.get("instance_url", self.LOGIN_TARGETS["production"]))
        self.selected_org_var = tk.StringVar()
        self.org_check_choice_var = tk.StringVar(value=self.ORG_CHECK_CHOICES[0])
        self.status_var = tk.StringVar(value=self._t("ready"))
        self.hero_image: tk.PhotoImage | None = None
        self.icon_image: tk.PhotoImage | None = None

        self.queue: Queue[tuple[str, object]] = Queue()
        self.worker: Thread | None = None
        self.action_buttons: list[ttk.Button] = []
        self.orgs: list[OrgSummary] = []
        self.orgs_by_label: dict[str, OrgSummary] = {}
        self.cli_service = SalesforceCliService(self.app_dir, log_callback=self._queue_log)

        self._build_ui()
        self._apply_language(initial=True)
        self._load_branding()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_queue)
        self.after(250, lambda: self._refresh_orgs(initial=True))

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

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

        self.cli_frame = ttk.LabelFrame(frame, padding=12)
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

        self.org_check_frame = ttk.LabelFrame(frame, padding=12)
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
        self.org_check_button = self._track_button(
            ttk.Button(org_check_row, command=self._run_org_check_excel)
        )
        self.org_check_button.pack(side="left")

        self.doc_frame = ttk.LabelFrame(frame, padding=12)
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

        button_row = ttk.Frame(self.doc_frame)
        button_row.pack(fill="x", pady=(8, 0))
        self.generate_button = self._track_button(ttk.Button(button_row, command=self._start_generation))
        self.generate_button.pack(side="left")
        self.status_label = ttk.Label(button_row, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=(16, 0))

        self.log_widget = scrolledtext.ScrolledText(frame, wrap="word", height=26)
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.configure(state="disabled")

    def _folder_picker(self, parent, variable: tk.StringVar, browse_command, open_command) -> dict[str, object]:
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

    def _file_picker(self, parent, variable: tk.StringVar, browse_command, open_command) -> dict[str, object]:
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

    def _load_branding(self) -> None:
        image_path = self.app_dir / "image" / "Lucie.png"
        if not image_path.exists():
            return

        try:
            self.icon_image = tk.PhotoImage(file=str(image_path))
            self.iconphoto(True, self.icon_image)

            self.hero_image = tk.PhotoImage(file=str(image_path))
            width = max(1, self.hero_image.width() // 180)
            height = max(1, self.hero_image.height() // 180)
            factor = max(width, height)
            if factor > 1:
                self.hero_image = self.hero_image.subsample(factor, factor)
            self.hero_label.configure(image=self.hero_image)
        except tk.TclError:
            self._append_log(self._t("branding_error"))

    def _load_settings(self) -> dict[str, str]:
        if not self.settings_path.exists():
            return {}
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_settings(self) -> None:
        payload = {
            "language": self.language,
            "login_target": self.login_target_key,
            "instance_url": self.instance_url_var.get().strip(),
            "exclusion_file": self.exclusion_file_var.get().strip(),
        }
        self.settings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

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
        self.login_button.configure(text=self._t("web_login"))
        self.refresh_button.configure(text=self._t("refresh"))
        self.generate_manifest_button.configure(text=self._t("generate_manifest"))
        self.retrieve_button.configure(text=self._t("retrieve"))
        self.full_pipeline_button.configure(text=self._t("full_pipeline"))
        self.org_check_button.configure(text=self._t("generate_org_check_excel"))
        self.generate_button.configure(text=self._t("generate_doc"))
        self.status_var.set(self._t("ready") if initial else self.status_var.get())

        self.language_combo["values"] = [self._language_display(code) for code in self.LANGUAGES]
        self.language_label_var.set(self._language_display(self.language))
        self.login_target_combo["values"] = [self._login_target_display(key) for key in self.LOGIN_TARGETS]
        self.login_target_var.set(self._login_target_display(self.login_target_key))
        self._on_login_target_changed()

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

        def task() -> dict[str, object]:
            manifest_path = self.cli_service.generate_manifest(selected_org.org_ref, source)
            retrieved_path = self.cli_service.retrieve_from_org(selected_org.org_ref, source, manifest_path)
            return SalesforceDocumentationGenerator(
                retrieved_path,
                output,
                exclusion_config_path=exclusion_file,
                log_callback=self._queue_log,
            ).generate()

        self._start_task(
            status_text=self._t("pipeline_in_progress"),
            task=task,
            success_message=self._t("pipeline_done"),
            on_success=lambda result: self._append_log(self._t("index_log", path=result["index"])),
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

    def _start_generation(self) -> None:
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
        self._start_task(
            status_text=self._t("doc_in_progress"),
            task=lambda: SalesforceDocumentationGenerator(
                source,
                output,
                exclusion_config_path=exclusion_file,
                log_callback=self._queue_log,
            ).generate(),
            success_message=self._t("doc_done"),
            on_success=lambda result: self._append_log(self._t("index_log", path=result["index"])),
        )

    def _start_task(
        self,
        *,
        status_text: str,
        task,
        success_message: str,
        on_success=None,
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

    def _run_task(self, task, success_message: str, on_success, notify: bool) -> None:
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


if __name__ == "__main__":
    app = Application()
    app.mainloop()
