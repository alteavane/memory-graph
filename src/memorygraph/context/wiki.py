# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu

from memorygraph.graph.models import WikiEntity, WikiState


class WikiStore:
    """Gestisce WikiPage: creazione, versionamento, link a nodi epistemici."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def create_wiki_page(
        self,
        user_id: str,
        project_id: str,
        title: str,
        content: str,
        summary: str,
    ) -> WikiEntity:
        """Crea WikiEntity + primo WikiState (version=1)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        wiki_id = str(uuid.uuid4())
        state_id = str(uuid.uuid4())
        self._conn.execute(
            """
            CREATE (w:WikiEntity {
                id: $id, user_id: $uid, project_id: $pid,
                title: $title, created_at: $now, is_deleted: false
            })
            """,
            {"id": wiki_id, "uid": user_id, "pid": project_id, "title": title, "now": now},
        )
        self._conn.execute(
            """
            CREATE (s:WikiState {
                id: $id, version: 1, content: $content, summary: $summary, created_at: $now
            })
            """,
            {"id": state_id, "content": content, "summary": summary, "now": now},
        )
        self._conn.execute(
            "MATCH (w:WikiEntity), (s:WikiState) WHERE w.id = $wid AND s.id = $sid "
            "CREATE (w)-[:WIKI_HAS_STATE]->(s)",
            {"wid": wiki_id, "sid": state_id},
        )
        return WikiEntity(
            id=wiki_id, user_id=user_id, project_id=project_id,
            title=title, created_at=now,
        )

    def update_wiki_page(self, wiki_id: str, content: str, summary: str) -> WikiState:
        """Crea un nuovo WikiState (version = max + 1). Non modifica i precedenti."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state_id = str(uuid.uuid4())
        result = self._conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState) "
            "WHERE w.id = $wid RETURN MAX(s.version) AS max_v",
            {"wid": wiki_id},
        )
        row = result.get_next()
        max_version: int = row[0] if row[0] is not None else 0
        new_version = max_version + 1
        self._conn.execute(
            """
            CREATE (s:WikiState {
                id: $id, version: $version, content: $content,
                summary: $summary, created_at: $now
            })
            """,
            {"id": state_id, "version": new_version, "content": content,
             "summary": summary, "now": now},
        )
        self._conn.execute(
            "MATCH (w:WikiEntity), (s:WikiState) WHERE w.id = $wid AND s.id = $sid "
            "CREATE (w)-[:WIKI_HAS_STATE]->(s)",
            {"wid": wiki_id, "sid": state_id},
        )
        return WikiState(
            id=state_id, wiki_id=wiki_id, version=new_version,
            content=content, summary=summary, created_at=now,
        )

    def get_wiki_history(self, wiki_id: str) -> list[WikiState]:
        """Tutti i WikiState del nodo in ordine cronologico (version ASC)."""
        result = self._conn.execute(
            """
            MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState)
            WHERE w.id = $wid
            RETURN s.id, s.version, s.content, s.summary, s.created_at
            ORDER BY s.version ASC
            """,
            {"wid": wiki_id},
        )
        states: list[WikiState] = []
        while result.has_next():
            row = result.get_next()
            states.append(WikiState(
                id=row[0], wiki_id=wiki_id, version=row[1],
                content=row[2], summary=row[3], created_at=row[4],
            ))
        return states

    def list_wiki_pages(
        self,
        project_id: str,
    ) -> list[tuple[WikiEntity, WikiState]]:
        """WikiPage del progetto con lo stato più recente. Escluse le deleted."""
        result = self._conn.execute(
            """
            MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState)
            WHERE w.project_id = $pid AND w.is_deleted = false
            RETURN w.id, w.user_id, w.project_id, w.title, w.created_at, w.is_deleted,
                   s.id, s.version, s.content, s.summary, s.created_at
            ORDER BY w.id ASC, s.version DESC
            """,
            {"pid": project_id},
        )
        seen: dict[str, tuple[WikiEntity, WikiState]] = {}
        while result.has_next():
            row = result.get_next()
            wiki_id = row[0]
            if wiki_id not in seen:
                entity = WikiEntity(
                    id=row[0], user_id=row[1], project_id=row[2],
                    title=row[3], created_at=row[4], is_deleted=row[5],
                )
                state = WikiState(
                    id=row[6], wiki_id=wiki_id, version=row[7],
                    content=row[8], summary=row[9], created_at=row[10],
                )
                seen[wiki_id] = (entity, state)
        return list(seen.values())

    def link_to_nodes(self, wiki_id: str, node_ids: list[str]) -> None:
        """Crea archi WIKI_COVERS (WikiEntity → NodeEntity). Idempotente."""
        for node_id in node_ids:
            result = self._conn.execute(
                "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
                "WHERE w.id = $wid AND n.id = $nid RETURN count(*) AS c",
                {"wid": wiki_id, "nid": node_id},
            )
            if result.get_next()[0] > 0:
                continue
            self._conn.execute(
                "MATCH (w:WikiEntity), (n:NodeEntity) "
                "WHERE w.id = $wid AND n.id = $nid "
                "CREATE (w)-[:WIKI_COVERS]->(n)",
                {"wid": wiki_id, "nid": node_id},
            )
