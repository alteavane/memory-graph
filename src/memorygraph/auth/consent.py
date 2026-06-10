# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from datetime import datetime, timezone

import kuzu

from memorygraph.graph.models import UserNetworkConsent


class ConsentStore:
    """Persists per-user UserNetworkConsent. First read returns all-false defaults (not persisted)."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def get_consent(self, user_id: str) -> UserNetworkConsent:
        """Return the user's consent, or an all-false default (unpersisted) if none exists yet."""
        result = self._conn.execute(
            "MATCH (c:UserNetworkConsent) WHERE c.user_id = $uid "
            "RETURN c.discoverable, c.share_deadends, c.share_triggers, "
            "c.auto_propose, c.updated_at",
            {"uid": user_id},
        )
        if not result.has_next():
            return UserNetworkConsent(user_id=user_id)
        row = result.get_next()
        return UserNetworkConsent(
            user_id=user_id,
            discoverable=row[0], share_deadends=row[1],
            share_triggers=row[2], auto_propose=row[3], updated_at=row[4],
        )

    def set_consent(
        self,
        user_id: str,
        *,
        discoverable: bool | None = None,
        share_deadends: bool | None = None,
        share_triggers: bool | None = None,
        auto_propose: bool | None = None,
    ) -> UserNetworkConsent:
        """Upsert the user's consent. Fields left as None keep their persisted value, or False if the user has no record yet."""
        current = self.get_consent(user_id)
        merged = UserNetworkConsent(
            user_id=user_id,
            discoverable=current.discoverable if discoverable is None else discoverable,
            share_deadends=current.share_deadends if share_deadends is None else share_deadends,
            share_triggers=current.share_triggers if share_triggers is None else share_triggers,
            auto_propose=current.auto_propose if auto_propose is None else auto_propose,
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        exists = current.updated_at is not None
        params = {
            "uid": user_id, "d": merged.discoverable, "sd": merged.share_deadends,
            "st": merged.share_triggers, "ap": merged.auto_propose, "ts": merged.updated_at,
        }
        if exists:
            self._conn.execute(
                "MATCH (c:UserNetworkConsent) WHERE c.user_id = $uid "
                "SET c.discoverable = $d, c.share_deadends = $sd, "
                "c.share_triggers = $st, c.auto_propose = $ap, c.updated_at = $ts",
                params,
            )
        else:
            self._conn.execute(
                "CREATE (c:UserNetworkConsent {user_id: $uid, discoverable: $d, "
                "share_deadends: $sd, share_triggers: $st, auto_propose: $ap, updated_at: $ts})",
                params,
            )
        return merged
