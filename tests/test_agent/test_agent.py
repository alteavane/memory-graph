# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
# tests/test_agent/test_agent.py
from __future__ import annotations

import pytest

from memorygraph.agent.agent import MemoryAgent
from memorygraph.agent.extractor import CandidateNode, ProposedNode
from memorygraph.graph.models import EdgeType, NodeType


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def _extractor_llm(prompt: str) -> str:
    """Mock LLM che ritorna un nodo Hypothesis valido."""
    return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'


def _no_contradiction_llm(prompt: str) -> str:
    """Mock LLM: estrae un nodo, non rileva contraddizioni."""
    if "Valid NodeTypes" in prompt:
        return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'
    return '{"contradiction": false, "node_id": null, "reason": null}'


@pytest.fixture
def agent(tmp_path):
    return MemoryAgent(str(tmp_path / "test.kuzu"), llm=_extractor_llm)


class TestMemoryAgentExtract:
    def test_extract_returns_candidates(self, agent):
        result = agent.extract("Il pH ottimale per la reazione è 7.4")
        assert len(result) == 1
        assert isinstance(result[0], CandidateNode)
        assert result[0].type == NodeType.HYPOTHESIS

    def test_extract_without_project_id(self, agent):
        result = agent.extract("testo senza progetto")
        assert result[0].project_id is None

    def test_extract_with_project_id_propagated(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_extractor_llm)
        result = agent.extract("testo", project_id="proj-999")
        assert result[0].project_id == "proj-999"

    def test_extract_full_context_used_when_project_exists(self, tmp_path):
        """Verifica che full_context del progetto venga passato al LLM quando il progetto esiste."""
        captured_prompts = []

        def capturing_llm(prompt: str) -> str:
            captured_prompts.append(prompt)
            return '{"nodes": []}'

        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=capturing_llm)
        project = agent._project_store.create_project(
            user_id="u1", title="T", objective="O",
            summary="summary pubblico", full_context="full context segreto",
        )
        agent.extract("testo", project_id=project.id)
        assert any("full context segreto" in p for p in captured_prompts)


class TestMemoryAgentPropose:
    def test_propose_returns_proposed_nodes(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_no_contradiction_llm)
        result = agent.propose("Il pH ottimale è 7.4")
        assert len(result) == 1
        assert isinstance(result[0], ProposedNode)
        assert result[0].hint is None

    def test_propose_filters_below_threshold(self, tmp_path):
        def _low_confidence_llm(p: str) -> str:
            return '{"nodes": [{"type": "Hypothesis", "content": "speculazione", "confidence": 0.1, "trigger": "t"}]}'
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_low_confidence_llm, min_confidence=0.3)
        result = agent.propose("testo")
        assert len(result) == 0

    def test_propose_loads_project_nodes(self, tmp_path):
        """Verifica che _load_project_nodes funzioni con un progetto reale."""
        db_path = str(tmp_path / "test.kuzu")

        agent = MemoryAgent(db_path, llm=_no_contradiction_llm)

        project = agent._project_store.create_project(
            user_id="u1", title="T", objective="O", summary="s", full_context="fc"
        )
        existing_node = agent._store.create_node(
            "u1", NodeType.HYPOTHESIS, "nodo esistente", 0.8, "trigger"
        )
        agent._store._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": existing_node.id, "pid": project.id},
        )

        # propose should load project nodes without error
        result = agent.propose("Il pH ottimale è 7.4", project_id=project.id)
        assert len(result) == 1  # one proposed node (filtered+passed through pipeline)


class TestMemoryAgentRunValidation:
    def test_run_raises_if_user_id_none(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_no_contradiction_llm)
        with pytest.raises(ValueError, match="user_id"):
            agent.run("testo", user_id=None)


class TestMemoryAgentRunApproval:
    def test_run_y_writes_node(self, tmp_path):
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=_no_contradiction_llm,
            _input_fn=lambda p: "y",
        )
        ids = agent.run("Il pH ottimale è 7.4", user_id="u1")
        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        assert len(graph["nodes"]) == 1

    def test_run_n_does_not_write(self, tmp_path):
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=_no_contradiction_llm,
            _input_fn=lambda p: "n",
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 0
        graph = agent._store.get_graph("u1")
        assert len(graph["nodes"]) == 0

    def test_run_s_skips_remaining(self, tmp_path):
        multi_llm = lambda p: (
            '{"nodes": ['
            '{"type": "Hypothesis", "content": "H1", "confidence": 0.7, "trigger": "t"},'
            '{"type": "Observation", "content": "O1", "confidence": 0.9, "trigger": "t"}'
            ']}'
            if "Valid NodeTypes" in p else
            '{"contradiction": false, "node_id": null, "reason": null}'
        )
        responses = iter(["s"])
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=multi_llm,
            _input_fn=lambda p: next(responses),
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 0

    def test_run_a_approves_all_remaining(self, tmp_path):
        multi_llm = lambda p: (
            '{"nodes": ['
            '{"type": "Hypothesis", "content": "H1", "confidence": 0.7, "trigger": "t"},'
            '{"type": "Observation", "content": "O1", "confidence": 0.9, "trigger": "t"}'
            ']}'
            if "Valid NodeTypes" in p else
            '{"contradiction": false, "node_id": null, "reason": null}'
        )
        responses = iter(["a"])
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=multi_llm,
            _input_fn=lambda p: next(responses),
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 2


class TestMemoryAgentContradiction:
    def test_contradiction_hint_y_creates_edge(self, tmp_path):
        db_path = str(tmp_path / "test.kuzu")

        # Create agent first (initializes full schema)
        agent = MemoryAgent(db_path, llm=lambda p: '{"nodes": []}', _input_fn=lambda p: "y")

        # Setup: create project and existing node via internal stores
        project = agent._project_store.create_project(
            user_id="u1", title="Test", objective="obj",
            summary="summary", full_context="context",
        )
        existing = agent._store.create_node(
            "u1", NodeType.HYPOTHESIS, "ACE2 non è il recettore primario", 0.8, "t"
        )
        agent._store._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": existing.id, "pid": project.id},
        )

        # Smart LLM: extracts a node on first call, detects contradiction on second
        def smart_llm(prompt: str) -> str:
            if "Valid NodeTypes" in prompt:
                return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.8, "trigger": "paper"}]}'
            return f'{{"contradiction": true, "node_id": "{existing.id}", "reason": "Contraddice diretta"}}'

        agent._llm = smart_llm
        responses = iter(["y", "y"])  # first y = approve node, second y = create CONTRADDICE edge
        agent._input_fn = lambda p: next(responses)

        ids = agent.run("testo", project_id=project.id, user_id="u1")

        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        edges = [e for e in graph["edges"] if e.type == EdgeType.CONTRADDICE]
        assert len(edges) == 1
        assert edges[0].from_node == ids[0]
        assert edges[0].to_node == existing.id

    def test_contradiction_hint_n_no_edge(self, tmp_path):
        db_path = str(tmp_path / "test.kuzu")
        agent = MemoryAgent(db_path, llm=lambda p: '{"nodes": []}', _input_fn=lambda p: "y")

        project = agent._project_store.create_project(
            user_id="u1", title="T", objective="o", summary="s", full_context="fc",
        )
        existing = agent._store.create_node("u1", NodeType.HYPOTHESIS, "tesi contraria", 0.8, "t")
        agent._store._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": existing.id, "pid": project.id},
        )

        def smart_llm(prompt: str) -> str:
            if "Valid NodeTypes" in prompt:
                return '{"nodes": [{"type": "Hypothesis", "content": "nuova tesi", "confidence": 0.8, "trigger": "t"}]}'
            return f'{{"contradiction": true, "node_id": "{existing.id}", "reason": "contraddice"}}'

        agent._llm = smart_llm
        responses = iter(["y", "n"])  # approve node, refuse CONTRADDICE edge
        agent._input_fn = lambda p: next(responses)

        ids = agent.run("testo", project_id=project.id, user_id="u1")
        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        edges = [e for e in graph["edges"] if e.type == EdgeType.CONTRADDICE]
        assert len(edges) == 0


class TestAgentLinkIntegration:
    def test_run_calls_link_agent_after_nodes(self, db_path, monkeypatch):
        """MemoryAgent.run() chiama LinkAgent dopo aver scritto i nodi."""
        import memorygraph.agent.link_agent as la_module
        called_with = []

        class MockLinkAgent:
            def __init__(self, *args, **kwargs): pass
            def run(self, new_node_ids, **kwargs):
                called_with.extend(new_node_ids)
                return []

        monkeypatch.setattr(la_module, "LinkAgent", MockLinkAgent)

        mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "test", "confidence": 0.7, "trigger": "t"}]}'
        agent = MemoryAgent(db_path, llm=mock_llm, _input_fn=lambda _: "y")
        written = agent.run("testo di test", user_id="u1")
        assert len(called_with) == len(written)

    def test_run_skips_link_agent_if_no_nodes_written(self, db_path, monkeypatch):
        """Se zero nodi approvati, LinkAgent.run() non viene chiamato."""
        import memorygraph.agent.link_agent as la_module
        link_called = []

        class MockLinkAgent:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args, **kwargs):
                link_called.append(True)
                return []

        monkeypatch.setattr(la_module, "LinkAgent", MockLinkAgent)

        mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "test", "confidence": 0.7, "trigger": "t"}]}'
        agent = MemoryAgent(db_path, llm=mock_llm, _input_fn=lambda _: "n")  # rifiuta tutti
        agent.run("testo di test", user_id="u1")
        assert link_called == []
