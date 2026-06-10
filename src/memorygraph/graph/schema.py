# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import kuzu

_SCHEMA_STATEMENTS = [
    """
    CREATE NODE TABLE IF NOT EXISTS NodeEntity (
        id STRING,
        user_id STRING,
        type STRING,
        created_at TIMESTAMP,
        is_deleted BOOLEAN,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS NodeState (
        id STRING,
        version INT64,
        content STRING,
        confidence DOUBLE,
        trigger STRING,
        created_at TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS HAS_STATE (
        FROM NodeEntity TO NodeState
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS CONNECTS (
        FROM NodeEntity TO NodeEntity,
        edge_id STRING,
        type STRING,
        confidence DOUBLE,
        invalidated_at TIMESTAMP
    )
    """,
]


def init_schema(conn: kuzu.Connection) -> None:
    """Create all Kuzu tables if they don't exist. Idempotent."""
    for stmt in _SCHEMA_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
