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
    # Button placed at the end of the provider row so the user can
    # explicitly tell the assistant to rely on the documentation that
    # already lives in the output folder, ignoring the in-memory
    # snapshot if any.
    app.discussion_force_docs_button = app._track_button(
        ttk.Button(
            provider_row,
            command=lambda: toggle_force_existing_docs(app),
        )
    )
    app.discussion_force_docs_button.pack(side="left", padx=(16, 0))

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
    # Yellow background highlight applied transiently by the
    # previous/next navigation buttons. Configured with high priority so
    # it visually wins over the per-role styling above.
    history.tag_configure("question_active", background="#fde68a")
    history.tag_raise("question_active")
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

    # Navigation + copy bar shown right below the input field.
    nav_row = ttk.Frame(container)
    nav_row.pack(fill="x", pady=(6, 0))
    # Empty cell aligned with the 'Votre message' label so buttons
    # line up under the entry rather than under the label.
    ttk.Label(nav_row, width=18).pack(side="left")
    app.discussion_prev_button = app._track_button(
        ttk.Button(nav_row, command=lambda: go_previous(app))
    )
    app.discussion_prev_button.pack(side="left")
    app.discussion_next_button = app._track_button(
        ttk.Button(nav_row, command=lambda: go_next(app))
    )
    app.discussion_next_button.pack(side="left", padx=(8, 0))
    app.discussion_copy_last_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_last_question(app))
    )
    app.discussion_copy_last_button.pack(side="left", padx=(16, 0))
    app.discussion_copy_current_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_current_question(app))
    )
    app.discussion_copy_current_button.pack(side="left", padx=(8, 0))
    app.discussion_copy_all_button = app._track_button(
        ttk.Button(nav_row, command=lambda: copy_discussion(app))
    )
    app.discussion_copy_all_button.pack(side="left", padx=(8, 0))

    update_navigation_state(app)


def _user_questions(app: Application) -> list[str]:
    """Return the list of user-authored questions, in chronological order."""

    return [m.content for m in app.discussion_messages if m.role == "user"]


def update_navigation_state(app: Application) -> None:
    """Enable/disable the navigation and copy buttons based on history."""

    if not hasattr(app, "discussion_prev_button"):
        return

    questions = _user_questions(app)
    has_questions = bool(questions)
    has_messages = bool(app.discussion_messages)
    index = app.discussion_question_index

    can_prev = has_questions and (index is None or index > 0)
    can_next = has_questions and index is not None and index < len(questions) - 1

    app.discussion_prev_button.configure(state="normal" if can_prev else "disabled")
    app.discussion_next_button.configure(state="normal" if can_next else "disabled")
    app.discussion_copy_last_button.configure(
        state="normal" if has_questions else "disabled"
    )
    app.discussion_copy_current_button.configure(
        state="normal" if (has_questions and index is not None) else "disabled"
    )
    app.discussion_copy_all_button.configure(
        state="normal" if has_messages else "disabled"
    )


def _focus_question(app: Application, index: int) -> None:
    """Scroll the history widget to question ``index`` and highlight it."""

    ranges = getattr(app, "discussion_question_ranges", [])
    if index < 0 or index >= len(ranges):
        return
    start, end = ranges[index]
    widget = app.discussion_history_widget
    widget.tag_remove("question_active", "1.0", "end")
    widget.tag_add("question_active", start, end)
    # ``see`` ensures the line is visible; pointing first at ``end``
    # then at ``start`` keeps the question header at the top of the
    # viewport when it is taller than the visible area.
    widget.see(end)
    widget.see(start)


def go_previous(app: Application) -> None:
    questions = _user_questions(app)
    if not questions:
        return
    if app.discussion_question_index is None:
        app.discussion_question_index = len(questions) - 1
    elif app.discussion_question_index > 0:
        app.discussion_question_index -= 1
    else:
        return
    _focus_question(app, app.discussion_question_index)
    update_navigation_state(app)


def go_next(app: Application) -> None:
    questions = _user_questions(app)
    if not questions or app.discussion_question_index is None:
        return
    if app.discussion_question_index < len(questions) - 1:
        app.discussion_question_index += 1
        _focus_question(app, app.discussion_question_index)
    update_navigation_state(app)


def _set_clipboard(app: Application, text: str) -> bool:
    """Push ``text`` into the system clipboard via Tk."""

    if not text:
        return False
    try:
        app.clipboard_clear()
        app.clipboard_append(text)
        app.update_idletasks()
    except tk.TclError:
        return False
    return True


def _question_with_answer(
    app: Application, user_index: int
) -> tuple[str, str | None]:
    """Return ``(question, answer_or_None)`` for the ``user_index``-th question.

    ``user_index`` is counted in the filtered list of user messages
    (same convention as ``discussion_question_index``). The associated
    answer is the first ``assistant`` message that follows the matching
    user message in ``discussion_messages``; ``None`` when the request
    is still pending or has failed.
    """

    seen = -1
    user_position: int | None = None
    for position, message in enumerate(app.discussion_messages):
        if message.role != "user":
            continue
        seen += 1
        if seen == user_index:
            user_position = position
            break
    if user_position is None:
        return "", None
    question = app.discussion_messages[user_position].content
    answer: str | None = None
    for follower in app.discussion_messages[user_position + 1 :]:
        if follower.role == "assistant":
            answer = follower.content
            break
        if follower.role == "user":
            break
    return question, answer


def _format_qa_clipboard(app: Application, question: str, answer: str | None) -> str:
    """Render the clipboard text for a question (and optional answer)."""

    user_label = app._t("discussion_role_user")
    blocks = [f"{user_label}: {question}"]
    if answer:
        assistant_label = app._t("discussion_role_assistant")
        blocks.append(f"{assistant_label}: {answer}")
    return "\n\n".join(blocks)


def copy_last_question(app: Application) -> None:
    questions = _user_questions(app)
    if not questions:
        return
    last_index = len(questions) - 1
    question, answer = _question_with_answer(app, last_index)
    if not _set_clipboard(app, _format_qa_clipboard(app, question, answer)):
        return
    key = (
        "discussion_copy_last_with_answer_done"
        if answer
        else "discussion_copy_last_no_answer_done"
    )
    append_line(app, app._t(key))


def copy_current_question(app: Application) -> None:
    questions = _user_questions(app)
    index = app.discussion_question_index
    if not questions or index is None or not 0 <= index < len(questions):
        return
    question, answer = _question_with_answer(app, index)
    if not _set_clipboard(app, _format_qa_clipboard(app, question, answer)):
        return
    key = (
        "discussion_copy_current_with_answer_done"
        if answer
        else "discussion_copy_current_no_answer_done"
    )
    append_line(app, app._t(key, index=index + 1))


def copy_discussion(app: Application) -> None:
    if not app.discussion_messages:
        return
    role_labels = {
        "user": app._t("discussion_role_user"),
        "assistant": app._t("discussion_role_assistant"),
        "system": app._t("discussion_role_system"),
    }
    blocks: list[str] = []
    for message in app.discussion_messages:
        prefix = role_labels.get(message.role, message.role)
        blocks.append(f"{prefix}: {message.content}")
    if _set_clipboard(app, "\n\n".join(blocks)):
        append_line(app, app._t("discussion_copy_all_done"))


def append_line(app: Application, text: str, tag: str = "system") -> None:
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.insert("end", text + "\n", tag)
    widget.see("end")
    widget.configure(state="disabled")


def _append_user_question(app: Application, message: str) -> None:
    """Append a user question to the history and remember its Tk range.

    The recorded ``(start, end)`` pair is later used by the previous /
    next navigation buttons to scroll back to the right line and
    highlight it inside the history widget.
    """

    widget = app.discussion_history_widget
    widget.configure(state="normal")
    start_idx = widget.index("end-1c")
    widget.insert("end", f"> {message}\n", "user")
    end_idx = widget.index("end-1c")
    widget.see("end")
    widget.configure(state="disabled")
    app.discussion_question_ranges.append((start_idx, end_idx))


def _rollback_failed_user_message(app: Application) -> None:
    """Undo a user message that could not be sent (e.g. missing key).

    Pops the message from the conversation list, drops its companion
    range so the navigation history stays in sync, and refreshes the
    button states. The text already inserted in the widget is kept on
    purpose so the user still sees what they tried to send.
    """

    if app.discussion_messages and app.discussion_messages[-1].role == "user":
        app.discussion_messages.pop()
    if app.discussion_question_ranges:
        app.discussion_question_ranges.pop()
    update_navigation_state(app)


def clear_history(app: Application) -> None:
    app.discussion_messages = []
    app.discussion_question_index = None
    app.discussion_question_ranges = []
    widget = app.discussion_history_widget
    widget.configure(state="normal")
    widget.tag_remove("question_active", "1.0", "end")
    widget.delete("1.0", "end")
    widget.configure(state="disabled")
    append_line(app, app._t("discussion_cleared"))
    update_navigation_state(app)


def update_context_status(app: Application) -> None:
    if not hasattr(app, "discussion_context_status_var"):
        return
    if getattr(app, "discussion_force_existing_docs", False):
        app.discussion_context_status_var.set(app._t("discussion_context_forced"))
        return
    if app.latest_snapshot is None:
        app.discussion_context_status_var.set(app._t("discussion_context_empty"))
    else:
        app.discussion_context_status_var.set(app._t("discussion_context_ready"))


def _has_generated_documentation(directory: str | None) -> bool:
    """Return True when ``directory`` looks like a Lucie documentation folder."""

    if not directory:
        return False
    from pathlib import Path  # local import keeps the panel light at import time

    try:
        path = Path(directory).expanduser()
    except (OSError, RuntimeError, ValueError):
        return False
    if not path.is_dir():
        return False
    if (path / "index.html").is_file():
        return True
    return any((path / sub).is_dir() for sub in ("objects", "apex", "flows", "omni"))


def toggle_force_existing_docs(app: Application) -> None:
    """Toggle the 'use existing documentation only' mode.

    When activated, :func:`send_message` passes ``snapshot=None`` to
    :func:`build_org_context`, which forces the assistant to walk through
    the documentation folder (and source folder) directly instead of
    relying on the in-memory analysis snapshot.

    Refuses to enable the mode when the configured output folder does
    not contain a generated documentation, so the user gets a clear
    error message instead of a silently broken context.
    """

    output_dir = app.output_var.get().strip()

    if not app.discussion_force_existing_docs:
        if not _has_generated_documentation(output_dir):
            append_line(
                app, app._t("discussion_force_docs_no_dir"), tag="error"
            )
            return
        app.discussion_force_existing_docs = True
        append_line(
            app,
            app._t("discussion_force_docs_enabled", path=output_dir),
            tag="system",
        )
    else:
        app.discussion_force_existing_docs = False
        append_line(app, app._t("discussion_force_docs_disabled"), tag="system")

    if hasattr(app, "discussion_force_docs_button"):
        app.discussion_force_docs_button.configure(
            text=app._t(
                "discussion_force_docs_active"
                if app.discussion_force_existing_docs
                else "discussion_force_docs"
            )
        )
    update_context_status(app)


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

    _append_user_question(app, message)
    app.discussion_input_var.set("")
    app.discussion_messages.append(AIMessage(role="user", content=message))
    app.discussion_question_index = None
    update_navigation_state(app)

    key_var = app.claude_api_key_var if provider == "Claude" else app.gemini_api_key_var
    if not key_var.get().strip():
        append_line(
            app,
            app._t("discussion_not_configured", provider=provider),
            tag="error",
        )
        _rollback_failed_user_message(app)
        return

    system_prompt = app.system_prompt or build_system_prompt(app.language)
    snapshot_for_context = (
        None
        if getattr(app, "discussion_force_existing_docs", False)
        else app.latest_snapshot
    )
    context = build_org_context(
        snapshot_for_context,
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
        _rollback_failed_user_message(app)
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
    update_navigation_state(app)


def handle_error(app: Application, message: str) -> None:
    app.discussion_pending = False
    app.discussion_send_button.configure(state="normal")
    _rollback_failed_user_message(app)
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
