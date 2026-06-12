# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from fastapi.testclient import TestClient

from memorygraph.api.app import create_app
from memorygraph.graph.models import NodeType


def _app(tmp_path, owner="anna", name="anna"):
    return create_app(owner_id=owner, db_path=str(tmp_path / f"{name}.kuzu"))


def _seed_project_and_node(app, owner="anna"):
    from memorygraph.context.project import ProjectStore

    mgr = app.state.manager

    def op(store):
        proj = ProjectStore(store._conn).create_project(
            owner, "T", "obj", "public summary", "SECRET ctx"
        )
        node = store.create_node(owner, NodeType.HYPOTHESIS, "pH matters", 0.6, "obs A")
        return proj.id, node.id

    return mgr.submit(owner, op)


def test_get_identity_returns_owner_public_key(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    resp = client.get("/identity/anna")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "anna"
    assert body["public_key"]                     # auto-provisioned, non-empty
    assert "private_key" not in body


def test_get_identity_unknown_user_404(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    assert client.get("/identity/ghost").status_code == 404


def test_get_consent_defaults_all_false(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    body = client.get("/consent").json()
    assert body == {
        "discoverable": False, "share_deadends": False,
        "share_triggers": False, "auto_propose": False,
    }


def test_put_consent_updates_and_persists(tmp_path):
    app = _app(tmp_path)
    client = TestClient(app)
    resp = client.put("/consent", json={"share_deadends": True, "share_triggers": True})
    assert resp.status_code == 200
    assert resp.json()["share_deadends"] is True
    # persisted across requests
    reread = client.get("/consent").json()
    assert reread["share_deadends"] is True
    assert reread["discoverable"] is False        # untouched stays default


def test_post_tokens_issues_signed_token(tmp_path):
    app = _app(tmp_path)
    project_id, node_id = _seed_project_and_node(app)
    client = TestClient(app)
    resp = client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": [{"id": node_id, "include_history": False}],
        "ttl_seconds": 3600,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_id"]
    assert "public summary" in body["token"]      # serialized token carries the snapshot
    assert "SECRET ctx" not in body["token"]       # full_context never leaks


def test_post_tokens_unknown_node_is_rejected(tmp_path):
    app = _app(tmp_path)
    project_id, _ = _seed_project_and_node(app)
    client = TestClient(app)
    resp = client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": [{"id": "ghost-node", "include_history": False}],
        "ttl_seconds": 3600,
    })
    assert resp.status_code == 404


def _issue_token_from(app, project_id, node_id, recipient="bruno"):
    """Issue a token on `app` and return (serialized_token, issuer_public_key)."""
    client = TestClient(app)
    token = client.post("/tokens", json={
        "recipient_id": recipient, "project_id": project_id,
        "node_ids": [{"id": node_id, "include_history": False}],
        "ttl_seconds": 3600,
    }).json()["token"]
    pub = client.get("/identity/anna").json()["public_key"]
    return token, pub


def test_post_inbox_accepts_valid_token(tmp_path):
    issuer = _app(tmp_path, owner="anna", name="anna")
    project_id, node_id = _seed_project_and_node(issuer, owner="anna")
    token, pub = _issue_token_from(issuer, project_id, node_id)

    recipient = _app(tmp_path, owner="bruno", name="bruno")
    rclient = TestClient(recipient)
    resp = rclient.post("/inbox/tokens", json={"token": token, "issuer_public_key": pub})
    assert resp.status_code == 201, resp.text
    assert resp.json()["token_id"]


def test_post_inbox_rejects_tampered_token(tmp_path):
    issuer = _app(tmp_path, owner="anna", name="anna")
    project_id, node_id = _seed_project_and_node(issuer, owner="anna")
    token, pub = _issue_token_from(issuer, project_id, node_id)
    tampered = token.replace("public summary", "tampered summary")

    recipient = _app(tmp_path, owner="bruno", name="bruno")
    rclient = TestClient(recipient)
    resp = rclient.post("/inbox/tokens", json={"token": tampered, "issuer_public_key": pub})
    assert resp.status_code == 422


def _receive(recipient_app, token, pub):
    return TestClient(recipient_app).post(
        "/inbox/tokens", json={"token": token, "issuer_public_key": pub}
    ).json()["token_id"]


def test_get_shared_returns_verified_subgraph(tmp_path):
    issuer = _app(tmp_path, owner="anna", name="anna")
    project_id, node_id = _seed_project_and_node(issuer, owner="anna")
    token, pub = _issue_token_from(issuer, project_id, node_id)
    recipient = _app(tmp_path, owner="bruno", name="bruno")
    token_id = _receive(recipient, token, pub)

    resp = TestClient(recipient).get(f"/shared/{token_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issuer_id"] == "anna"
    assert body["project_summary"] == "public summary"
    assert body["wiki_page_ids"] == []
    assert body["nodes"][0]["states"][0]["content"] == "pH matters"


def test_get_shared_unknown_token_404(tmp_path):
    app = _app(tmp_path, owner="bruno", name="bruno")
    assert TestClient(app).get("/shared/nope").status_code == 404


def test_get_shared_rejects_expired(tmp_path):
    # issue with a 1-second TTL, then the stored token is past expiry at read time
    issuer = _app(tmp_path, owner="anna", name="anna")
    project_id, node_id = _seed_project_and_node(issuer, owner="anna")
    client = TestClient(issuer)
    token = client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": [{"id": node_id, "include_history": False}],
        "ttl_seconds": 1,
    }).json()["token"]
    pub = client.get("/identity/anna").json()["public_key"]
    recipient = _app(tmp_path, owner="bruno", name="bruno")
    # receive immediately (still valid), then it expires before /shared
    import time
    token_id = _receive(recipient, token, pub)
    time.sleep(2)
    assert TestClient(recipient).get(f"/shared/{token_id}").status_code == 403


def test_get_shared_missing_issuer_key_403(tmp_path):
    # a token stored without registering the issuer's public key cannot be re-verified → 403
    from memorygraph.auth.token import TokenStore, deserialize

    issuer = _app(tmp_path, owner="anna", name="anna")
    project_id, node_id = _seed_project_and_node(issuer, owner="anna")
    token_str, _ = _issue_token_from(issuer, project_id, node_id)

    recipient = _app(tmp_path, owner="bruno", name="bruno")
    tok = deserialize(token_str)
    recipient.state.manager.submit("bruno", lambda s: TokenStore(s._conn).save(tok))
    assert TestClient(recipient).get(f"/shared/{tok.id}").status_code == 403


def test_post_inbox_rejects_malformed_token(tmp_path):
    # a structurally broken token string fails at deserialize → 422 "malformed token"
    app = _app(tmp_path, owner="bruno", name="bruno")
    resp = TestClient(app).post(
        "/inbox/tokens", json={"token": "not-a-valid-token", "issuer_public_key": "x"}
    )
    assert resp.status_code == 422
    assert "malformed" in resp.json()["detail"]
