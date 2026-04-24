from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable


RetryNotifier = Callable[[int, int, float], None]
"""Callback invoked when a provider has to wait before retrying.

Signature: ``(attempt, max_attempts, wait_seconds)``
"""


GEMINI_MODELS: list[str] = [
    # Google retired gemini-1.5-* and gemini-2.0-* families in March 2026.
    # Only the gemini-2.5-* family is served on the free tier now.
    # Ordered from the most generous free-tier RPM/RPD to the strictest.
    # As of April 2026 (source: ai.google.dev/gemini-api/docs/rate-limits):
    #   - gemini-2.5-flash-lite : 15 RPM / 1000 RPD / 250k TPM
    #   - gemini-2.5-flash      : 10 RPM /  500 RPD / 250k TPM
    #   - gemini-2.5-pro        :  5 RPM /  100 RPD / 250k TPM
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

CLAUDE_MODELS: list[str] = [
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
]


DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_WAIT_SECONDS = 20.0
MAX_RETRY_WAIT_SECONDS = 90.0


_RETRY_DELAY_RE = re.compile(r"retry[_\s]*delay[^0-9]*?(\d+(?:\.\d+)?)", re.IGNORECASE)
_RETRY_IN_RE = re.compile(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE)
_SECONDS_FIELD_RE = re.compile(r"seconds\s*[:=]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass(slots=True)
class AIMessage:
    """Represents a single message in a chat conversation."""

    role: str  # "user" or "assistant"
    content: str


class AIProviderNotConfigured(Exception):
    """Raised when an AI provider is selected but its API key is missing."""


class AIProviderNotInstalled(Exception):
    """Raised when the Python SDK for a provider is not installed."""


class DailyQuotaExceeded(Exception):
    """Raised when a free-tier *per-day* (RPD) quota has been spent.

    Unlike per-minute quotas, retrying after a few seconds will not help.
    The UI should surface the exception message verbatim so the user
    understands they must either wait for the daily reset, switch model,
    or switch provider.
    """


def _is_rate_limit_exception(exc: BaseException) -> bool:
    """Return True when the exception looks like a 429 / quota error.

    Supports both the legacy ``google.generativeai`` SDK (raises
    ``google.api_core.exceptions.ResourceExhausted``) and the new
    ``google.genai`` SDK (raises ``google.genai.errors.ClientError`` /
    ``APIError`` with a ``.code`` attribute equal to 429).
    """
    class_name = type(exc).__name__
    if class_name in {"ResourceExhausted", "TooManyRequests", "RateLimitError"}:
        return True
    # New google-genai SDK packs the HTTP status in `.code` on ClientError.
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code == 429:
        return True
    if class_name in {"ClientError", "APIError"} and "429" in str(exc):
        return True
    message = str(exc)
    lowered = message.lower()
    if "429" in lowered:
        return True
    if "resourceexhausted" in lowered:
        return True
    if "quota" in lowered and ("exceed" in lowered or "limit" in lowered):
        return True
    if "rate limit" in lowered:
        return True
    return False


def _is_daily_quota_exception(exc: BaseException) -> bool:
    """Return True if the 429 concerns a *per-day* (RPD) quota.

    Google differentiates quotas through the ``quota_id`` field of the error:
    - ``GenerateRequestsPerMinutePerProjectPerModel-FreeTier`` for RPM
    - ``GenerateRequestsPerDayPerProjectPerModel-FreeTier`` for RPD
    - ``GenerateContentInputTokensPerModelPerMinute-FreeTier`` for TPM
    """
    if not _is_rate_limit_exception(exc):
        return False
    lowered = str(exc).lower()
    if "perdayper" in lowered.replace("_", "").replace("-", ""):
        return True
    if "perday" in lowered.replace(" ", ""):
        return True
    if "daily" in lowered and "quota" in lowered:
        return True
    return False


def _humanize_quota_error(exc: BaseException) -> str:
    """Return a short, actionable message for the user.

    Strips the verbose protobuf-ish payload Google returns and keeps only
    what is useful to decide what to do next.
    """
    raw = str(exc)
    lowered = raw.lower()
    compact = lowered.replace("_", "").replace("-", "").replace(" ", "")

    # Order matters: TPM quota_id *also* contains "PerMinute" so we must match
    # the token-based quotas before the generic per-minute one.
    if "perdayperproject" in compact or "perday" in lowered.replace(" ", ""):
        return (
            "Quota journalier (RPD) Gemini epuise pour ce modele sur le palier "
            "gratuit. Le compteur est remis a zero a minuit heure Pacifique "
            "(~09h00 UTC). Solutions : attendre le reset, changer de modele "
            "via Configuration > Discussion, ou basculer sur Claude."
        )
    if "tokens" in lowered and ("perminute" in compact or "tpm" in lowered):
        return (
            "Quota de tokens par minute (TPM) Gemini atteint. Le contexte "
            "envoye a l'IA est trop gros pour le palier gratuit. Effacez "
            "l'historique ou reduisez la taille du prompt systeme via "
            "Configuration > Discussion."
        )
    if "perminute" in compact or "rate limit" in lowered:
        return (
            "Quota par minute (RPM) Gemini atteint. Lucie retente "
            "automatiquement apres la pause demandee par Google."
        )
    # Fallback: keep the original message (truncated) for transparency.
    truncated = raw if len(raw) < 280 else raw[:280] + "..."
    return truncated


def _extract_retry_seconds(exc: BaseException) -> float:
    """Best-effort extraction of the suggested retry delay from the error."""
    candidate: float | None = None

    retry_delay = getattr(exc, "retry_delay", None)
    if retry_delay is not None:
        seconds = getattr(retry_delay, "seconds", None)
        if isinstance(seconds, (int, float)) and seconds > 0:
            candidate = float(seconds)

    if candidate is None:
        retry_after = getattr(exc, "retry_after", None)
        if isinstance(retry_after, (int, float)) and retry_after > 0:
            candidate = float(retry_after)

    if candidate is None:
        message = str(exc)
        for regex in (_RETRY_IN_RE, _RETRY_DELAY_RE, _SECONDS_FIELD_RE):
            match = regex.search(message)
            if match:
                try:
                    value = float(match.group(1))
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    candidate = value
                    break

    if candidate is None:
        candidate = DEFAULT_RETRY_WAIT_SECONDS

    # Add a small safety margin and cap to avoid blocking the UI for minutes.
    return min(candidate + 1.0, MAX_RETRY_WAIT_SECONDS)


class AIServiceBase:
    """Base class for AI providers."""

    name: str = "base"
    default_model: str = ""
    available_models: list[str] = []

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.model = (model or self.default_model).strip() or self.default_model

    def is_ready(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        raise NotImplementedError


class ClaudeService(AIServiceBase):
    """Anthropic Claude chat service."""

    name = "Claude"
    default_model = "claude-sonnet-4-5-20250929"
    available_models = CLAUDE_MODELS

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Claude configuree. Ajoutez-la dans Configuration > Discussion."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime check
            raise AIProviderNotInstalled(
                "Le package 'anthropic' n'est pas installe. Executez: pip install anthropic"
            ) from exc

        payload: list[dict[str, Any]] = []
        for message in messages:
            if message.role not in ("user", "assistant"):
                continue
            if not message.content.strip():
                continue
            payload.append({"role": message.role, "content": message.content})
        if not payload:
            raise ValueError("Aucun message utilisateur a envoyer.")

        client = anthropic.Anthropic(api_key=self.api_key)

        def _call() -> Any:
            return client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt or "You are a helpful Salesforce expert assistant.",
                messages=payload,
            )

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )

        fragments: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                fragments.append(text)
        return "".join(fragments).strip() or "(Reponse vide de Claude)"


class GeminiService(AIServiceBase):
    """Google Gemini chat service."""

    name = "Gemini"
    # gemini-2.5-flash-lite has the most generous free-tier quota as of 2026-04
    # (15 RPM / 1000 RPD / 250k TPM).
    default_model = "gemini-2.5-flash-lite"
    available_models = GEMINI_MODELS

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
        *,
        on_retry: RetryNotifier | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Gemini configuree. Ajoutez-la dans Configuration > Discussion."
            )

        if not messages or messages[-1].role != "user":
            raise ValueError("Le dernier message doit provenir de l'utilisateur.")

        effective_system = (
            system_prompt or "You are a helpful Salesforce expert assistant."
        )
        history_messages = list(messages[:-1])
        last_prompt = messages[-1].content

        # Prefer the official google-genai SDK (new, active support).
        # Fall back to the deprecated google-generativeai only if the new
        # package is not yet installed on the user's machine, so existing
        # setups keep working while they migrate.
        try:
            from google import genai as google_genai  # type: ignore
            from google.genai import types as genai_types  # type: ignore
        except ImportError:
            return self._chat_legacy_sdk(
                history_messages=history_messages,
                last_prompt=last_prompt,
                system_prompt=effective_system,
                max_tokens=max_tokens,
                on_retry=on_retry,
                max_retries=max_retries,
            )

        client = google_genai.Client(api_key=self.api_key)
        history_payload = [
            genai_types.Content(
                role="user" if message.role == "user" else "model",
                parts=[genai_types.Part(text=message.content)],
            )
            for message in history_messages
            if message.role in ("user", "assistant") and message.content.strip()
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=effective_system,
            max_output_tokens=max_tokens,
        )

        def _call() -> Any:
            # Recreate the chat on every attempt so that a failed send_message
            # does not leave half-populated history on the next retry.
            chat = client.chats.create(
                model=self.model,
                config=config,
                history=history_payload,
            )
            return chat.send_message(last_prompt)

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )

        text = getattr(response, "text", "") or ""
        return text.strip() or "(Reponse vide de Gemini)"

    def _chat_legacy_sdk(
        self,
        *,
        history_messages: list[AIMessage],
        last_prompt: str,
        system_prompt: str,
        max_tokens: int,
        on_retry: RetryNotifier | None,
        max_retries: int,
    ) -> str:
        """Fallback path for users still on the deprecated google-generativeai.

        The new ``google-genai`` package is strongly preferred because the
        legacy one no longer receives bug fixes. If nothing is installed,
        we point users to the new package.
        """
        try:
            import google.generativeai as legacy_genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime guard
            raise AIProviderNotInstalled(
                "Aucun SDK Gemini trouve. Installez le package officiel : "
                "pip install google-genai"
            ) from exc

        legacy_genai.configure(api_key=self.api_key)
        model = legacy_genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={"max_output_tokens": max_tokens},
        )

        history: list[dict[str, Any]] = []
        for message in history_messages:
            if message.role not in ("user", "assistant"):
                continue
            if not message.content.strip():
                continue
            role = "user" if message.role == "user" else "model"
            history.append({"role": role, "parts": [message.content]})

        def _call() -> Any:
            chat = model.start_chat(history=history)
            return chat.send_message(last_prompt)

        response = _call_with_retry(
            _call,
            provider_label=self.name,
            on_retry=on_retry,
            max_retries=max_retries,
        )
        text = getattr(response, "text", "") or ""
        return text.strip() or "(Reponse vide de Gemini)"


def _call_with_retry(
    callable_: Callable[[], Any],
    *,
    provider_label: str,
    on_retry: RetryNotifier | None,
    max_retries: int,
) -> Any:
    """Invoke ``callable_`` and retry on rate-limit style errors.

    The retry delay is derived from the server's hint (``retry_delay``
    / ``retry_after`` / "retry in Ns") and capped by
    :data:`MAX_RETRY_WAIT_SECONDS`.
    """
    attempts = max(1, int(max_retries))
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return callable_()
        except Exception as exc:  # noqa: BLE001 - we classify below
            last_exc = exc
            if not _is_rate_limit_exception(exc):
                raise
            if _is_daily_quota_exception(exc):
                # RPD quotas will not recover within the retry window; stop now
                # and surface a clear, localisable message to the UI.
                raise DailyQuotaExceeded(_humanize_quota_error(exc)) from exc
            if attempt >= attempts:
                break
            wait_seconds = _extract_retry_seconds(exc)
            if on_retry is not None:
                try:
                    on_retry(attempt, attempts, wait_seconds)
                except Exception:  # pragma: no cover - callback is best-effort
                    pass
            _ = provider_label  # kept for future structured logging
            time.sleep(wait_seconds)
    # Exhausted all retries: re-raise the last quota error so the UI shows it.
    assert last_exc is not None
    raise last_exc


def create_service(provider: str, settings: dict[str, Any]) -> AIServiceBase:
    """Build the correct AI service for the selected provider."""
    provider_norm = (provider or "").strip().lower()
    if provider_norm == "claude":
        return ClaudeService(
            api_key=str(settings.get("claude_api_key", "") or ""),
            model=str(settings.get("claude_model", "") or "") or None,
        )
    if provider_norm == "gemini":
        return GeminiService(
            api_key=str(settings.get("gemini_api_key", "") or ""),
            model=str(settings.get("gemini_model", "") or "") or None,
        )
    raise ValueError(f"Fournisseur IA inconnu : {provider}")
