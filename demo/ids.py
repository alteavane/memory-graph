# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""VHS demo helper: prints the UUID of a node/project by reading it from the DB.

Used by the tape to resolve IDs at runtime (avoids hardcoded UUIDs):
    PID=$(uv run python demo/ids.py project)
    HYP=$(uv run python demo/ids.py hyp)
"""
from __future__ import annotations

import os
import sys

import kuzu

_QUERIES = {
    "project": "MATCH (p:Project) WHERE p.user_id = 'marco' RETURN p.id LIMIT 1",
    "hyp": (
        "MATCH (n:NodeEntity)-[:HAS_STATE]->(s:NodeState) "
        "WHERE s.content STARTS WITH 'Protonation' RETURN n.id LIMIT 1"
    ),
}


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else "project"
    conn = kuzu.Connection(kuzu.Database(os.environ["MEMORYGRAPH_DB_PATH"]))
    result = conn.execute(_QUERIES[what])
    print(result.get_next()[0])


if __name__ == "__main__":
    main()
