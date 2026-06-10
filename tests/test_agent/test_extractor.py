# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
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
            content="The optimal pH is 7.4",
            confidence=0.7,
            trigger="experiment #3",
        )
        assert node.type == NodeType.HYPOTHESIS
        assert node.project_id is None

    def test_proposed_node_hint_default_none(self):
        candidate = CandidateNode(NodeType.OBSERVATION, "fact", 0.9, "direct")
        proposed = ProposedNode(candidate=candidate)
        assert proposed.hint is None

    def test_contradiction_hint_fields(self):
        hint = ContradictionHint(existing_node_id="abc-123", reason="contradicts")
        assert hint.existing_node_id == "abc-123"


class TestExtract:
    def test_returns_candidate_nodes(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "ACE2 is the receptor", "confidence": 0.7, "trigger": "paper Zhang"}]}'
        )
        result = extract("text", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.HYPOTHESIS
        assert result[0].content == "ACE2 is the receptor"
        assert result[0].confidence == 0.7

    def test_strips_markdown_backticks(self):
        llm = _make_llm(
            '```json\n{"nodes": [{"type": "Observation", "content": "pH 7.4", "confidence": 0.9, "trigger": "measurement"}]}\n```'
        )
        result = extract("text", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.OBSERVATION

    def test_unknown_type_skipped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Unknown", "content": "something", "confidence": 0.5, "trigger": "t"}]}'
        )
        result = extract("text", llm)
        assert len(result) == 0

    def test_confidence_clamped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Conclusion", "content": "certain", "confidence": 1.5, "trigger": "t"}]}'
        )
        result = extract("text", llm)
        assert result[0].confidence == 1.0

    def test_project_context_in_prompt(self):
        received_prompts = []
        def capturing_llm(prompt: str) -> str:
            received_prompts.append(prompt)
            return '{"nodes": []}'

        extract("text", capturing_llm, project_context="secret project context")
        assert "secret project context" in received_prompts[0]

    def test_project_id_propagated_to_candidates(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "H", "confidence": 0.6, "trigger": "t"}]}'
        )
        result = extract("text", llm, project_id="proj-1")
        assert result[0].project_id == "proj-1"

    def test_invalid_json_returns_empty(self):
        llm = _make_llm("not valid json at all")
        result = extract("text", llm)
        assert result == []

    def test_null_confidence_returns_zero(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "H", "confidence": null, "trigger": "t"}]}'
        )
        result = extract("text", llm)
        assert result[0].confidence == 0.0
