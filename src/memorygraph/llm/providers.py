"""LLM provider factories — LLM-agnostic, injectable via LLMCallable."""
from __future__ import annotations

import os

from memorygraph.agent.extractor import LLMCallable

_PROVIDER_ENV = "MEMORYGRAPH_LLM_PROVIDER"
_ANTHROPIC_KEY_ENV = "ANTHROPIC_API_KEY"
_OPENAI_KEY_ENV = "OPENAI_API_KEY"

_DEFAULT_ANTHROPIC_MODEL = os.getenv("MEMORYGRAPH_ANTHROPIC_MODEL", "claude-sonnet-4-6")
_DEFAULT_OPENAI_MODEL = os.getenv("MEMORYGRAPH_OPENAI_MODEL", "gpt-4o-mini")


def _make_anthropic_llm() -> LLMCallable:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic non installato. Esegui: uv add anthropic"
        ) from e

    client = anthropic.Anthropic(api_key=os.environ[_ANTHROPIC_KEY_ENV])

    def call(prompt: str) -> str:
        message = client.messages.create(
            model=_DEFAULT_ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    return call


def _make_openai_llm() -> LLMCallable:
    try:
        import openai
    except ImportError as e:
        raise RuntimeError(
            "openai non installato. Esegui: uv add openai"
        ) from e

    client = openai.OpenAI(api_key=os.environ[_OPENAI_KEY_ENV])

    def call(prompt: str) -> str:
        response = client.chat.completions.create(
            model=_DEFAULT_OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    return call


def _make_demo_llm() -> LLMCallable:
    def demo(prompt: str) -> str:
        if "NodeType validi" in prompt:
            return (
                '{"nodes": [{"type": "Observation", '
                '"content": "Testo inserito tramite CLI (demo LLM)", '
                '"confidence": 0.5, '
                '"trigger": "Inserito via agent-extract"}]}'
            )
        return '{"contradiction": false, "node_id": null, "reason": null}'

    return demo


def make_llm() -> LLMCallable:
    """Seleziona il provider LLM dalla configurazione ambiente.

    Priorità:
    1. MEMORYGRAPH_LLM_PROVIDER=anthropic|openai  (esplicito)
    2. ANTHROPIC_API_KEY presente → anthropic
    3. OPENAI_API_KEY presente → openai
    4. Nessuna chiave → demo (stub)
    """
    explicit = os.getenv(_PROVIDER_ENV, "").lower().strip()
    if explicit == "anthropic":
        return _make_anthropic_llm()
    if explicit == "openai":
        return _make_openai_llm()

    if os.getenv(_ANTHROPIC_KEY_ENV):
        return _make_anthropic_llm()
    if os.getenv(_OPENAI_KEY_ENV):
        return _make_openai_llm()

    return _make_demo_llm()
