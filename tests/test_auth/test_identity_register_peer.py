# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import kuzu
import pytest

from memorygraph.auth.identity import IdentityStore
from memorygraph.auth.schema import init_auth_schema
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_auth_schema(c)
    return c


def test_register_peer_persists_public_key_only(conn):
    store = IdentityStore(conn)
    store.register_peer("anna", "PUBKEY_ANNA")
    assert store.get_public_key("anna") == "PUBKEY_ANNA"
    identity = store.get_identity("anna", include_private=True)
    assert identity is not None
    assert identity.private_key == ""        # peer has no private key here


def test_register_peer_is_idempotent_upsert(conn):
    store = IdentityStore(conn)
    store.register_peer("anna", "OLD")
    store.register_peer("anna", "NEW")        # second call updates, does not raise
    assert store.get_public_key("anna") == "NEW"
    result = conn.execute("MATCH (i:UserIdentity) RETURN count(i)")
    assert result.get_next()[0] == 1          # still exactly one row
