# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import dataclasses
from datetime import datetime

from memorygraph.auth.crypto import generate_keypair, sign
from memorygraph.auth.token import _token_payload, deserialize, serialize, verify_token
from memorygraph.graph.models import SubgraphToken


def _sample_token() -> SubgraphToken:
    now = datetime(2026, 6, 10, 9, 0, 0)
    return SubgraphToken(
        id="t1", issuer_id="anna", recipient_id="bruno",
        nodes=[{
            "id": "n1", "type": "Hypothesis", "include_history": False,
            "states": [{
                "version": 1, "content": "pH matters", "confidence": 0.6,
                "trigger": "", "created_at": "2026-06-10T08:00:00",
            }],
        }],
        project_summary="public summary",
        wiki_page_ids=[],
        forkable=False,
        expires_at=datetime(2026, 6, 11, 9, 0, 0),
        signature="sig-placeholder",
        created_at=now,
    )


def _signed_token(private_key: str) -> SubgraphToken:
    token = _sample_token()
    signature = sign(_token_payload(token), private_key)
    return dataclasses.replace(token, signature=signature)


def test_serialize_deserialize_roundtrip():
    token = _sample_token()
    restored = deserialize(serialize(token))
    assert restored.id == token.id
    assert restored.issuer_id == token.issuer_id
    assert restored.recipient_id == token.recipient_id
    assert restored.nodes == token.nodes
    assert restored.project_summary == token.project_summary
    assert restored.wiki_page_ids == token.wiki_page_ids
    assert restored.forkable == token.forkable
    assert restored.expires_at == token.expires_at
    assert restored.created_at == token.created_at
    assert restored.signature == token.signature


def test_serialize_is_deterministic():
    token = _sample_token()
    assert serialize(token) == serialize(token)


def test_verify_token_accepts_valid_unexpired():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    result = verify_token(token, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is True


def test_verify_token_rejects_expired():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    result = verify_token(token, pub, now=datetime(2026, 6, 12, 9, 0, 0))  # past expires_at
    assert result.ok is False
    assert result.reason == "expired"


def test_verify_token_rejects_tampered_payload():
    priv, pub = generate_keypair()
    token = _signed_token(priv)
    tampered = SubgraphToken(
        id=token.id, issuer_id=token.issuer_id, recipient_id=token.recipient_id,
        nodes=token.nodes, project_summary="TAMPERED summary",  # changed after signing
        wiki_page_ids=token.wiki_page_ids, forkable=token.forkable,
        expires_at=token.expires_at, signature=token.signature, created_at=token.created_at,
    )
    result = verify_token(tampered, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_verify_token_never_raises_on_garbage_signature():
    _, pub = generate_keypair()
    token = _sample_token()  # signature is "sig-placeholder", not valid base64 sig
    result = verify_token(token, pub, now=datetime(2026, 6, 10, 12, 0, 0))
    assert result.ok is False
    assert result.reason == "bad_signature"


def test_verify_token_accepts_at_exact_expiry():
    priv, pub = generate_keypair()
    token = _signed_token(priv)  # expires_at = 2026-06-11T09:00:00
    result = verify_token(token, pub, now=datetime(2026, 6, 11, 9, 0, 0))
    assert result.ok is True
