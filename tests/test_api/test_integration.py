# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""DoD §9 — full two-instance flow, in-process: issue → transmit → verify → read-only view."""
from fastapi.testclient import TestClient

from memorygraph.api.app import create_app
from memorygraph.context.project import ProjectStore
from memorygraph.graph.models import NodeType


def _instance(tmp_path, owner):
    return create_app(owner_id=owner, db_path=str(tmp_path / f"{owner}.kuzu"))


def test_two_instance_share_flow(tmp_path):
    # --- Anna's instance: a project + a node ---
    anna = _instance(tmp_path, "anna")
    anna_client = TestClient(anna)

    def seed(store):
        proj = ProjectStore(store._conn).create_project(
            "anna", "Viral entry", "study ACE2", "Study of viral entry — focus on ACE2", "PRIVATE full context"
        )
        node = store.create_node("anna", NodeType.HYPOTHESIS, "pH drives entry", 0.6, "obs")
        return proj.id, node.id

    project_id, node_id = anna.state.manager.submit("anna", seed)

    # --- Bruno's instance ---
    bruno = _instance(tmp_path, "bruno")
    bruno_client = TestClient(bruno)

    # 1. Bruno fetches Anna's public key
    anna_pub = anna_client.get("/identity/anna").json()["public_key"]

    # 2. Anna issues a signed token
    issued = anna_client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": [{"id": node_id, "include_history": False}], "ttl_seconds": 3600,
    }).json()

    # 3. The token is transmitted; Bruno posts it to his inbox
    received = bruno_client.post("/inbox/tokens", json={
        "token": issued["token"], "issuer_public_key": anna_pub,
    })
    assert received.status_code == 201
    token_id = received.json()["token_id"]

    # 4. Bruno reads the verified shared subgraph
    shared = bruno_client.get(f"/shared/{token_id}")
    assert shared.status_code == 200
    body = shared.json()
    assert body["issuer_id"] == "anna"
    assert body["project_summary"] == "Study of viral entry — focus on ACE2"
    assert body["nodes"][0]["states"][0]["content"] == "pH drives entry"
    # Bruno never sees Anna's private context
    assert "PRIVATE full context" not in str(body)


def test_two_instance_tampered_token_is_refused_at_shared(tmp_path):
    anna = _instance(tmp_path, "anna")
    anna_client = TestClient(anna)

    def seed(store):
        proj = ProjectStore(store._conn).create_project("anna", "T", "o", "summary", "ctx")
        node = store.create_node("anna", NodeType.HYPOTHESIS, "x", 0.6, "t")
        return proj.id, node.id

    project_id, node_id = anna.state.manager.submit("anna", seed)
    anna_pub = anna_client.get("/identity/anna").json()["public_key"]
    issued = anna_client.post("/tokens", json={
        "recipient_id": "bruno", "project_id": project_id,
        "node_ids": [{"id": node_id, "include_history": False}], "ttl_seconds": 3600,
    }).json()

    bruno = _instance(tmp_path, "bruno")
    bruno_client = TestClient(bruno)
    # a tampered token is refused already at the inbox
    tampered = issued["token"].replace("summary", "TAMPERED")
    assert bruno_client.post("/inbox/tokens", json={
        "token": tampered, "issuer_public_key": anna_pub,
    }).status_code == 422
