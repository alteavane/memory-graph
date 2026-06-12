# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""WriterManager — in-process, per-user serialized access to Kuzu.

Kuzu is single-writer per process and GraphStore is thread-unsafe, while FastAPI
runs sync endpoints in a threadpool. Every DB touch (read or write) goes through
submit(), which serializes per user under a lock. This is the ONLY component that
opens a Kuzu connection (project rule).
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

from memorygraph.auth.schema import init_auth_schema
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.store import GraphStore

T = TypeVar("T")


class WriterManager:
    """Maps user_id → a lazily-created GraphStore, serializing every op per user."""

    def __init__(self, db_path_for: Callable[[str], str]) -> None:
        self._db_path_for = db_path_for
        self._writers: dict[str, GraphStore] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def writer(self, user_id: str) -> GraphStore:
        """Return the user's GraphStore, creating it (with all schemas) on first use."""
        with self._guard:
            if user_id not in self._writers:
                store = GraphStore(self._db_path_for(user_id))
                init_context_schema(store._conn)
                init_auth_schema(store._conn)
                self._writers[user_id] = store
            return self._writers[user_id]

    def submit(self, user_id: str, op: Callable[[GraphStore], T]) -> T:
        """Run op against the user's GraphStore, serialized under that user's lock."""
        with self._lock_for(user_id):
            return op(self.writer(user_id))

    def close(self) -> None:
        """Drop all cached writers and locks. Connections are released when garbage-collected."""
        with self._guard:
            self._writers.clear()
            self._locks.clear()

    def _lock_for(self, user_id: str) -> threading.Lock:
        with self._guard:
            if user_id not in self._locks:
                self._locks[user_id] = threading.Lock()
            return self._locks[user_id]
