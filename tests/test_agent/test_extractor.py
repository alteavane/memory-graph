from __future__ import annotations

from memorygraph.agent.extractor import (
    CandidateNode,
    ContradictionHint,
    ProposedNode,
    extract,
)
from memorygraph.graph.models import NodeType


def _make_llm(response: str):
    return lambda _prompt: response


class TestExtractTypes:
    def test_candidate_node_fields(self):
        node = CandidateNode(
            type=NodeType.HYPOTHESIS,
            content="Il pH ottimale è 7.4",
            confidence=0.7,
            trigger="esperimento #3",
        )
        assert node.type == NodeType.HYPOTHESIS
        assert node.project_id is None

    def test_proposed_node_hint_default_none(self):
        candidate = CandidateNode(NodeType.OBSERVATION, "fatto", 0.9, "diretto")
        proposed = ProposedNode(candidate=candidate)
        assert proposed.hint is None

    def test_contradiction_hint_fields(self):
        hint = ContradictionHint(existing_node_id="abc-123", reason="contraddice")
        assert hint.existing_node_id == "abc-123"


class TestExtract:
    def test_returns_candidate_nodes(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'
        )
        result = extract("testo", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.HYPOTHESIS
        assert result[0].content == "ACE2 è il recettore"
        assert result[0].confidence == 0.7

    def test_strips_markdown_backticks(self):
        llm = _make_llm(
            '```json\n{"nodes": [{"type": "Observation", "content": "pH 7.4", "confidence": 0.9, "trigger": "misura"}]}\n```'
        )
        result = extract("testo", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.OBSERVATION

    def test_unknown_type_skipped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Unknown", "content": "qualcosa", "confidence": 0.5, "trigger": "t"}]}'
        )
        result = extract("testo", llm)
        assert len(result) == 0

    def test_confidence_clamped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Conclusion", "content": "certo", "confidence": 1.5, "trigger": "t"}]}'
        )
        result = extract("testo", llm)
        assert result[0].confidence == 1.0

    def test_project_context_in_prompt(self):
        received_prompts = []
        def capturing_llm(prompt: str) -> str:
            received_prompts.append(prompt)
            return '{"nodes": []}'

        extract("testo", capturing_llm, project_context="contesto segreto del progetto")
        assert "contesto segreto del progetto" in received_prompts[0]

    def test_project_id_propagated_to_candidates(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "H", "confidence": 0.6, "trigger": "t"}]}'
        )
        result = extract("testo", llm, project_id="proj-1")
        assert result[0].project_id == "proj-1"
