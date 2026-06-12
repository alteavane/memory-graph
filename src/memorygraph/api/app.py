# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI app factory + endpoints for the federated Phase 3c REST API.

One instance serves one owner. Every DB touch goes through the WriterManager so
the single Kuzu connection is never used concurrently.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException

from memorygraph.api.schemas import ConsentResponse, ConsentUpdate, IdentityResponse
from memorygraph.api.writer import WriterManager
from memorygraph.auth.consent import ConsentStore
from memorygraph.auth.identity import IdentityStore
from memorygraph.auth.token import TokenStore
from memorygraph.context.project import ProjectStore
from memorygraph.graph.store import GraphStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bundle(store: GraphStore) -> SimpleNamespace:
    """Build all stores for an owner from a single GraphStore connection."""
    conn = store._conn
    return SimpleNamespace(
        graph=store,
        identity=IdentityStore(conn),
        consent=ConsentStore(conn),
        project=ProjectStore(conn),
        token=TokenStore(conn),
    )


def create_app(owner_id: str, db_path: str) -> FastAPI:
    """Build a FastAPI app for one owner. Auto-provisions the owner's identity."""
    manager = WriterManager(lambda _uid: db_path)

    def _ensure_identity(store: GraphStore) -> None:
        identity = IdentityStore(store._conn)
        if identity.get_public_key(owner_id) is None:
            identity.create_identity(owner_id)

    manager.submit(owner_id, _ensure_identity)

    app = FastAPI(title="MemoryGraph instance API")
    app.state.owner_id = owner_id
    app.state.manager = manager

    @app.get("/identity/{user_id}", response_model=IdentityResponse)
    def get_identity(user_id: str) -> IdentityResponse:
        """Return a user's Ed25519 public key (public endpoint). 404 if unknown."""
        public_key = manager.submit(
            owner_id, lambda s: _bundle(s).identity.get_public_key(user_id)
        )
        if public_key is None:
            raise HTTPException(status_code=404, detail=f"no identity for {user_id}")
        return IdentityResponse(user_id=user_id, public_key=public_key)

    def _consent_response(store: GraphStore) -> ConsentResponse:
        consent = _bundle(store).consent.get_consent(owner_id)
        return ConsentResponse(
            discoverable=consent.discoverable,
            share_deadends=consent.share_deadends,
            share_triggers=consent.share_triggers,
            auto_propose=consent.auto_propose,
        )

    @app.get("/consent", response_model=ConsentResponse)
    def get_consent() -> ConsentResponse:
        """Read the owner's network-sharing consent flags."""
        return manager.submit(owner_id, _consent_response)

    @app.put("/consent", response_model=ConsentResponse)
    def put_consent(update: ConsentUpdate) -> ConsentResponse:
        """Update one or more of the owner's consent flags (omitted flags unchanged)."""

        def op(store: GraphStore) -> ConsentResponse:
            _bundle(store).consent.set_consent(
                owner_id,
                discoverable=update.discoverable,
                share_deadends=update.share_deadends,
                share_triggers=update.share_triggers,
                auto_propose=update.auto_propose,
            )
            return _consent_response(store)

        return manager.submit(owner_id, op)

    return app
