# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 3c §8 invariants enforced through the HTTP surface."""
from fastapi.testclient import TestClient

from memorygraph.api.app import create_app
from memorygraph.context.project import ProjectStore
from memorygraph.graph.models import NodeType


def _instance(tmp_path, owner, name):
    return create_app(owner_id=owner, db_path=str(tmp_path / f"{name}.kuzu"))


def _seed(app, owner, *, summary="public summary", full_context="SECRET_FULL_CONTEXT", trigger="SECRET_TRIGGER"):
    mgr = app.state.manager

    def op(store):
        proj = ProjectStore(store._conn).create_project(owner, "T", "obj", summary, full_context)
        node = store.create_node(owner, NodeType.HYPOTHESIS, "content", 0.6, trigger)
        dead = store.create_node(owner, NodeType.DEAD_END, "rejected", 0.1, "falsified")
        return proj.id, node.id, dead.id

    return mgr.submit(owner, op)


def _issue(app, project_id, node_ids):
    client = TestClient(app)
    token = client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": node_ids, "ttl_seconds": 3600,
    }).json()
    pub = client.get("/identity/anna").json()["public_key"]
    return token, pub


def test_full_context_never_in_token_response(tmp_path):
    app = _instance(tmp_path, "anna", "anna")
    project_id, node_id, _ = _seed(app, "anna")
    token, _ = _issue(app, project_id, [{"id": node_id, "include_history": False}])
    assert "SECRET_FULL_CONTEXT" not in token["token"]


def test_private_key_never_in_identity_response(tmp_path):
    app = _instance(tmp_path, "anna", "anna")
    body = TestClient(app).get("/identity/anna").json()
    assert "private_key" not in body
    assert "private" not in str(body).lower()


def test_default_consent_strips_triggers_through_shared(tmp_path):
    anna = _instance(tmp_path, "anna", "anna")
    project_id, node_id, _ = _seed(anna, "anna")
    token, pub = _issue(anna, project_id, [{"id": node_id, "include_history": False}])
    bruno = _instance(tmp_path, "bruno", "bruno")
    bclient = TestClient(bruno)
    token_id = bclient.post("/inbox/tokens", json={"token": token["token"], "issuer_public_key": pub}).json()["token_id"]
    shared = bclient.get(f"/shared/{token_id}").json()
    assert shared["nodes"][0]["states"][0]["trigger"] == ""
    assert "SECRET_TRIGGER" not in str(shared)


def test_default_consent_excludes_deadend_through_tokens(tmp_path):
    app = _instance(tmp_path, "anna", "anna")
    project_id, node_id, dead_id = _seed(app, "anna")
    token, _ = _issue(app, project_id, [
        {"id": node_id, "include_history": False},
        {"id": dead_id, "include_history": False},
    ])
    assert dead_id not in token["token"]


def test_project_summary_frozen_through_api(tmp_path):
    app = _instance(tmp_path, "anna", "anna")
    project_id, node_id, _ = _seed(app, "anna")
    token, _ = _issue(app, project_id, [{"id": node_id, "include_history": False}])
    # edit the project summary after issuance
    app.state.manager.submit("anna", lambda s: ProjectStore(s._conn).update_project(project_id, summary="EDITED"))
    assert "public summary" in token["token"]
    assert "EDITED" not in token["token"]


def test_wiki_page_ids_empty_unless_provided(tmp_path):
    app = _instance(tmp_path, "anna", "anna")
    project_id, node_id, _ = _seed(app, "anna")
    token, _ = _issue(app, project_id, [{"id": node_id, "include_history": False}])
    assert '"wiki_page_ids":[]' in token["token"]
