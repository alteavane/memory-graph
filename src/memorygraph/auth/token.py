# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SubgraphToken: build → sign → serialize/deserialize → verify, plus persistence.

   Datetimes are naive UTC (tzinfo stripped) throughout, matching the Kuzu TIMESTAMP
   convention used by every store in this codebase.
   """
from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from memorygraph.auth.consent import ConsentStore
from memorygraph.auth.crypto import sign, verify
from memorygraph.auth.identity import IdentityStore
from memorygraph.context.project import ProjectStore
from memorygraph.graph.models import NodeType, SubgraphToken
from memorygraph.graph.store import GraphStore


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


def _materialize_states(states, *, share_triggers: bool) -> list[dict]:
    """Turn NodeState objects into JSON-ready dicts; strip triggers when consent forbids them."""
    return [
        {
            "version": s.version,
            "content": s.content,
            "confidence": s.confidence,
            "trigger": s.trigger if share_triggers else "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in states
    ]


def build_token(
    *,
    graph_store: GraphStore,
    identity_store: IdentityStore,
    consent_store: ConsentStore,
    project_store: ProjectStore,
    issuer_id: str,
    recipient_id: str,
    project_id: str,
    node_ids: list[dict],
    wiki_page_ids: Sequence[str] = (),
    forkable: bool = False,
    ttl_seconds: int = 86400,
    now: datetime | None = None,
) -> SubgraphToken:
    """Materialize the issuer's selected nodes, snapshot the project summary, apply consent, and sign.

    node_ids is a list of {"id": str, "include_history": bool}. Nodes that are not the issuer's
    raise ValueError. With share_deadends=False, DeadEnd nodes are dropped; with share_triggers=False,
    every trigger is stripped. project_summary is copied as an immutable snapshot.
    """
    identity = identity_store.get_identity(issuer_id, include_private=True)
    if identity is None:
        raise ValueError(f"no identity for issuer {issuer_id}")

    summary = project_store.get_project_summary(project_id)
    if summary is None:
        raise ValueError(f"project {project_id} not found")

    consent = consent_store.get_consent(issuer_id)
    graph = graph_store.get_graph(issuer_id)
    index = {entity.id: (entity, state) for entity, state in graph["nodes"]}

    materialized: list[dict] = []
    for sel in node_ids:
        nid = sel["id"]
        include_history = bool(sel.get("include_history", False))
        if nid not in index:
            raise ValueError(f"node {nid} not found for issuer {issuer_id}")
        entity, latest = index[nid]
        if entity.type == NodeType.DEAD_END and not consent.share_deadends:
            continue  # consent: DeadEnd excluded
        states = (
            graph_store.get_node_history(nid) if include_history else [latest]
        )
        materialized.append({
            "id": nid,
            "type": entity.type.value,
            "include_history": include_history,
            "states": _materialize_states(states, share_triggers=consent.share_triggers),
        })

    issued_at = now or datetime.now(timezone.utc).replace(tzinfo=None)
    token = SubgraphToken(
        id=str(uuid.uuid4()),
        issuer_id=issuer_id,
        recipient_id=recipient_id,
        nodes=materialized,
        project_summary=summary["summary"],
        wiki_page_ids=list(wiki_page_ids),
        forkable=forkable,
        expires_at=issued_at + timedelta(seconds=ttl_seconds),
        signature="",
        created_at=issued_at,
    )
    signature = sign(_token_payload(token), identity.private_key)
    token.signature = signature
    return token
