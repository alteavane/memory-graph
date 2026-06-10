# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import logging
import math

from memorygraph.agent.extractor import (
    CandidateNode,
    ContradictionHint,
    EmbedCallable,
    LLMCallable,
)
from memorygraph.graph.models import NodeState

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _format_nodes(nodes: list[NodeState]) -> str:
    return "\n".join(
        f"- id: {n.node_id} | {n.content} (confidence: {n.confidence:.2f})"
        for n in nodes
    )


def _call_llm(
    candidate: CandidateNode,
    nodes: list[NodeState],
    llm: LLMCallable,
) -> ContradictionHint | None:
    prompt = (
        "You are a contradiction detector in a knowledge graph.\n\n"
        f"Candidate:\n"
        f"  Type: {candidate.type.value}\n"
        f"  Content: {candidate.content}\n"
        f"  Confidence: {candidate.confidence:.2f}\n\n"
        f"Existing nodes in the project:\n"
        f"{_format_nodes(nodes)}\n\n"
        "Does the candidate contradict any of the existing nodes?\n"
        'Reply ONLY with valid JSON:\n'
        '{"contradiction": true/false, "node_id": "<node id or null>", "reason": "<explanation or null>"}'
    )
    raw = llm(prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.split("\n") if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Detector LLM invalid JSON: %s", raw[:200])
        return None

    if data.get("contradiction") and data.get("node_id"):
        return ContradictionHint(
            existing_node_id=data["node_id"],
            reason=data.get("reason") or "",
        )
    return None


def detect(
    candidate: CandidateNode,
    project_nodes: list[NodeState],
    llm: LLMCallable,
    embed: EmbedCallable | None = None,
    top_k: int = 5,
) -> ContradictionHint | None:
    """Detect whether the candidate contradicts existing nodes in the project.

    If ``embed`` is provided, pre-filter the ``top_k`` nodes most similar to the
    candidate via cosine similarity before calling the LLM. Otherwise the LLM
    receives all of the project's nodes.

    Returns:
        ContradictionHint if a contradiction is detected, None otherwise.
    """
    if candidate.project_id is None or not project_nodes:
        return None

    if embed is None:
        return _call_llm(candidate, project_nodes, llm)

    candidate_vec = embed(candidate.content)
    scored: list[tuple[float, NodeState]] = []
    for node in project_nodes:
        node_vec = embed(node.content)
        sim = _cosine_similarity(candidate_vec, node_vec)
        scored.append((sim, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_nodes = [node for _, node in scored[:top_k]]
    return _call_llm(candidate, top_nodes, llm)
