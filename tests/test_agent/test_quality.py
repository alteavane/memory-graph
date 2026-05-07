from __future__ import annotations

import pytest

from memorygraph.agent.extractor import CandidateNode
from memorygraph.agent.quality import filter_candidates
from memorygraph.graph.models import NodeType


def _make(content: str = "contenuto", confidence: float = 0.7) -> CandidateNode:
    return CandidateNode(
        type=NodeType.HYPOTHESIS, content=content, confidence=confidence, trigger="t"
    )


class TestFilterCandidates:
    def test_below_threshold_removed(self):
        result = filter_candidates([_make(confidence=0.2)], min_confidence=0.3)
        assert len(result) == 0

    def test_empty_content_removed(self):
        result = filter_candidates([_make(content="   ")], min_confidence=0.3)
        assert len(result) == 0

    def test_valid_candidate_passes(self):
        result = filter_candidates([_make(confidence=0.5)], min_confidence=0.3)
        assert len(result) == 1

    def test_default_min_confidence_is_0_3(self):
        below = _make(confidence=0.29)
        above = _make(confidence=0.30)
        result = filter_candidates([below, above])
        assert len(result) == 1
        assert result[0].confidence == 0.30

    def test_empty_list_returns_empty(self):
        assert filter_candidates([]) == []
