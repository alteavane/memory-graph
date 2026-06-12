# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from fastapi.testclient import TestClient

from memorygraph.api.app import create_app
from memorygraph.api.writer import WriterManager  # noqa: F401  (used indirectly)
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
