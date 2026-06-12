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
