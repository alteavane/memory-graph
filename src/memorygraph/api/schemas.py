# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pydantic request/response models for the Phase 3c REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IdentityResponse(BaseModel):
    """Public identity view — never carries the private key."""

    user_id: str
    public_key: str


class ConsentResponse(BaseModel):
    """A user's network-sharing consent flags."""

    discoverable: bool
    share_deadends: bool
    share_triggers: bool
    auto_propose: bool


class ConsentUpdate(BaseModel):
    """Partial consent update — omitted flags keep their current value."""

    discoverable: bool | None = None
    share_deadends: bool | None = None
    share_triggers: bool | None = None
    auto_propose: bool | None = None


class NodeSelection(BaseModel):
    """One node to share, with whether to embed its full history."""

    id: str
    include_history: bool = False


class TokenIssueRequest(BaseModel):
    """Body of POST /tokens — what to share and with whom."""

    recipient_id: str
    project_id: str
    node_ids: list[NodeSelection]
    wiki_page_ids: list[str] = Field(default_factory=list)
    forkable: bool = False
    ttl_seconds: int = 86400


class TokenIssueResponse(BaseModel):
    """Result of issuing a token: its id and the serialized, signed token."""

    token_id: str
    token: str


class InboxRequest(BaseModel):
    """Body of POST /inbox/tokens — a serialized token plus the issuer's public key (out-of-band)."""

    token: str
    issuer_public_key: str


class InboxResponse(BaseModel):
    """Result of accepting a received token."""

    token_id: str


class SharedResponse(BaseModel):
    """Read-only view of a verified shared subgraph (only what the token embeds)."""

    issuer_id: str
    project_summary: str
    wiki_page_ids: list[str]
    nodes: list[dict]
