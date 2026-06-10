# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ed25519 signing primitives — pure functions, no I/O."""
from __future__ import annotations

import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_b64, public_key_b64) for a fresh Ed25519 identity."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_b64 = base64.b64encode(private.private_bytes_raw()).decode("ascii")
    public_b64 = base64.b64encode(public.public_bytes_raw()).decode("ascii")
    return private_b64, public_b64


def canonical_bytes(payload: dict) -> bytes:
    """Deterministic serialization used as the signed message.

    Sorted keys + compact separators so the bytes are stable across
    processes and languages.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign(payload: dict, private_key_b64: str) -> str:
    """Sign the canonical form of ``payload`` with an Ed25519 private key."""
    private = Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(private_key_b64)
    )
    signature = private.sign(canonical_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def verify(payload: dict, signature_b64: str, public_key_b64: str) -> bool:
    """Return True iff ``signature_b64`` is a valid signature of ``payload``."""
    try:
        public = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64)
        )
        public.verify(base64.b64decode(signature_b64), canonical_bytes(payload))
        return True
    except (InvalidSignature, ValueError):
        return False
