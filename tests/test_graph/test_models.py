# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import datetime, timezone

import pytest

from memorygraph.graph.models import (
    DocumentIndex, Edge, EdgeType, NodeEntity, NodeState, NodeType,
    Project, WikiEntity, WikiState,
)


def test_node_type_values():
    assert NodeType.HYPOTHESIS.value == "Hypothesis"
    assert NodeType.DEAD_END.value == "DeadEnd"
    assert NodeType.METHOD_DECISION.value == "MethodDecision"


def test_edge_type_values():
    assert EdgeType.SUPPORTS.value == "supports"
    assert EdgeType.OPENS_QUESTION.value == "opens_question"


def test_node_entity_defaults():
    entity = NodeEntity(
        id="abc",
        user_id="user1",
        type=NodeType.HYPOTHESIS,
        created_at=datetime.now(timezone.utc),
    )
    assert entity.is_deleted is False


def test_node_state_fields():
    state = NodeState(
        id="s1",
        node_id="abc",
        version=1,
        content="test content",
        confidence=0.7,
        trigger="test trigger",
        created_at=datetime.now(timezone.utc),
    )
    assert state.version == 1
    assert state.confidence == 0.7


def test_edge_defaults():
    edge = Edge(
        edge_id="e1",
        from_node="n1",
        to_node="n2",
        type=EdgeType.SUPPORTS,
        confidence=0.9,
    )
    assert edge.invalidated_at is None


def test_node_type_from_str():
    t = NodeType("Hypothesis")
    assert t == NodeType.HYPOTHESIS


def test_edge_type_from_str():
    t = EdgeType("supports")
    assert t == EdgeType.SUPPORTS


# ── Context Layer models ──────────────────────────────────────────────────────


def test_project_fields():
    now = datetime.now(timezone.utc)
    p = Project(
        id="p1", user_id="u1", title="T", objective="O",
        summary="S", full_context="FC", created_at=now, updated_at=now,
    )
    assert p.summary == "S"
    assert p.full_context == "FC"
    assert p.updated_at == now


def test_wiki_entity_defaults():
    now = datetime.now(timezone.utc)
    w = WikiEntity(id="w1", user_id="u1", project_id="p1", title="Title", created_at=now)
    assert w.is_deleted is False


def test_wiki_state_has_summary_not_trigger():
    now = datetime.now(timezone.utc)
    s = WikiState(id="s1", wiki_id="w1", version=1, content="C", summary="What changed", created_at=now)
    assert s.summary == "What changed"
    assert s.version == 1


def test_document_index_optional_fields_none():
    now = datetime.now(timezone.utc)
    d = DocumentIndex(id="d1", user_id="u1", title="Paper", doi=None,
                      url=None, authors=None, pub_date=None, created_at=now)
    assert d.doi is None
    assert d.pub_date is None


def test_document_index_with_all_fields():
    now = datetime.now(timezone.utc)
    d = DocumentIndex(id="d1", user_id="u1", title="Paper",
                      doi="10.1000/xyz", url="https://example.com",
                      authors="Rossi M, Bianchi A", pub_date="2024-01-15",
                      created_at=now)
    assert d.doi == "10.1000/xyz"
    assert d.authors == "Rossi M, Bianchi A"


def test_user_identity_fields():
    from memorygraph.graph.models import UserIdentity
    now = datetime.now(timezone.utc)
    identity = UserIdentity(
        user_id="u1", public_key="pub", private_key="priv", created_at=now,
    )
    assert identity.user_id == "u1"
    assert identity.public_key == "pub"
    assert identity.private_key == "priv"
    assert identity.created_at == now


def test_user_network_consent_defaults_all_false():
    from memorygraph.graph.models import UserNetworkConsent
    consent = UserNetworkConsent(user_id="u1")
    assert consent.user_id == "u1"
    assert consent.discoverable is False
    assert consent.share_deadends is False
    assert consent.share_triggers is False
    assert consent.auto_propose is False
    assert consent.updated_at is None


def test_subgraph_token_fields():
    from memorygraph.graph.models import SubgraphToken
    now = datetime(2026, 6, 10, 9, 0, 0)
    token = SubgraphToken(
        id="t1", issuer_id="anna", recipient_id="bruno",
        nodes=[{"id": "n1", "type": "Hypothesis", "include_history": False, "states": []}],
        project_summary="public summary",
        wiki_page_ids=[],
        forkable=False,
        expires_at=now,
        signature="sig",
        created_at=now,
    )
    assert token.issuer_id == "anna"
    assert token.recipient_id == "bruno"
    assert token.project_summary == "public summary"
    assert token.wiki_page_ids == []
    assert token.nodes[0]["type"] == "Hypothesis"
    assert token.id == "t1"
    assert token.forkable is False
    assert token.expires_at == now
    assert token.signature == "sig"
    assert token.created_at == now
