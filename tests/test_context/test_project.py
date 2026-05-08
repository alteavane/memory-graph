# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import time

import kuzu
import pytest

from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_context_schema(c)
    return c


@pytest.fixture
def store(conn):
    return ProjectStore(conn)


# ── create_project ────────────────────────────────────────────────────────────

class TestCreateProject:
    def test_returns_project_with_all_fields(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary", "FullCtx")
        assert p.id is not None
        assert p.user_id == "u1"
        assert p.title == "Titolo"
        assert p.objective == "Obiettivo"
        assert p.summary == "Summary"
        assert p.full_context == "FullCtx"

    def test_created_at_equals_updated_at_on_creation(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC")
        assert p.created_at == p.updated_at

    def test_each_project_unique_id(self, store):
        p1 = store.create_project("u1", "T1", "O", "S", "FC")
        p2 = store.create_project("u1", "T2", "O", "S", "FC")
        assert p1.id != p2.id


# ── get_project ───────────────────────────────────────────────────────────────

class TestGetProject:
    def test_returns_none_for_missing(self, store):
        assert store.get_project("nonexistent") is None

    def test_default_strips_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "private")
        result = store.get_project(p.id)
        assert result is not None
        assert result.full_context == ""

    def test_agent_context_returns_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "private")
        result = store.get_project(p.id, agent_context=True)
        assert result is not None
        assert result.full_context == "private"

    def test_public_fields_always_present(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary pub", "FC")
        result = store.get_project(p.id)
        assert result.title == "Titolo"
        assert result.summary == "Summary pub"


# ── get_project_summary ───────────────────────────────────────────────────────

class TestGetProjectSummary:
    def test_returns_dict_with_public_fields(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary", "private")
        s = store.get_project_summary(p.id)
        assert s is not None
        assert s["id"] == p.id
        assert s["title"] == "Titolo"
        assert s["objective"] == "Obiettivo"
        assert s["summary"] == "Summary"

    def test_full_context_not_in_dict(self, store):
        p = store.create_project("u1", "T", "O", "S", "DATI_PRIVATI")
        s = store.get_project_summary(p.id)
        assert "full_context" not in s
        assert "DATI_PRIVATI" not in str(s)

    def test_returns_none_for_missing(self, store):
        assert store.get_project_summary("nonexistent") is None


# ── update_project ────────────────────────────────────────────────────────────

class TestUpdateProject:
    def test_updates_only_specified_fields(self, store):
        p = store.create_project("u1", "Old", "ObjOld", "S", "FC")
        updated = store.update_project(p.id, title="New")
        assert updated.title == "New"
        assert updated.objective == "ObjOld"   # invariato
        assert updated.summary == "S"          # invariato

    def test_updated_at_changes(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC")
        time.sleep(0.01)
        updated = store.update_project(p.id, summary="Nuova summary")
        assert updated.updated_at >= p.updated_at

    def test_raises_for_missing_project(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.update_project("nonexistent", title="X")

    def test_update_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC_old")
        updated = store.update_project(p.id, full_context="FC_new")
        result = store.get_project(updated.id, agent_context=True)
        assert result.full_context == "FC_new"


# ── list_projects ─────────────────────────────────────────────────────────────

class TestListProjects:
    def test_returns_all_projects_for_user(self, store):
        store.create_project("u1", "T1", "O", "S", "FC")
        store.create_project("u1", "T2", "O", "S", "FC")
        assert len(store.list_projects("u1")) == 2

    def test_isolates_by_user_id(self, store):
        store.create_project("u1", "T1", "O", "S", "FC")
        store.create_project("u2", "T2", "O", "S", "FC")
        assert len(store.list_projects("u1")) == 1
        assert len(store.list_projects("u2")) == 1

    def test_default_strips_full_context(self, store):
        store.create_project("u1", "T", "O", "S", "private")
        for p in store.list_projects("u1"):
            assert p.full_context == ""

    def test_agent_context_returns_full_context(self, store):
        store.create_project("u1", "T", "O", "S", "private")
        for p in store.list_projects("u1", agent_context=True):
            assert p.full_context == "private"

    def test_empty_list_for_user_without_projects(self, store):
        assert store.list_projects("nobody") == []


# ── Architectural Invariant ───────────────────────────────────────────────────

class TestArchitecturalInvariant:
    def test_full_context_never_in_public_output(self, store):
        """
        Guardrail architetturale: full_context NON deve mai comparire
        nell'output pubblico di ProjectStore per default.
        Se questo test rompe, qualcuno ha esposto full_context per sbaglio.
        """
        p = store.create_project("u1", "T", "O", "S", "DATI_SEGRETI")

        # get_project senza agent_context
        result = store.get_project(p.id)
        assert result.full_context == ""

        # get_project_summary
        summary = store.get_project_summary(p.id)
        assert "full_context" not in summary
        assert "DATI_SEGRETI" not in str(summary)

        # list_projects senza agent_context
        for proj in store.list_projects("u1"):
            assert proj.full_context == ""
