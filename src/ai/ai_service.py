from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AIMessage:
    """Represents a single message in a chat conversation."""

    role: str  # "user" or "assistant"
    content: str


class AIProviderNotConfigured(Exception):
    """Raised when an AI provider is selected but its API key is missing."""


class AIProviderNotInstalled(Exception):
    """Raised when the Python SDK for a provider is not installed."""


class AIServiceBase:
    """Base class for AI providers."""

    name: str = "base"
    default_model: str = ""

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
    ) -> str:
        raise NotImplementedError


class ClaudeService(AIServiceBase):
    """Anthropic Claude chat service."""

    name = "Claude"
    default_model = "claude-sonnet-4-5-20250929"

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
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
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt or "You are a helpful Salesforce expert assistant.",
            messages=payload,
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
    default_model = "gemini-2.5-flash"

    def chat(
        self,
        messages: list[AIMessage],
        system_prompt: str = "",
        max_tokens: int = 4096,
    ) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(
                "Aucune cle API Gemini configuree. Ajoutez-la dans Configuration > Discussion."
            )
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime check
            raise AIProviderNotInstalled(
                "Le package 'google-generativeai' n'est pas installe. Executez: pip install google-generativeai"
            ) from exc

        if not messages or messages[-1].role != "user":
            raise ValueError("Le dernier message doit provenir de l'utilisateur.")

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt or "You are a helpful Salesforce expert assistant.",
            generation_config={"max_output_tokens": max_tokens},
        )

        history: list[dict[str, Any]] = []
        for message in messages[:-1]:
            if message.role not in ("user", "assistant"):
                continue
            if not message.content.strip():
                continue
            role = "user" if message.role == "user" else "model"
            history.append({"role": role, "parts": [message.content]})

        chat = model.start_chat(history=history)
        response = chat.send_message(messages[-1].content)
        text = getattr(response, "text", "") or ""
        return text.strip() or "(Reponse vide de Gemini)"


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
