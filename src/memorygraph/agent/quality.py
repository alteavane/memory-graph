# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from memorygraph.agent.extractor import CandidateNode


def filter_candidates(
    candidates: list[CandidateNode],
    min_confidence: float = 0.3,
) -> list[CandidateNode]:
    """Filtra i candidati che non soddisfano i criteri minimi di quality."""
    return [
        c for c in candidates
        if c.confidence >= min_confidence and c.content.strip()
    ]
