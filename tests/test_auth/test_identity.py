# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import kuzu
import pytest

from memorygraph.auth.crypto import sign, verify
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


def test_create_identity_returns_usable_keys(conn):
    store = IdentityStore(conn)
    identity = store.create_identity("u1")
    assert identity.user_id == "u1"
    assert identity.public_key
    assert identity.private_key
    signature = sign({"x": 1}, identity.private_key)
    assert verify({"x": 1}, signature, identity.public_key) is True


def test_create_identity_duplicate_raises(conn):
    store = IdentityStore(conn)
    store.create_identity("u1")
    with pytest.raises(ValueError, match="already exists"):
        store.create_identity("u1")
