# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations
import json
import pytest
from memorygraph.agent.link_agent import CandidateEdge, ProposedEdge, LinkAgent
from memorygraph.graph.models import EdgeType


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def _mock_llm(edges: list[dict]):
    def llm(prompt: str) -> str:
        return json.dumps({"edges": edges})
    return llm


class TestProposeFiltering:
    def test_valid_edge_returned(self, db_path):
        """LLM returns valid edges → non-empty list of ProposedEdge."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs content", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp content", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert len(proposed) == 1
        assert proposed[0].candidate.type == EdgeType.SUPPORTS

    def test_markdown_stripped(self, db_path):
        """JSON with markdown backticks → parsed correctly."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        def llm_with_backticks(prompt: str) -> str:
            return f"```json\n{json.dumps({'edges': [{'from': n1.id, 'to': n2.id, 'type': 'supports', 'confidence': 0.8, 'reason': 'ok'}]})}\n```"
        agent = LinkAgent(db_path, llm=llm_with_backticks)
        proposed = agent.propose([n1.id], user_id="u1")
        assert len(proposed) == 1

    def test_invalid_type_skipped(self, db_path):
        """invalid type → edge skipped."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "TIPO_INVENTATO", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_low_confidence_filtered(self, db_path):
        """confidence < min_confidence → edge filtered out."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.1, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm, min_confidence=0.4)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_self_loop_filtered(self, db_path):
        """self-loop → edge filtered out."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        llm = _mock_llm([{"from": n1.id, "to": n1.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_unknown_node_filtered(self, db_path):
        """node_id not in graph → edge filtered out."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        llm = _mock_llm([{"from": n1.id, "to": "node-does-not-exist", "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_preview_populated(self, db_path):
        """from_content and to_content populated from the query."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "source content", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "target content", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed[0].from_content == "source content"
        assert proposed[0].to_content == "target content"

    def test_empty_edges_returns_empty_list(self, db_path):
        """LLM returns {"edges": []} → empty list."""
        llm = _mock_llm([])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose(["anything"], user_id="u1")
        assert proposed == []


class TestRun:
    def test_approved_edges_written(self, db_path, monkeypatch):
        """Approved edges → written to GraphStore."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        # simulate confirmation y
        monkeypatch.setattr("builtins.input", lambda _: "y")
        edge_ids = agent.run([n1.id], user_id="u1")
        assert len(edge_ids) == 1
        graph = agent._store.get_graph("u1")
        assert len(graph["edges"]) == 1

    def test_deselected_edge_not_written(self, db_path, monkeypatch):
        """Deselected edge → not written."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        # deselect 1 then confirm
        inputs = iter(["n 1", "y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        edge_ids = agent.run([n1.id], user_id="u1")
        assert edge_ids == []

    def test_no_candidates_returns_empty(self, db_path):
        """No candidates → returns [] without prompting."""
        llm = _mock_llm([])
        agent = LinkAgent(db_path, llm=llm)
        edge_ids = agent.run(["anything"], user_id="u1")
        assert edge_ids == []

    def test_cancel_writes_nothing(self, db_path, monkeypatch):
        """N → no edge written."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supports", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        monkeypatch.setattr("builtins.input", lambda _: "N")
        edge_ids = agent.run([n1.id], user_id="u1")
        assert edge_ids == []
        graph = store.get_graph("u1")
        assert len(graph["edges"]) == 0
