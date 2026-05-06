"""Panel for Salesforce CLI operations (login, org list, retrieve)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: Application, parent: ttk.Frame) -> None:
    """Build the Salesforce CLI interaction panel."""
    app.cli_frame = ttk.LabelFrame(parent, padding=12)
    app.cli_frame.pack(fill="x", pady=(0, 12))

    login_row = ttk.Frame(app.cli_frame)
    login_row.pack(fill="x", pady=(0, 8))
    app.alias_label = ttk.Label(login_row, width=14)
    app.alias_label.pack(side="left")
    ttk.Entry(login_row, textvariable=app.alias_var, width=24).pack(side="left", padx=(0, 12))
    app.environment_label = ttk.Label(login_row, width=14)
    app.environment_label.pack(side="left")
    app.login_target_combo = ttk.Combobox(
        login_row,
        textvariable=app.login_target_var,
        state="readonly",
        width=14,
    )
    app.login_target_combo.pack(side="left", padx=(0, 12))
    app.login_target_combo.bind("<<ComboboxSelected>>", app._on_login_target_changed)
    app.instance_url_label = ttk.Label(login_row, width=14)
    app.instance_url_label.pack(side="left")
    app.instance_url_entry = ttk.Entry(login_row, textvariable=app.instance_url_var)
    app.instance_url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    app.login_button = app._track_button(ttk.Button(login_row, command=app._login_web))
    app.login_button.pack(side="left")

    org_row = ttk.Frame(app.cli_frame)
    org_row.pack(fill="x")
    app.org_available_label = ttk.Label(org_row, width=14)
    app.org_available_label.pack(side="left")
    app.org_combo = ttk.Combobox(
        org_row,
        textvariable=app.selected_org_var,
        state="readonly",
    )
    app.org_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
    app.org_combo.bind("<<ComboboxSelected>>", app._on_org_selected)
    app.refresh_button = app._track_button(ttk.Button(org_row, command=app._refresh_orgs))
    app.refresh_button.pack(side="left", padx=(0, 8))
    app.generate_manifest_button = app._track_button(ttk.Button(org_row, command=app._generate_manifest))
    app.generate_manifest_button.pack(side="left", padx=(0, 8))
    app.retrieve_button = app._track_button(ttk.Button(org_row, command=app._retrieve_from_selected_org))
    app.retrieve_button.pack(side="left", padx=(0, 8))
    
    app.delete_button = app._track_button(ttk.Button(org_row, command=app._delete))
    app.delete_button.pack(side="left", padx=(0, 8))
    
    app.full_pipeline_button = app._track_button(ttk.Button(org_row, command=app._run_full_pipeline))
    app.full_pipeline_button.pack(side="left")
