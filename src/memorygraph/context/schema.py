# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Context Layer schema — Project, WikiEntity, WikiState, DocumentIndex."""

import kuzu

_CONTEXT_SCHEMA_STATEMENTS = [
    """
    CREATE NODE TABLE IF NOT EXISTS Project (
        id           STRING,
        user_id      STRING,
        title        STRING,
        objective    STRING,
        summary      STRING,
        full_context STRING,
        created_at   TIMESTAMP,
        updated_at   TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS WikiEntity (
        id         STRING,
        user_id    STRING,
        project_id STRING,
        title      STRING,
        created_at TIMESTAMP,
        is_deleted BOOLEAN,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS WikiState (
        id         STRING,
        version    INT64,
        content    STRING,
        summary    STRING,
        created_at TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS DocumentIndex (
        id         STRING,
        user_id    STRING,
        title      STRING,
        doi        STRING,
        url        STRING,
        authors    STRING,
        pub_date   STRING,
        created_at TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS WIKI_HAS_STATE (
        FROM WikiEntity TO WikiState
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS BELONGS_TO (
        FROM NodeEntity TO Project
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS WIKI_COVERS (
        FROM WikiEntity TO NodeEntity
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS REFERENCES_DOC (
        FROM NodeEntity TO DocumentIndex
    )
    """,
]


def init_context_schema(conn: kuzu.Connection) -> None:
    """Create the context layer tables. Idempotent. Must be called after init_schema()."""
    for stmt in _CONTEXT_SCHEMA_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
