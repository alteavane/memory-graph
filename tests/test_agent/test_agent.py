# tests/test_agent/test_agent.py
from __future__ import annotations

import pytest

from memorygraph.agent.agent import MemoryAgent
from memorygraph.agent.extractor import CandidateNode, ProposedNode
from memorygraph.graph.models import EdgeType, NodeType


def _extractor_llm(prompt: str) -> str:
    """Mock LLM che ritorna un nodo Hypothesis valido."""
    return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'


def _no_contradiction_llm(prompt: str) -> str:
    """Mock LLM: estrae un nodo, non rileva contraddizioni."""
    if "NodeType validi" in prompt:
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


class TestMemoryAgentPropose:
    def test_propose_returns_proposed_nodes(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_no_contradiction_llm)
        result = agent.propose("Il pH ottimale è 7.4")
        assert len(result) == 1
        assert isinstance(result[0], ProposedNode)
        assert result[0].hint is None

    def test_propose_filters_below_threshold(self, tmp_path):
        low_conf_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "speculazione", "confidence": 0.1, "trigger": "t"}]}'
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=low_conf_llm, min_confidence=0.3)
        result = agent.propose("testo")
        assert len(result) == 0
