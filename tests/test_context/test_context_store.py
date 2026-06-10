# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from memorygraph.context import ContextStore
from memorygraph.context.project import ProjectStore
from memorygraph.context.wiki import WikiStore
from memorygraph.context.documents import DocumentStore


@pytest.fixture
def ctx(tmp_path):
    return ContextStore(str(tmp_path / "test.kuzu"))


def _make_node(ctx):
    """Helper: create a NodeEntity through ContextStore's shared connection."""
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ctx._conn.execute(
        "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
        "created_at: $ts, is_deleted: false})",
        {"id": nid, "ts": now},
    )
    return nid


class TestContextStoreInit:
    def test_projects_is_project_store(self, ctx):
        assert isinstance(ctx.projects, ProjectStore)

    def test_wiki_is_wiki_store(self, ctx):
        assert isinstance(ctx.wiki, WikiStore)

    def test_documents_is_document_store(self, ctx):
        assert isinstance(ctx.documents, DocumentStore)

    def test_sub_stores_share_connection(self, ctx):
        # Verify that data written by one sub-store is visible to the others
        # by creating a Project and checking it is readable from the same connection
        p = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        result = ctx._conn.execute(
            "MATCH (p:Project) WHERE p.id = $pid RETURN p.title",
            {"pid": p.id},
        )
        assert result.get_next()[0] == "T"


class TestAttachNode:
    def test_creates_belongs_to_edge(self, ctx):
        node_id = _make_node(ctx)
        project = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        ctx.attach_node(node_id, project.id)
        result = ctx._conn.execute(
            "MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1

    def test_multiple_nodes_can_belong_to_same_project(self, ctx):
        n1 = _make_node(ctx)
        n2 = _make_node(ctx)
        project = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        ctx.attach_node(n1, project.id)
        ctx.attach_node(n2, project.id)
        result = ctx._conn.execute(
            "MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project) "
            "WHERE p.id = $pid RETURN count(*) AS c",
            {"pid": project.id},
        )
        assert result.get_next()[0] == 2
