# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SubgraphToken: build → sign → serialize/deserialize → verify, plus persistence.

   Datetimes are naive UTC (tzinfo stripped) throughout, matching the Kuzu TIMESTAMP
   convention used by every store in this codebase.
   """
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from memorygraph.auth.crypto import verify
from memorygraph.graph.models import SubgraphToken


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of verify_token. ok is the only thing callers must branch on; reason aids debugging."""

    ok: bool
    reason: str | None = None


def _token_payload(token: SubgraphToken) -> dict:
    """The canonical payload used for signing and verification: every field except the signature, timestamps as ISO strings."""
    return {
        "id": token.id,
        "issuer_id": token.issuer_id,
        "recipient_id": token.recipient_id,
        "nodes": list(token.nodes),
        "project_summary": token.project_summary,
        "wiki_page_ids": list(token.wiki_page_ids),
        "forkable": token.forkable,
        "expires_at": token.expires_at.isoformat(),
        "created_at": token.created_at.isoformat(),
    }


def serialize(token: SubgraphToken) -> str:
    """Serialize a token to a deterministic, self-contained JSON string (payload + signature)."""
    payload = _token_payload(token)
    payload["signature"] = token.signature
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deserialize(data: str) -> SubgraphToken:
    """Parse a serialized token back into a SubgraphToken. Inverse of serialize()."""
    d = json.loads(data)
    return SubgraphToken(
        id=d["id"],
        issuer_id=d["issuer_id"],
        recipient_id=d["recipient_id"],
        nodes=d["nodes"],
        project_summary=d["project_summary"],
        wiki_page_ids=d["wiki_page_ids"],
        forkable=d["forkable"],
        expires_at=datetime.fromisoformat(d["expires_at"]),
        signature=d["signature"],
        created_at=datetime.fromisoformat(d["created_at"]),
    )


def verify_token(
    token: SubgraphToken, issuer_public_key: str, *, now: datetime
) -> VerifyResult:
    """Verify expiry then Ed25519 signature with the issuer's public key. Never raises.

    A token observed exactly at its expiry instant (now == expires_at) is accepted.
    """
    try:
        if now > token.expires_at:
            return VerifyResult(ok=False, reason="expired")
        if not verify(_token_payload(token), token.signature, issuer_public_key):
            return VerifyResult(ok=False, reason="bad_signature")
    except (ValueError, TypeError):
        return VerifyResult(ok=False, reason="bad_signature")
    return VerifyResult(ok=True, reason=None)
