# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu
import pytest

from memorygraph.context.documents import DocumentStore
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
def docs(conn):
    return DocumentStore(conn)


def _make_node(conn):
    """Helper: create a NodeEntity in the DB for cross-layer tests."""
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
        "created_at: $ts, is_deleted: false})",
        {"id": nid, "ts": now},
    )
    return nid


# ── add_document ──────────────────────────────────────────────────────────────

class TestAddDocument:
    def test_returns_document_with_required_fields(self, docs):
        d = docs.add_document("u1", "Paper on pH")
        assert d.id is not None
        assert d.user_id == "u1"
        assert d.title == "Paper on pH"
        assert d.doi is None
        assert d.url is None
        assert d.authors is None
        assert d.pub_date is None

    def test_returns_document_with_all_fields(self, docs):
        d = docs.add_document(
            "u1", "Complete paper",
            doi="10.1000/xyz123",
            url="https://example.com/paper",
            authors="Rossi M, Bianchi A",
            pub_date="2024-01-15",
        )
        assert d.doi == "10.1000/xyz123"
        assert d.url == "https://example.com/paper"
        assert d.authors == "Rossi M, Bianchi A"
        assert d.pub_date == "2024-01-15"

    def test_each_document_unique_id(self, docs):
        d1 = docs.add_document("u1", "P1")
        d2 = docs.add_document("u1", "P2")
        assert d1.id != d2.id


# ── get_document ──────────────────────────────────────────────────────────────

class TestGetDocument:
    def test_returns_document(self, docs):
        d = docs.add_document("u1", "Paper", doi="10.1/x")
        result = docs.get_document(d.id)
        assert result is not None
        assert result.id == d.id
        assert result.doi == "10.1/x"

    def test_optional_fields_round_trip_as_none(self, docs):
        d = docs.add_document("u1", "Paper without metadata")
        result = docs.get_document(d.id)
        assert result.doi is None
        assert result.url is None
        assert result.authors is None
        assert result.pub_date is None

    def test_returns_none_for_missing(self, docs):
        assert docs.get_document("nonexistent") is None


# ── list_documents ────────────────────────────────────────────────────────────

class TestListDocuments:
    def test_returns_all_documents_for_user(self, docs):
        docs.add_document("u1", "P1")
        docs.add_document("u1", "P2")
        assert len(docs.list_documents("u1")) == 2

    def test_isolates_by_user_id(self, docs):
        docs.add_document("u1", "P1")
        docs.add_document("u2", "P2")
        assert len(docs.list_documents("u1")) == 1
        assert len(docs.list_documents("u2")) == 1

    def test_empty_list_for_user_without_documents(self, docs):
        assert docs.list_documents("nobody") == []


# ── reference_document ────────────────────────────────────────────────────────

class TestReferenceDocument:
    def test_creates_references_doc_edge(self, docs, conn):
        node_id = _make_node(conn)
        d = docs.add_document("u1", "Paper")
        docs.reference_document(node_id, d.id)
        result = conn.execute(
            "MATCH (n:NodeEntity)-[:REFERENCES_DOC]->(d:DocumentIndex) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1

    def test_idempotent_double_call(self, docs, conn):
        node_id = _make_node(conn)
        d = docs.add_document("u1", "Paper")
        docs.reference_document(node_id, d.id)
        docs.reference_document(node_id, d.id)   # second call
        result = conn.execute(
            "MATCH (n:NodeEntity)-[:REFERENCES_DOC]->(d:DocumentIndex) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1
