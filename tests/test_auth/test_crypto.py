# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import base64

from memorygraph.auth.crypto import generate_keypair


def test_generate_keypair_returns_distinct_base64():
    private_key, public_key = generate_keypair()
    assert private_key != public_key
    # Ed25519 raw keys are 32 bytes each
    assert len(base64.b64decode(private_key)) == 32
    assert len(base64.b64decode(public_key)) == 32


def test_generate_keypair_is_random():
    assert generate_keypair()[0] != generate_keypair()[0]


from memorygraph.auth.crypto import canonical_bytes


def test_canonical_bytes_is_key_order_independent():
    a = canonical_bytes({"b": 1, "a": 2})
    b = canonical_bytes({"a": 2, "b": 1})
    assert a == b


def test_canonical_bytes_is_compact_and_sorted():
    assert canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
