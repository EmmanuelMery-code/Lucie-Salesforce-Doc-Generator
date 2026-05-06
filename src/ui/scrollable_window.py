"""Reusable Toplevel layout with a scrollable body and a fixed footer.

Both the scoring/Adopt-vs-Adapt editors and the threshold editor share the
same pattern: a header + tall scrollable content + always-visible action
buttons at the bottom. Centralising the layout here removes duplication
and guarantees identical scroll/footer behaviour across windows.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.application import Application


def build_scrollable_window(
    app: Application, *, title: str, geometry: str
) -> tuple[tk.Toplevel, ttk.Frame, ttk.Frame]:
    """Create a Toplevel with a scrollable body and a fixed footer.

    Returns ``(window, body, footer)``.

    * ``body`` is a frame embedded in a scrollable canvas; pack widgets
      into it as in any standard frame.
    * ``footer`` stays anchored at the bottom of the window so action
      buttons always remain visible. It is packed before the body with
      ``side="bottom"``, which guarantees the slot is reserved even when
      the body fills the rest of the window.
    """

    window = tk.Toplevel(app)
    window.title(title)
    window.geometry(geometry)
    app._configure_secondary_window(window)

    footer = ttk.Frame(window, padding=(16, 8, 16, 12))
    footer.pack(side="bottom", fill="x")

    outer = ttk.Frame(window)
    outer.pack(side="top", fill="both", expand=True)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas, padding=16)

    body.bind(
        "<Configure>",
        lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas_window = canvas.create_window((0, 0), window=body, anchor="nw")

    canvas.bind(
        "<Configure>",
        lambda event: canvas.itemconfigure(canvas_window, width=event.width),
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Bind the wheel only while the cursor is over this window so multiple
    # scrollable windows don't compete for the same global wheel events.
    def _on_wheel(event: tk.Event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_wheel(_event: tk.Event) -> None:
        canvas.bind_all("<MouseWheel>", _on_wheel)

    def _unbind_wheel(_event: tk.Event) -> None:
        canvas.unbind_all("<MouseWheel>")

    window.bind("<Enter>", _bind_wheel)
    window.bind("<Leave>", _unbind_wheel)
    window.bind("<Destroy>", _unbind_wheel)

    return window, body, footer
