# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import datetime

from memorygraph.auth.token import deserialize, serialize
from memorygraph.graph.models import SubgraphToken


def _sample_token() -> SubgraphToken:
    now = datetime(2026, 6, 10, 9, 0, 0)
    return SubgraphToken(
        id="t1", issuer_id="anna", recipient_id="bruno",
        nodes=[{
            "id": "n1", "type": "Hypothesis", "include_history": False,
            "states": [{
                "version": 1, "content": "pH matters", "confidence": 0.6,
                "trigger": "", "created_at": "2026-06-10T08:00:00",
            }],
        }],
        project_summary="public summary",
        wiki_page_ids=[],
        forkable=False,
        expires_at=datetime(2026, 6, 11, 9, 0, 0),
        signature="sig-placeholder",
        created_at=now,
    )


def test_serialize_deserialize_roundtrip():
    token = _sample_token()
    restored = deserialize(serialize(token))
    assert restored.id == token.id
    assert restored.issuer_id == token.issuer_id
    assert restored.recipient_id == token.recipient_id
    assert restored.nodes == token.nodes
    assert restored.project_summary == token.project_summary
    assert restored.wiki_page_ids == token.wiki_page_ids
    assert restored.forkable == token.forkable
    assert restored.expires_at == token.expires_at
    assert restored.created_at == token.created_at
    assert restored.signature == token.signature


def test_serialize_is_deterministic():
    token = _sample_token()
    assert serialize(token) == serialize(token)
