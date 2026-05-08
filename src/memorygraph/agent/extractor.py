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
Sei un estrattore di credenze da testo scientifico.

NodeType validi: Observation, Hypothesis, Conclusion, DeadEnd, OpenQuestion, Paper, Experiment, MethodDecision

Scegli il tipo più specifico:
- Observation    → fatto empirico osservato direttamente
- Hypothesis     → ipotesi da verificare, anche se il testo usa "forse", "potrebbe"
- Conclusion     → validata, alta certezza
- DeadEnd        → fallimento, strada chiusa, falsificazione
- OpenQuestion   → domanda senza risposta ancora
- Paper          → citazione di fonte esterna, articolo, dataset
- Experiment     → descrizione di un esperimento con metodo/risultato
- MethodDecision → scelta metodologica con ragionamento

Se il testo esprime incertezza esplicita → Hypothesis o OpenQuestion.
Se descrive un fallimento → DeadEnd.
Se cita una fonte esterna → Paper.

Scala confidence:
0.9+    → fatto empirico osservato direttamente
0.6–0.9 → ipotesi con evidenza parziale
0.3–0.6 → speculazione o evidenza debole
< 0.3   → dubbio esplicito — includi solo se il contenuto è significativo"""

_OUTPUT_FORMAT = """\
Rispondi SOLO con JSON valido in questo formato:
{"nodes": [{"type": "...", "content": "...", "confidence": 0.0, "trigger": "..."}]}
Se non trovi nodi significativi, rispondi: {"nodes": []}"""


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
        parts.append(f"Contesto del progetto:\n{project_context}")
    parts.append(f"Testo:\n{text}")
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
