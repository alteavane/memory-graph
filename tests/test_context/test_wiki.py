# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import kuzu
import pytest

from memorygraph.context.schema import init_context_schema
from memorygraph.context.wiki import WikiStore
from memorygraph.context.project import ProjectStore
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_context_schema(c)
    return c


@pytest.fixture
def project_id(conn):
    return ProjectStore(conn).create_project(
        "u1", "Test Project", "Objective", "Summary", "FC"
    ).id


@pytest.fixture
def wiki(conn):
    return WikiStore(conn)


# ── create_wiki_page ──────────────────────────────────────────────────────────

class TestCreateWikiPage:
    def test_returns_wiki_entity(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "Title", "Content", "First version")
        assert entity.id is not None
        assert entity.title == "Title"
        assert entity.project_id == project_id
        assert entity.user_id == "u1"
        assert entity.is_deleted is False

    def test_creates_first_state_version_1(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "Content v1", "Creation")
        history = wiki.get_wiki_history(entity.id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].content == "Content v1"
        assert history[0].summary == "Creation"
        assert history[0].wiki_id == entity.id

    def test_each_page_has_unique_id(self, wiki, project_id):
        w1 = wiki.create_wiki_page("u1", project_id, "T1", "C", "S")
        w2 = wiki.create_wiki_page("u1", project_id, "T2", "C", "S")
        assert w1.id != w2.id


# ── update_wiki_page ──────────────────────────────────────────────────────────

class TestUpdateWikiPage:
    def test_increments_version(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        state = wiki.update_wiki_page(entity.id, "v2", "Added paragraph")
        assert state.version == 2
        assert state.content == "v2"
        assert state.summary == "Added paragraph"

    def test_preserves_previous_states(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        history = wiki.get_wiki_history(entity.id)
        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].content == "v1"
        assert history[1].version == 2
        assert history[1].content == "v2"

    def test_multiple_updates_increment_correctly(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        state3 = wiki.update_wiki_page(entity.id, "v3", "s3")
        assert state3.version == 3
        history = wiki.get_wiki_history(entity.id)
        assert [s.version for s in history] == [1, 2, 3]


# ── get_wiki_history ──────────────────────────────────────────────────────────

class TestGetWikiHistory:
    def test_returns_states_in_version_order(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        history = wiki.get_wiki_history(entity.id)
        assert history[0].version == 1
        assert history[1].version == 2

    def test_returns_empty_for_unknown_wiki(self, wiki):
        assert wiki.get_wiki_history("nonexistent") == []


# ── list_wiki_pages ───────────────────────────────────────────────────────────

class TestListWikiPages:
    def test_returns_latest_state_only(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        pages = wiki.list_wiki_pages(project_id)
        assert len(pages) == 1
        _, state = pages[0]
        assert state.version == 2
        assert state.content == "v2"

    def test_returns_entity_and_state_pair(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "Title", "C", "S")
        pages = wiki.list_wiki_pages(project_id)
        ent, state = pages[0]
        assert ent.title == "Title"
        assert ent.id == entity.id
        assert state.version == 1

    def test_excludes_deleted_pages(self, wiki, project_id, conn):
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        conn.execute(
            "MATCH (w:WikiEntity) WHERE w.id = $id SET w.is_deleted = true",
            {"id": entity.id},
        )
        assert wiki.list_wiki_pages(project_id) == []

    def test_multiple_pages_returned(self, wiki, project_id):
        wiki.create_wiki_page("u1", project_id, "T1", "C1", "S1")
        wiki.create_wiki_page("u1", project_id, "T2", "C2", "S2")
        assert len(wiki.list_wiki_pages(project_id)) == 2


# ── link_to_nodes ─────────────────────────────────────────────────────────────

class TestLinkToNodes:
    def _make_node(self, conn):
        """Helper: create a NodeEntity in the DB for cross-layer tests."""
        import uuid as _uuid
        from datetime import datetime, timezone
        nid = str(_uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute(
            "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
            "created_at: $ts, is_deleted: false})",
            {"id": nid, "ts": now},
        )
        return nid

    def test_creates_wiki_covers_edges(self, wiki, project_id, conn):
        node_id = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [node_id])
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 1

    def test_idempotent_double_call(self, wiki, project_id, conn):
        node_id = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [node_id])
        wiki.link_to_nodes(entity.id, [node_id])   # second call
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 1

    def test_links_multiple_nodes(self, wiki, project_id, conn):
        n1 = self._make_node(conn)
        n2 = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [n1, n2])
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 2

    def test_empty_list_is_noop(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [])   # must complete without errors
