# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auth Layer schema — UserIdentity, SubgraphToken, UserNetworkConsent."""

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
    """
    CREATE NODE TABLE IF NOT EXISTS SubgraphToken (
        id              STRING,
        issuer_id       STRING,
        recipient_id    STRING,
        node_ids        STRING,
        project_summary STRING,
        wiki_page_ids   STRING,
        forkable        BOOLEAN,
        expires_at      TIMESTAMP,
        signature       STRING,
        created_at      TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS UserNetworkConsent (
        user_id        STRING,
        discoverable   BOOLEAN,
        share_deadends BOOLEAN,
        share_triggers BOOLEAN,
        auto_propose   BOOLEAN,
        updated_at     TIMESTAMP,
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
