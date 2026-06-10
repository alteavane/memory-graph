# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auth Layer schema — UserIdentity (consent/token tables come in 3b)."""

import kuzu

_AUTH_SCHEMA_STATEMENTS = [
    """
    CREATE NODE TABLE IF NOT EXISTS UserIdentity (
        user_id     STRING,
        public_key  STRING,
        private_key STRING,
        created_at  TIMESTAMP,
        PRIMARY KEY (user_id)
    )
    """,
]


def init_auth_schema(conn: kuzu.Connection) -> None:
    """Create the auth layer tables. Idempotent. Must be called after init_schema()."""
    for stmt in _AUTH_SCHEMA_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
