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
        "u1", "Progetto Test", "Obiettivo", "Summary", "FC"
    ).id


@pytest.fixture
def wiki(conn):
    return WikiStore(conn)


# ── create_wiki_page ──────────────────────────────────────────────────────────

class TestCreateWikiPage:
    def test_returns_wiki_entity(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "Titolo", "Contenuto", "Prima versione")
        assert entity.id is not None
        assert entity.title == "Titolo"
        assert entity.project_id == project_id
        assert entity.user_id == "u1"
        assert entity.is_deleted is False

    def test_creates_first_state_version_1(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "Contenuto v1", "Creazione")
        history = wiki.get_wiki_history(entity.id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].content == "Contenuto v1"
        assert history[0].summary == "Creazione"
        assert history[0].wiki_id == entity.id

    def test_each_page_has_unique_id(self, wiki, project_id):
        w1 = wiki.create_wiki_page("u1", project_id, "T1", "C", "S")
        w2 = wiki.create_wiki_page("u1", project_id, "T2", "C", "S")
        assert w1.id != w2.id


# ── update_wiki_page ──────────────────────────────────────────────────────────

class TestUpdateWikiPage:
    def test_increments_version(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        state = wiki.update_wiki_page(entity.id, "v2", "Aggiunto paragrafo")
        assert state.version == 2
        assert state.content == "v2"
        assert state.summary == "Aggiunto paragrafo"

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
