# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from datetime import datetime

from memorygraph.agent.detector import detect
from memorygraph.agent.extractor import CandidateNode
from memorygraph.graph.models import NodeState, NodeType


def _make_candidate(project_id: str | None = "proj-1") -> CandidateNode:
    return CandidateNode(
        type=NodeType.HYPOTHESIS,
        content="ACE2 è il recettore principale",
        confidence=0.8,
        trigger="paper",
        project_id=project_id,
    )


def _make_state(node_id: str = "node-existing", content: str = "ACE2 non è il recettore") -> NodeState:
    return NodeState(
        id="state-1",
        node_id=node_id,
        version=1,
        content=content,
        confidence=0.8,
        trigger="t",
        created_at=datetime(2026, 1, 1),
    )


class TestDetect:
    def test_no_project_id_returns_none(self):
        llm = lambda p: '{"contradiction": true, "node_id": "x", "reason": "r"}'
        result = detect(_make_candidate(project_id=None), [_make_state()], llm)
        assert result is None

    def test_empty_project_nodes_returns_none(self):
        llm = lambda p: '{"contradiction": true, "node_id": "x", "reason": "r"}'
        result = detect(_make_candidate(), [], llm)
        assert result is None

    def test_llm_detects_contradiction(self):
        llm = lambda p: '{"contradiction": true, "node_id": "node-existing", "reason": "Contraddice diretta"}'
        result = detect(_make_candidate(), [_make_state()], llm)
        assert result is not None
        assert result.existing_node_id == "node-existing"
        assert result.reason == "Contraddice diretta"

    def test_llm_no_contradiction_returns_none(self):
        llm = lambda p: '{"contradiction": false, "node_id": null, "reason": null}'
        result = detect(_make_candidate(), [_make_state()], llm)
        assert result is None

    def test_embed_top_k_llm_called_only_on_top_k(self):
        prompts_received = []

        def recording_llm(prompt: str) -> str:
            prompts_received.append(prompt)
            return '{"contradiction": false, "node_id": null, "reason": null}'

        # 3 nodes, top_k=2 — LLM prompt should contain at most 2 node ids
        states = [
            _make_state(node_id="n1", content="testo 1"),
            _make_state(node_id="n2", content="testo 2"),
            _make_state(node_id="n3", content="testo 3"),
        ]
        embed = lambda t: [1.0, 0.0]   # same vector for all — ties resolved by list order

        detect(_make_candidate(), states, recording_llm, embed=embed, top_k=2)

        assert len(prompts_received) == 1
        # Only 2 of the 3 node ids should appear in the prompt
        count = sum(1 for s in states if s.node_id in prompts_received[0])
        assert count == 2
