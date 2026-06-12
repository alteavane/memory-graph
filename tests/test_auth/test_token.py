# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import dataclasses
from datetime import datetime

from memorygraph.auth.crypto import generate_keypair, sign
from memorygraph.auth.token import _token_payload, deserialize, serialize, verify_token
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


def _signed_token(private_key: str) -> SubgraphToken:
    token = _sample_token()
    signature = sign(_token_payload(token), private_key)
    return dataclasses.replace(token, signature=signature)


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


def test_verify_token_accepts_valid_unexpired():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    result = verify_token(token, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is True


def test_verify_token_rejects_expired():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    result = verify_token(token, pub, now=datetime(2026, 6, 12, 9, 0, 0))  # past expires_at
    assert result.ok is False
    assert result.reason == "expired"


def test_verify_token_rejects_tampered_payload():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    tampered = SubgraphToken(
        id=token.id, issuer_id=token.issuer_id, recipient_id=token.recipient_id,
        nodes=token.nodes, project_summary="TAMPERED summary",  # changed after signing
        wiki_page_ids=token.wiki_page_ids, forkable=token.forkable,
        expires_at=token.expires_at, signature=token.signature, created_at=token.created_at,
    )
    result = verify_token(tampered, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_verify_token_never_raises_on_garbage_signature():
    _, pub = generate_keypair()
    token = _sample_token()  # signature is "sig-placeholder", not valid base64 sig
    result = verify_token(token, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_verify_token_accepts_at_exact_expiry():
    priv, pub = generate_keypair()
    token = _signed_token(priv)  # expires_at = 2026-06-11T09:00:00
    result = verify_token(token, pub, now=datetime(2026, 6, 11, 9, 0, 0))
    assert result.ok is True


from types import SimpleNamespace

import kuzu
import pytest

from memorygraph.auth.consent import ConsentStore
from memorygraph.auth.identity import IdentityStore
from memorygraph.auth.schema import init_auth_schema
from memorygraph.auth.token import build_token
from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.models import NodeType
from memorygraph.graph.store import GraphStore


@pytest.fixture
def stores(tmp_path):
    graph = GraphStore(str(tmp_path / "t.kuzu"))
    conn = graph._conn
    init_context_schema(conn)
    init_auth_schema(conn)
    return SimpleNamespace(
        graph=graph,
        identity=IdentityStore(conn),
        consent=ConsentStore(conn),
        project=ProjectStore(conn),
    )


def test_build_token_materializes_and_signs(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "public summary", "SECRET ctx")
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "pH matters", 0.6, "obs A")

    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[{"id": node.id, "include_history": False}],
        ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
    )

    assert token.issuer_id == "anna"
    assert token.recipient_id == "bruno"
    assert token.project_summary == "public summary"
    assert token.wiki_page_ids == []
    assert token.expires_at == datetime(2026, 6, 10, 10, 0, 0)
    assert len(token.nodes) == 1
    entry = token.nodes[0]
    assert entry["id"] == node.id
    assert entry["type"] == "Hypothesis"
    assert entry["states"][0]["content"] == "pH matters"
    assert entry["states"][0]["trigger"] == ""  # default consent strips triggers
    # signature verifies against the issuer's public key
    pub = stores.identity.get_public_key("anna")
    assert verify_token(token, pub, now=datetime(2026, 6, 10, 9, 30, 0)).ok is True


def test_build_token_include_history_materializes_all_states(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "v1", 0.6, "t1")
    stores.graph.update_node(node.id, "v2", 0.35, "t2")

    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[{"id": node.id, "include_history": True}],
        ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
    )
    versions = [s["version"] for s in token.nodes[0]["states"]]
    assert versions == [1, 2]


def test_build_token_rejects_foreign_node(stores):
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    bruno_node = stores.graph.create_node("bruno", NodeType.OBSERVATION, "his data", 0.9, "t")
    with pytest.raises(ValueError, match="not found for issuer"):
        build_token(
            graph_store=stores.graph, identity_store=stores.identity,
            consent_store=stores.consent, project_store=stores.project,
            issuer_id="anna", recipient_id="bruno", project_id=proj.id,
            node_ids=[{"id": bruno_node.id, "include_history": False}],
            ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
        )


def test_build_token_unknown_issuer_raises(stores):
    proj = stores.project.create_project("anna", "T", "obj", "s", "ctx")
    with pytest.raises(ValueError, match="no identity"):
        build_token(
            graph_store=stores.graph, identity_store=stores.identity,
            consent_store=stores.consent, project_store=stores.project,
            issuer_id="ghost", recipient_id="bruno", project_id=proj.id,
            node_ids=[], ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
        )


from memorygraph.auth.token import TokenStore


def test_token_store_save_and_get_roundtrip(stores, tmp_path):
    token_store = TokenStore(stores.graph._conn)
    stores.identity.create_identity("anna")
    proj = stores.project.create_project("anna", "T", "obj", "public summary", "ctx")
    node = stores.graph.create_node("anna", NodeType.HYPOTHESIS, "pH", 0.6, "obs")
    token = build_token(
        graph_store=stores.graph, identity_store=stores.identity,
        consent_store=stores.consent, project_store=stores.project,
        issuer_id="anna", recipient_id="bruno", project_id=proj.id,
        node_ids=[{"id": node.id, "include_history": False}],
        ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
    )
    token_store.save(token)
    loaded = token_store.get(token.id)
    assert loaded is not None
    assert loaded.id == token.id
    assert loaded.project_summary == "public summary"
    assert loaded.nodes == token.nodes
    assert loaded.signature == token.signature
    assert loaded.expires_at == token.expires_at
    # the persisted token still verifies
    pub = stores.identity.get_public_key("anna")
    assert verify_token(loaded, pub, now=datetime(2026, 6, 10, 9, 30, 0)).ok is True


def test_token_store_get_missing_returns_none(stores):
    token_store = TokenStore(stores.graph._conn)
    assert token_store.get("nope") is None


def test_verify_token_handles_none_public_key():
    priv, _ = generate_keypair()
    token = _signed_token(priv)
    # None public key makes crypto raise TypeError → caught, reported as bad_signature
    result = verify_token(token, None, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_build_token_unknown_project_raises(stores):
    stores.identity.create_identity("anna")
    with pytest.raises(ValueError, match="not found"):
        build_token(
            graph_store=stores.graph, identity_store=stores.identity,
            consent_store=stores.consent, project_store=stores.project,
            issuer_id="anna", recipient_id="bruno", project_id="ghost-project",
            node_ids=[], ttl_seconds=3600, now=datetime(2026, 6, 10, 9, 0, 0),
        )
