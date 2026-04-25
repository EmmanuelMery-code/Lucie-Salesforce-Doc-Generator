"""Discussion / chat tab.

Encapsulates the conversational UI used to talk to the configured AI
provider. Keeping this in its own module keeps :class:`Application` focused
on orchestration rather than chat plumbing.
"""

from __future__ import annotations

import time
import tkinter as tk
from threading import Thread
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.ai import (
    AIMessage,
    AIProviderNotConfigured,
    AIProviderNotInstalled,
    DailyQuotaExceeded,
    build_org_context,
    build_system_prompt,
    create_service,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def build_panel(app: Application, parent: ttk.Frame) -> None:
    """Render the discussion tab into ``parent``."""

    container = ttk.Frame(parent, padding=12)
    container.pack(fill="both", expand=True)

    app.discussion_title_label = ttk.Label(container, font=("Segoe UI", 13, "bold"))
    app.discussion_title_label.pack(anchor="w")
    app.discussion_description_label = ttk.Label(
        container, wraplength=700, justify="left"
    )
    app.discussion_description_label.pack(anchor="w", pady=(4, 8))

    provider_row = ttk.Frame(container)
    provider_row.pack(fill="x", pady=(0, 8))
    app.discussion_provider_label = ttk.Label(provider_row, width=18)
    app.discussion_provider_label.pack(side="left")
    app.discussion_provider_value = ttk.Label(
        provider_row, textvariable=app.ai_provider_var, font=("Segoe UI", 10, "bold")
    )
    app.discussion_provider_value.pack(side="left")

    app.discussion_context_status_var = tk.StringVar(
        value=app._t("discussion_context_empty")
    )
    app.discussion_context_label = ttk.Label(
        provider_row,
        textvariable=app.discussion_context_status_var,
        foreground="#6b7280",
    )
    app.discussion_context_label.pack(side="left", padx=(16, 0))

    app.discussion_history_label = ttk.Label(container)
    app.discussion_history_label.pack(anchor="w")
    history = scrolledtext.ScrolledText(container, wrap="word", height=14)
    history.pack(fill="both", expand=True, pady=(2, 8))
    history.configure(state="disabled")
    history.tag_configure("user", foreground="#1d4ed8", font=("Segoe UI", 10, "bold"))
    history.tag_configure("assistant", foreground="#047857")
    history.tag_configure(
        "system", foreground="#6b7280", font=("Segoe UI", 9, "italic")
    )
    history.tag_configure("error", foreground="#b91c1c")
    app.discussion_history_widget = history

    input_row = ttk.Frame(container)
    input_row.pack(fill="x")
    app.discussion_input_label = ttk.Label(input_row, width=18)
    app.discussion_input_label.pack(side="left")
    app.discussion_input_var = tk.StringVar()
    app.discussion_input_entry = ttk.Entry(input_row, textvariable=app.discussion_input_var)
    app.discussion_input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    app.discussion_input_entry.bind(
        "<Return>", lambda _event: send_message(app)
    )
    app.discussion_send_button = app._track_button(
        ttk.Button(input_row, command=lambda: send_message(app))
    )
    app.discussion_send_button.pack(side="left")
    app.discussion_clear_button = app._track_button(
        ttk.Button(input_row, command=lambda: clear_history(app))
    )
    app.discussion_clear_button.pack(side="left", padx=(8, 0))


def append_line(app: Application, text: str, tag: str = "system") -> None:
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.insert("end", text + "\n", tag)
    widget.see("end")
    widget.configure(state="disabled")


def clear_history(app: Application) -> None:
    app.discussion_messages = []
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.configure(state="disabled")
    append_line(app, app._t("discussion_cleared"))


def update_context_status(app: Application) -> None:
    if not hasattr(app, "discussion_context_status_var"):
        return
    if app.latest_snapshot is None:
        app.discussion_context_status_var.set(app._t("discussion_context_empty"))
    else:
        app.discussion_context_status_var.set(app._t("discussion_context_ready"))


def send_message(app: Application) -> None:
    if app.discussion_pending:
        append_line(app, app._t("discussion_busy"), tag="error")
        return

    now = time.monotonic()
    gap = now - app._discussion_last_send_ts
    if app._discussion_last_send_ts and gap < app.DISCUSSION_MIN_INTERVAL_SECONDS:
        wait = app.DISCUSSION_MIN_INTERVAL_SECONDS - gap
        append_line(
            app,
            app._t("discussion_throttle_wait", seconds=int(round(wait)) or 1),
            tag="system",
        )
        return

    message = app.discussion_input_var.get().strip()
    if not message:
        return
    provider = app.ai_provider_var.get().strip() or app.AI_PROVIDERS[0]

    append_line(app, f"> {message}", tag="user")
    app.discussion_input_var.set("")
    app.discussion_messages.append(AIMessage(role="user", content=message))

    key_var = app.claude_api_key_var if provider == "Claude" else app.gemini_api_key_var
    if not key_var.get().strip():
        append_line(
            app,
            app._t("discussion_not_configured", provider=provider),
            tag="error",
        )
        app.discussion_messages.pop()
        return

    system_prompt = app.system_prompt or build_system_prompt(app.language)
    context = build_org_context(
        app.latest_snapshot,
        source_dir=app.source_var.get().strip() or None,
        documentation_dir=app.output_var.get().strip() or None,
    )
    full_system = f"{system_prompt}\n\n{context}"

    settings_for_service = {
        "claude_api_key": app.claude_api_key_var.get(),
        "gemini_api_key": app.gemini_api_key_var.get(),
        "claude_model": app.claude_model_var.get().strip() or app.DEFAULT_CLAUDE_MODEL,
        "gemini_model": app.gemini_model_var.get().strip() or app.DEFAULT_GEMINI_MODEL,
    }

    try:
        service = create_service(provider, settings_for_service)
    except ValueError as exc:
        append_line(app, str(exc), tag="error")
        app.discussion_messages.pop()
        return

    messages_snapshot = list(app.discussion_messages)
    app.discussion_pending = True
    app._discussion_last_send_ts = time.monotonic()
    app.discussion_send_button.configure(state="disabled")
    append_line(
        app, app._t("discussion_thinking", provider=provider), tag="system"
    )

    queue = app.queue

    def on_retry(attempt: int, max_attempts: int, wait_seconds: float) -> None:
        queue.put(
            (
                "discussion_info",
                {
                    "provider": provider,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "seconds": int(round(wait_seconds)),
                    "kind": "rate_limit",
                },
            )
        )

    def worker() -> None:
        try:
            reply = service.chat(
                messages_snapshot,
                system_prompt=full_system,
                on_retry=on_retry,
            )
            queue.put(("discussion_reply", {"provider": provider, "reply": reply}))
        except (AIProviderNotConfigured, AIProviderNotInstalled) as exc:
            queue.put(("discussion_error", str(exc)))
        except DailyQuotaExceeded as exc:
            queue.put(("discussion_error", str(exc)))
        except Exception as exc:  # pragma: no cover - network failures
            queue.put(("discussion_error", f"{type(exc).__name__}: {exc}"))

    app.discussion_worker = Thread(target=worker, daemon=True)
    app.discussion_worker.start()


def handle_reply(app: Application, payload: dict[str, str]) -> None:
    reply = payload.get("reply", "")
    provider = payload.get("provider", "")
    app.discussion_pending = False
    app.discussion_send_button.configure(state="normal")
    if reply:
        app.discussion_messages.append(AIMessage(role="assistant", content=reply))
        append_line(app, f"[{provider}] {reply}", tag="assistant")
    else:
        append_line(app, app._t("discussion_empty_reply"), tag="error")


def handle_error(app: Application, message: str) -> None:
    app.discussion_pending = False
    app.discussion_send_button.configure(state="normal")
    if app.discussion_messages and app.discussion_messages[-1].role == "user":
        app.discussion_messages.pop()
    append_line(app, app._t("discussion_error", error=message), tag="error")


def handle_info(app: Application, payload: dict[str, object]) -> None:
    kind = str(payload.get("kind", ""))
    if kind == "rate_limit":
        append_line(
            app,
            app._t(
                "discussion_rate_limit_wait",
                provider=str(payload.get("provider", "")),
                seconds=int(payload.get("seconds", 0) or 0),
                attempt=int(payload.get("attempt", 0) or 0),
                max_attempts=int(payload.get("max_attempts", 0) or 0),
            ),
            tag="system",
        )
