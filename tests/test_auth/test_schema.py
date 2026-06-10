# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import kuzu

from memorygraph.auth.schema import init_auth_schema
from memorygraph.graph.schema import init_schema


def test_init_auth_schema_idempotent(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)
    init_schema(conn)
    init_auth_schema(conn)
    init_auth_schema(conn)  # second call must not raise


def test_user_identity_table_accepts_insert(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)
    init_schema(conn)
    init_auth_schema(conn)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        "CREATE (i:UserIdentity {user_id: 'u1', public_key: 'p', "
        "private_key: 's', created_at: $ts})",
        {"ts": now},
    )
    result = conn.execute(
        "MATCH (i:UserIdentity) WHERE i.user_id = 'u1' RETURN i.public_key"
    )
    assert result.get_next()[0] == "p"
