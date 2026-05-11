# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable

from memorygraph.graph.models import NodeType

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]
# Defined here (not in detector.py) to avoid circular imports — detector.py imports from extractor.py
EmbedCallable = Callable[[str], list[float]]

_NODE_TYPE_VALUES = {nt.value for nt in NodeType}

_ROLE_INSTRUCTIONS = """\
You are a belief extractor from scientific text.

Valid NodeTypes: Observation, Hypothesis, Conclusion, DeadEnd, OpenQuestion, Paper, Experiment, MethodDecision

Choose the most specific type:
- Observation    → empirical fact observed directly
- Hypothesis     → hypothesis to be verified, even if the text uses "perhaps", "might"
- Conclusion     → validated, high certainty
- DeadEnd        → failure, closed path, falsification
- OpenQuestion   → question without an answer yet
- Paper          → citation of external source, article, dataset
- Experiment     → description of an experiment with method/result
- MethodDecision → methodological choice with explicit reasoning

If the text expresses explicit uncertainty → Hypothesis or OpenQuestion.
If it describes a failure → DeadEnd.
If it cites an external source → Paper.

Confidence scale:
0.9+    → empirical fact observed directly
0.6–0.9 → hypothesis with partial evidence
0.3–0.6 → speculation or weak evidence
< 0.3   → explicit doubt — include only if the content is significant"""

_OUTPUT_FORMAT = """\
Reply ONLY with valid JSON in this format:
{"nodes": [{"type": "...", "content": "...", "confidence": 0.0, "trigger": "..."}]}
If no significant nodes are found, reply: {"nodes": []}"""


@dataclass
class CandidateNode:
    """Nodo candidato estratto dal testo dal LLM, non ancora filtrato né scritto nel grafo."""

    type: NodeType
    content: str
    confidence: float
    trigger: str
    project_id: str | None = None


@dataclass
class ContradictionHint:
    """Segnale di possibile contraddizione rilevato dal detector — non blocca il nodo, lo annota."""

    existing_node_id: str
    reason: str


@dataclass
class ProposedNode:
    """Candidato post-quality-gate con eventuale hint di contraddizione, pronto per il loop CLI."""

    candidate: CandidateNode
    hint: ContradictionHint | None = None


def _build_prompt(text: str, project_context: str | None) -> str:
    parts = [_ROLE_INSTRUCTIONS]
    if project_context:
        parts.append(f"Project context:\n{project_context}")
    parts.append(f"Text:\n{text}")
    parts.append(_OUTPUT_FORMAT)
    return "\n\n".join(parts)


def _strip_markdown(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


def extract(
    text: str,
    llm: LLMCallable,
    project_context: str | None = None,
    project_id: str | None = None,
) -> list[CandidateNode]:
    """Chiama LLM con prompt strutturato, parsifica JSON, ritorna candidati."""
    prompt = _build_prompt(text, project_context)
    raw = llm(prompt)
    cleaned = _strip_markdown(raw)

    try:
        data = json.loads(cleaned)
        nodes_raw: list[dict] = data.get("nodes", [])
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %s", raw[:200])
        return []

    candidates: list[CandidateNode] = []
    for item in nodes_raw:
        type_str = item.get("type", "")
        if type_str not in _NODE_TYPE_VALUES:
            logger.warning("Unknown node type skipped: %s", type_str)
            continue
        content = item.get("content", "")
        confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.0)))
        trigger = item.get("trigger", "")
        candidates.append(CandidateNode(
            type=NodeType(type_str),
            content=content,
            confidence=confidence,
            trigger=trigger,
            project_id=project_id,
        ))

    return candidates
