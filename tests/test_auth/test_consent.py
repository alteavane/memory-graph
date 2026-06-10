# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import kuzu
import pytest

from memorygraph.auth.consent import ConsentStore
from memorygraph.auth.schema import init_auth_schema
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_auth_schema(c)
    return c


def test_get_consent_defaults_all_false_and_unpersisted(conn):
    store = ConsentStore(conn)
    consent = store.get_consent("u1")
    assert consent.user_id == "u1"
    assert consent.discoverable is False
    assert consent.share_deadends is False
    assert consent.share_triggers is False
    assert consent.auto_propose is False
    assert consent.updated_at is None
    # default read must not write a row
    result = conn.execute("MATCH (c:UserNetworkConsent) RETURN count(c)")
    assert result.get_next()[0] == 0


def test_set_consent_persists_and_reads_back(conn):
    store = ConsentStore(conn)
    updated = store.set_consent("u1", share_deadends=True, share_triggers=True)
    assert updated.share_deadends is True
    assert updated.share_triggers is True
    assert updated.discoverable is False  # untouched → stays default
    assert updated.updated_at is not None
    reread = store.get_consent("u1")
    assert reread.share_deadends is True
    assert reread.share_triggers is True


def test_set_consent_partial_update_keeps_existing(conn):
    store = ConsentStore(conn)
    first = store.set_consent("u1", discoverable=True, share_deadends=True)
    second = store.set_consent("u1", share_deadends=False)  # only flip one flag
    assert second.updated_at >= first.updated_at
    final = store.get_consent("u1")
    assert final.discoverable is True       # preserved
    assert final.share_deadends is False    # updated
