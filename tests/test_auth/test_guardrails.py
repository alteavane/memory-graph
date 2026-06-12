# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 3b §8 invariants: nothing private leaks, snapshot is frozen, consent is enforced."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from memorygraph.auth.consent import ConsentStore
from memorygraph.auth.identity import IdentityStore
from memorygraph.auth.schema import init_auth_schema
from memorygraph.auth.token import build_token, serialize, verify_token
from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.models import NodeType
from memorygraph.graph.store import GraphStore

ISSUE_TS = datetime(2026, 6, 10, 9, 0, 0)
CHECK_TS = datetime(2026, 6, 10, 9, 30, 0)


@pytest.fixture
def stores(tmp_path):
    graph = GraphStore(str(tmp_path / "t.kuzu"))
    conn = graph._conn
    init_context_schema(conn)
    init_auth_schema(conn)
    return SimpleNamespace(
        graph=graph, identity=IdentityStore(conn),
        consent=ConsentStore(conn), project=ProjectStore(conn),
    )


def _issue(stores, *, node_ids, project_summary="public summary", full_context="SECRET_FULL_CONTEXT"):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", project_summary, full_context)
    return proj, build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=node_ids, ttl_seconds=3600, now=ISSUE_TS,
    )


def test_full_context_never_in_serialized_token(stores):
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "t")
    _, token = _issue(stores, node_ids=[{"id": node.id, "include_history": False}])
    assert "SECRET_FULL_CONTEXT" not in serialize(token)


def test_private_key_never_in_serialized_token(stores):
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "t")
    _, token = _issue(stores, node_ids=[{"id": node.id, "include_history": False}])
    private_key = stores.identity.get_identity("anna", include_private=True).private_key
    assert private_key not in serialize(token)


def test_project_summary_snapshot_is_frozen(stores):
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "t")
    proj, token = _issue(stores, node_ids=[{"id": node.id, "include_history": False}])
    stores.project.update_project(proj.id, summary="EDITED LATER")
    assert token.project_summary == "public summary"  # unchanged
    pub = stores.identity.get_public_key("anna")
    assert verify_token(token, pub, now=CHECK_TS).ok is True


def test_wiki_page_ids_empty_unless_provided(stores):
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "t")
    _, token = _issue(stores, node_ids=[{"id": node.id, "include_history": False}])
    assert token.wiki_page_ids == []


def test_share_deadends_false_excludes_deadend(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    hyp = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "alive", 0.6, "t")
    dead = stores.graph.create_node("anna", NodeType.DEAD_END, "rejected path", 0.1, "falsified")
    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[
            {"id": hyp.id, "include_history": False},
            {"id": dead.id, "include_history": False},
        ],
        ttl_seconds=3600, now=ISSUE_TS,
    )
    ids = [n["id"] for n in token.nodes]
    assert hyp.id in ids
    assert dead.id not in ids  # consent default: no DeadEnd


def test_share_deadends_true_includes_deadend(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    stores.consent.set_consent("anna", share_deadends=True)
    dead = stores.graph.create_node("anna", NodeType.DEAD_END, "rejected path", 0.1, "falsified")
    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[{"id": dead.id, "include_history": False}],
        ttl_seconds=3600, now=ISSUE_TS,
    )
    assert [n["id"] for n in token.nodes] == [dead.id]


def test_share_triggers_false_strips_trigger(stores):
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "SECRET_TRIGGER")
    _, token = _issue(stores, node_ids=[{"id": node.id, "include_history": False}])
    assert token.nodes[0]["states"][0]["trigger"] == ""
    assert "SECRET_TRIGGER" not in serialize(token)


def test_share_triggers_true_keeps_trigger(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    stores.consent.set_consent("anna", share_triggers=True)
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "kept trigger")
    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[{"id": node.id, "include_history": False}],
        ttl_seconds=3600, now=ISSUE_TS,
    )
    assert token.nodes[0]["states"][0]["trigger"] == "kept trigger"
