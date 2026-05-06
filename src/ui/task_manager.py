"""Task management and background execution for the Salesforce documentation generator."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.ui.application import Application


class TaskManager:
    """Handles background thread execution and UI queue polling."""

    def __init__(self, app: Application) -> None:
        self.app = app
        self.queue: Queue[tuple[str, Any]] = Queue()
        self.worker: Thread | None = None

    def start_task(
        self,
        *,
        status_text: str,
        task: Callable[[], Any],
        success_message: str,
        on_success: Callable[[Any], None] | None = None,
        notify: bool = True,
    ) -> None:
        """Launch a background task in a dedicated thread."""
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(self.app._t("info_title"), self.app._t("action_already_running"))
            return

        self.app.status_var.set(status_text)
        self.app._set_buttons_state(False)
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
        """Internal thread target that executes the task and puts results in the queue."""
        try:
            result = task()
            self.queue.put(("done", (success_message, result, on_success, notify)))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def queue_log(self, message: str) -> None:
        """Thread-safe way to append a message to the UI log."""
        self.queue.put(("log", message))

    def poll_queue(self) -> None:
        """Periodically check the queue for background task results."""
        try:
            while True:
                event_type, payload = self.queue.get_nowait()
                if event_type == "log":
                    self.app._append_log(str(payload))
                elif event_type == "done":
                    success_message, result, on_success, notify = payload
                    if on_success is not None:
                        on_success(result)
                    self.app._append_log(success_message)
                    self.app.status_var.set(self.app._t("operation_done"))
                    self.app._set_buttons_state(True)
                    if notify:
                        messagebox.showinfo(self.app._t("success_title"), success_message)
                elif event_type == "error":
                    self.app._append_log(f"Erreur: {payload}")
                    self.app.status_var.set(self.app._t("operation_failed"))
                    self.app._set_buttons_state(True)
                    messagebox.showerror(self.app._t("error_title"), str(payload))
                elif event_type == "discussion_reply":
                    self.app._handle_discussion_reply(payload)
                elif event_type == "discussion_error":
                    self.app._handle_discussion_error(str(payload))
                elif event_type == "discussion_info":
                    if isinstance(payload, dict):
                        self.app._handle_discussion_info(payload)
        except Empty:
            pass
        # Reschedule polling
        self.app.after(150, self.poll_queue)
