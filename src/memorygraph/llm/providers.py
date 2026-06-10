# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LLM provider factories — LLM-agnostic, injectable via LLMCallable."""
from __future__ import annotations

import json
import os
import re

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
            "anthropic is not installed. Run: uv add anthropic"
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
            "openai is not installed. Run: uv add openai"
        ) from e

    client = openai.OpenAI(api_key=os.environ[_OPENAI_KEY_ENV])

    def call(prompt: str) -> str:
        response = client.chat.completions.create(
            model=_DEFAULT_OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    return call


_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Extraction fixtures: (substring recognized in the text) → candidate nodes.
# Deterministically reproduces the SARS-CoV-2 scenario from demo/memorygraph-video-script.md.
_DEMO_EXTRACTIONS: list[tuple[str, list[dict]]] = [
    ("Lan et al", [
        {"type": "Observation",
         "content": "The spike RBD domain binds ACE2 with 10-20x higher affinity than SARS-CoV-1, with 17 contact residues at the interface.",
         "confidence": 0.90, "trigger": "Lan et al. 2020 (Nature), crystal structure"},
    ]),
    ("histidine 34", [
        {"type": "Hypothesis",
         "content": "Protonation of ACE2 histidine 34 in the acidic endosome (pH 5.5-6.0) may reduce spike binding affinity, impairing viral entry.",
         "confidence": 0.60, "trigger": "Structural reasoning"},
        {"type": "OpenQuestion",
         "content": "Does this mechanism apply to all SARS-CoV-2 variants?",
         "confidence": 0.55, "trigger": "Raised alongside the pH hypothesis"},
    ]),
    ("catalytic site inhibitors", [
        {"type": "DeadEnd",
         "content": "Blocking the ACE2 catalytic site as an antiviral worsens lung damage via angiotensin II accumulation. Path closed.",
         "confidence": 0.90, "trigger": "Three weeks of experiments"},
    ]),
    ("TMPRSS2", [
        {"type": "Observation",
         "content": "TMPRSS2 serine protease primes spike at the cell surface and bypasses the endosomal route; ACE2 alone is not sufficient and pH is not the limiting factor.",
         "confidence": 0.88, "trigger": "Hoffmann et al. 2020 (Cell)"},
    ]),
]


def _demo_extract(prompt: str) -> str:
    for needle, nodes in _DEMO_EXTRACTIONS:
        if needle in prompt:
            return json.dumps({"nodes": nodes})
    return '{"nodes": []}'


def _id_for(block: str, keyword: str) -> str | None:
    """First UUID appearing on a line of the block that contains ``keyword``."""
    for line in block.splitlines():
        if keyword in line:
            m = _UUID_RE.search(line)
            if m:
                return m.group(0)
    return None


def _demo_detect(prompt: str) -> str:
    # The pH hypothesis contradicts the observation about high RBD-ACE2 affinity.
    candidate_part = prompt.split("Existing nodes")[0]
    if "histidine 34" in candidate_part:
        node_id = _id_for(prompt, "higher affinity")
        if node_id:
            return json.dumps({
                "contradiction": True,
                "node_id": node_id,
                "reason": "The candidate claims protonation reduces binding affinity, "
                          "while the existing node reports 10-20x higher affinity than SARS-CoV-1.",
            })
    return '{"contradiction": false, "node_id": null, "reason": null}'


def _demo_link(prompt: str) -> str:
    new_part, _, existing_part = prompt.partition("Existing nodes in the graph:")
    edges: list[dict] = []

    # opens_question: the hypothesis (just added) raises the open question about variants
    hyp_id = _id_for(new_part, "histidine 34")
    oq_id = _id_for(prompt, "mechanism apply to all")
    if hyp_id and oq_id:
        edges.append({"from": hyp_id, "to": oq_id, "type": "opens_question",
                      "confidence": 0.70, "reason": "The pH hypothesis raises a question about variants."})

    # falsifies: the TMPRSS2 observation (just added) invalidates the pH hypothesis
    tmprss2_id = _id_for(new_part, "TMPRSS2")
    target_hyp_id = _id_for(prompt, "histidine 34")
    if tmprss2_id and target_hyp_id:
        edges.append({"from": tmprss2_id, "to": target_hyp_id, "type": "falsifies",
                      "confidence": 0.85, "reason": "The TMPRSS2 surface pathway bypasses the endosome, so pH is not limiting."})

    return json.dumps({"edges": edges})


def _make_demo_llm() -> LLMCallable:
    """Deterministic replay LLM for the demo — no network calls.

    Recognizes the three prompt types (extraction, contradiction detection,
    edge proposal) and returns fixed responses consistent with the SARS-CoV-2
    scenario. Node UUIDs are resolved by reading them from the prompt itself,
    so the flow stays deterministic even if the IDs change on every run.
    """
    def demo(prompt: str) -> str:
        if "contradiction detector" in prompt:
            return _demo_detect(prompt)
        if "analyst of scientific knowledge graphs" in prompt:
            return _demo_link(prompt)
        return _demo_extract(prompt)

    return demo


def make_llm() -> LLMCallable:
    """Select the LLM provider from the environment configuration.

    Priority:
    1. MEMORYGRAPH_LLM_PROVIDER=anthropic|openai  (explicit)
    2. ANTHROPIC_API_KEY present → anthropic
    3. OPENAI_API_KEY present → openai
    4. No key → demo (stub)
    """
    explicit = os.getenv(_PROVIDER_ENV, "").lower().strip()
    if explicit == "demo":
        return _make_demo_llm()
    if explicit == "anthropic":
        return _make_anthropic_llm()
    if explicit == "openai":
        return _make_openai_llm()

    if os.getenv(_ANTHROPIC_KEY_ENV):
        return _make_anthropic_llm()
    if os.getenv(_OPENAI_KEY_ENV):
        return _make_openai_llm()

    return _make_demo_llm()
