"""Configuration tab managing the list of AI usage tags.

The "Tag : IA" tab lets the user add, edit, remove or reset the tags that
:func:`src.core.ai_usage.scan_ai_usage` looks for in metadata
descriptions and Apex comments. Persistence is delegated to
:meth:`src.ui.application.Application._save_settings` via the
``ai_usage_tags`` attribute on the app instance.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from src.ui.settings import DEFAULT_AI_USAGE_TAGS

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: "Application", parent: ttk.Frame) -> None:
    """Render the AI tags tab into ``parent``.

    Stores widget handles on the ``app`` instance so the surrounding
    configuration screen can read the edited list back when the user
    presses *Save*.
    """

    title = ttk.Label(
        parent,
        text=app._t("configuration_ai_tags_title"),
        font=("Segoe UI", 12, "bold"),
    )
    title.pack(anchor="w", pady=(0, 4))

    description = ttk.Label(
        parent,
        text=app._t("configuration_ai_tags_description"),
        wraplength=820,
        justify="left",
    )
    description.pack(anchor="w", pady=(0, 10))

    list_frame = ttk.Frame(parent)
    list_frame.pack(fill="both", expand=True)

    listbox = tk.Listbox(list_frame, height=10, exportselection=False)
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.configure(yscrollcommand=scrollbar.set)

    for tag in app.ai_usage_tags:
        listbox.insert(tk.END, tag)

    button_row = ttk.Frame(parent)
    button_row.pack(fill="x", pady=(8, 0))

    ttk.Button(
        button_row,
        text=app._t("configuration_ai_tags_add"),
        command=lambda: _add_tag(app, listbox),
    ).pack(side="left")
    ttk.Button(
        button_row,
        text=app._t("configuration_ai_tags_edit"),
        command=lambda: _edit_tag(app, listbox),
    ).pack(side="left", padx=(8, 0))
    ttk.Button(
        button_row,
        text=app._t("configuration_ai_tags_remove"),
        command=lambda: _remove_tag(app, listbox),
    ).pack(side="left", padx=(8, 0))
    ttk.Button(
        button_row,
        text=app._t("configuration_ai_tags_reset"),
        command=lambda: _reset_tags(app, listbox),
    ).pack(side="right")

    hint = ttk.Label(
        parent,
        text=app._t("configuration_ai_tags_hint"),
        wraplength=820,
        justify="left",
        foreground="#475569",
    )
    hint.pack(anchor="w", pady=(8, 0))

    app._ai_tags_listbox = listbox


def collect_tags(app: "Application") -> list[str]:
    """Return the tag list currently displayed in the configuration tab.

    Falls back to ``app.ai_usage_tags`` when the panel was not built (the
    user can theoretically save the configuration screen without ever
    opening the tab, although the tab is always created when the screen
    opens).
    """

    listbox = getattr(app, "_ai_tags_listbox", None)
    if listbox is None:
        return list(app.ai_usage_tags)
    return _read_listbox(listbox)


def reset_state(app: "Application") -> None:
    """Drop widget references after the configuration window closes."""

    app._ai_tags_listbox = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_listbox(listbox: tk.Listbox) -> list[str]:
    return [str(listbox.get(index)).strip() for index in range(listbox.size())]


def _ask_tag(
    app: "Application", title: str, initial: str = ""
) -> str | None:
    """Prompt the user for a tag value.

    Returns the cleaned value, or ``None`` when the user cancelled or the
    input was empty after stripping. ``simpledialog`` is centred on the
    configuration window so it stays close to the user's focus.
    """

    parent: tk.Misc = app.configuration_window or app
    value = simpledialog.askstring(
        title,
        app._t("configuration_ai_tags_prompt"),
        initialvalue=initial,
        parent=parent,
    )
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned


def _add_tag(app: "Application", listbox: tk.Listbox) -> None:
    new_value = _ask_tag(app, app._t("configuration_ai_tags_add"))
    if new_value is None:
        return
    existing = {item.casefold() for item in _read_listbox(listbox)}
    if new_value.casefold() in existing:
        messagebox.showwarning(
            app._t("info_title"),
            app._t("configuration_ai_tags_duplicate"),
            parent=app.configuration_window or app,
        )
        return
    listbox.insert(tk.END, new_value)
    listbox.selection_clear(0, tk.END)
    listbox.selection_set(tk.END)


def _edit_tag(app: "Application", listbox: tk.Listbox) -> None:
    selection = listbox.curselection()
    if not selection:
        messagebox.showinfo(
            app._t("info_title"),
            app._t("configuration_ai_tags_select_first"),
            parent=app.configuration_window or app,
        )
        return
    index = selection[0]
    current_value = str(listbox.get(index))
    new_value = _ask_tag(
        app, app._t("configuration_ai_tags_edit"), initial=current_value
    )
    if new_value is None:
        return
    others = {
        item.casefold()
        for position, item in enumerate(_read_listbox(listbox))
        if position != index
    }
    if new_value.casefold() in others:
        messagebox.showwarning(
            app._t("info_title"),
            app._t("configuration_ai_tags_duplicate"),
            parent=app.configuration_window or app,
        )
        return
    listbox.delete(index)
    listbox.insert(index, new_value)
    listbox.selection_clear(0, tk.END)
    listbox.selection_set(index)


def _remove_tag(app: "Application", listbox: tk.Listbox) -> None:
    selection = listbox.curselection()
    if not selection:
        messagebox.showinfo(
            app._t("info_title"),
            app._t("configuration_ai_tags_select_first"),
            parent=app.configuration_window or app,
        )
        return
    for index in reversed(selection):
        listbox.delete(index)


def _reset_tags(app: "Application", listbox: tk.Listbox) -> None:
    listbox.delete(0, tk.END)
    for tag in DEFAULT_AI_USAGE_TAGS:
        listbox.insert(tk.END, tag)
