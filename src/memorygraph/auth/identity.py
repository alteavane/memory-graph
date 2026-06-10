# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from datetime import datetime, timezone

import kuzu

from memorygraph.auth.crypto import generate_keypair
from memorygraph.graph.models import UserIdentity


class IdentityStore:
    """Persists per-user Ed25519 identities. The private key is never exposed unless explicitly requested."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def create_identity(self, user_id: str) -> UserIdentity:
        """Generate and persist a new Ed25519 identity. Raises ValueError if one already exists."""
        if self.get_public_key(user_id) is not None:
            raise ValueError(f"Identity for {user_id} already exists")
        private_key, public_key = generate_keypair()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self._conn.execute(
            "CREATE (i:UserIdentity {user_id: $uid, public_key: $pub, "
            "private_key: $priv, created_at: $ts})",
            {"uid": user_id, "pub": public_key, "priv": private_key, "ts": now},
        )
        return UserIdentity(
            user_id=user_id, public_key=public_key,
            private_key=private_key, created_at=now,
        )

    def get_public_key(self, user_id: str) -> str | None:
        """Return the user's public key, or None if no identity exists."""
        result = self._conn.execute(
            "MATCH (i:UserIdentity) WHERE i.user_id = $uid RETURN i.public_key",
            {"uid": user_id},
        )
        if not result.has_next():
            return None
        return result.get_next()[0]

    def get_identity(
        self, user_id: str, *, include_private: bool = False
    ) -> UserIdentity | None:
        """Return the user's identity, or None. The private key is blank unless include_private=True."""
        result = self._conn.execute(
            "MATCH (i:UserIdentity) WHERE i.user_id = $uid "
            "RETURN i.user_id, i.public_key, i.private_key, i.created_at",
            {"uid": user_id},
        )
        if not result.has_next():
            return None
        row = result.get_next()
        return UserIdentity(
            user_id=row[0],
            public_key=row[1],
            private_key=row[2] if include_private else "",
            created_at=row[3],
        )
