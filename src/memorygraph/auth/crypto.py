# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ed25519 signing primitives — pure functions, no I/O."""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)


def generate_keypair() -> tuple[str, str]:
    """Return (private_key_b64, public_key_b64) for a fresh Ed25519 identity."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_b64 = base64.b64encode(private.private_bytes_raw()).decode("ascii")
    public_b64 = base64.b64encode(public.public_bytes_raw()).decode("ascii")
    return private_b64, public_b64
