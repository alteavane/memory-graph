# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from memorygraph.graph.models import Edge, EdgeType, NodeEntity, NodeState, NodeType
from memorygraph.graph.schema import init_schema


class GraphStore:
    """Single access point to the Kuzu graph store. Thread-unsafe — one instance per process."""

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        init_schema(self._conn)

    def create_node(
        self,
        user_id: str,
        type: NodeType,
        content: str,
        confidence: float,
        trigger: str,
    ) -> NodeEntity:
        """Create a NodeEntity with its first NodeState (version=1)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        entity_id = str(uuid.uuid4())
        state_id = str(uuid.uuid4())

        self._conn.execute(
            "CREATE (n:NodeEntity {id: $id, user_id: $uid, type: $type, created_at: $ts, is_deleted: false})",
            {"id": entity_id, "uid": user_id, "type": type.value, "ts": now},
        )
        self._conn.execute(
            "CREATE (s:NodeState {id: $id, version: 1, content: $content, confidence: $conf, trigger: $trigger, created_at: $ts})",
            {"id": state_id, "content": content, "conf": confidence, "trigger": trigger, "ts": now},
        )
        self._conn.execute(
            "MATCH (e:NodeEntity), (s:NodeState) WHERE e.id = $eid AND s.id = $sid CREATE (e)-[:HAS_STATE]->(s)",
            {"eid": entity_id, "sid": state_id},
        )

        return NodeEntity(id=entity_id, user_id=user_id, type=type, created_at=now)

    def update_node(
        self,
        node_id: str,
        content: str,
        confidence: float,
        trigger: str,
    ) -> NodeState:
        """Create a new NodeState (version = max + 1). Never modifies previous ones."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state_id = str(uuid.uuid4())

        result = self._conn.execute(
            "MATCH (e:NodeEntity)-[:HAS_STATE]->(s:NodeState) WHERE e.id = $nid RETURN MAX(s.version) AS max_v",
            {"nid": node_id},
        )
        row = result.get_next()
        max_version: int = row[0] if row[0] is not None else 0
        new_version = max_version + 1

        self._conn.execute(
            "CREATE (s:NodeState {id: $id, version: $version, content: $content, confidence: $conf, trigger: $trigger, created_at: $ts})",
            {"id": state_id, "version": new_version, "content": content, "conf": confidence, "trigger": trigger, "ts": now},
        )
        self._conn.execute(
            "MATCH (e:NodeEntity), (s:NodeState) WHERE e.id = $eid AND s.id = $sid CREATE (e)-[:HAS_STATE]->(s)",
            {"eid": node_id, "sid": state_id},
        )

        return NodeState(
            id=state_id, node_id=node_id, version=new_version,
            content=content, confidence=confidence, trigger=trigger, created_at=now,
        )

    def get_graph(self, user_id: str) -> dict:
        """
        Current snapshot of the user's graph.
        Returns: {"nodes": list[tuple[NodeEntity, NodeState]], "edges": list[Edge]}
        Only non-deleted nodes with their most recent state. Only non-invalidated edges.
        """
        node_result = self._conn.execute(
            """
            MATCH (e:NodeEntity)-[:HAS_STATE]->(s:NodeState)
            WHERE e.user_id = $uid AND e.is_deleted = false
            RETURN e.id, e.user_id, e.type, e.created_at, e.is_deleted,
                   s.id, s.version, s.content, s.confidence, s.trigger, s.created_at
            ORDER BY e.id ASC, s.version DESC
            """,
            {"uid": user_id},
        )

        seen: dict[str, tuple[NodeEntity, NodeState]] = {}
        while node_result.has_next():
            row = node_result.get_next()
            node_id = row[0]
            if node_id not in seen:
                entity = NodeEntity(
                    id=row[0], user_id=row[1], type=NodeType(row[2]),
                    created_at=row[3], is_deleted=row[4],
                )
                state = NodeState(
                    id=row[5], node_id=node_id, version=row[6],
                    content=row[7], confidence=row[8], trigger=row[9], created_at=row[10],
                )
                seen[node_id] = (entity, state)

        edge_result = self._conn.execute(
            """
            MATCH (a:NodeEntity)-[r:CONNECTS]->(b:NodeEntity)
            WHERE a.user_id = $uid
            RETURN r.edge_id, a.id, b.id, r.type, r.confidence, r.invalidated_at
            """,
            {"uid": user_id},
        )
        edges: list[Edge] = []
        while edge_result.has_next():
            row = edge_result.get_next()
            invalidated_at = row[5]
            if invalidated_at is not None:
                continue
            edges.append(Edge(
                edge_id=row[0], from_node=row[1], to_node=row[2],
                type=EdgeType(row[3]), confidence=row[4], invalidated_at=None,
            ))

        return {"nodes": list(seen.values()), "edges": edges}

    def create_edge(
        self,
        from_id: str,
        to_id: str,
        type: EdgeType,
        confidence: float,
    ) -> Edge:
        """Create a CONNECTS relationship between two NodeEntity nodes."""
        edge_id = str(uuid.uuid4())
        self._conn.execute(
            """
            MATCH (a:NodeEntity), (b:NodeEntity)
            WHERE a.id = $from_id AND b.id = $to_id
            CREATE (a)-[:CONNECTS {edge_id: $eid, type: $type, confidence: $conf, invalidated_at: null}]->(b)
            """,
            {"from_id": from_id, "to_id": to_id, "eid": edge_id, "type": type.value, "conf": confidence},
        )
        return Edge(edge_id=edge_id, from_node=from_id, to_node=to_id, type=type, confidence=confidence)

    def invalidate_edge(self, edge_id: str) -> Edge:
        """
        Invalidate an edge by setting invalidated_at = now(). Atomic operation (single Kuzu query).
        Never a permanent deletion — history is immutable.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        result = self._conn.execute(
            """
            MATCH (a:NodeEntity)-[r:CONNECTS]->(b:NodeEntity)
            WHERE r.edge_id = $eid
            SET r.invalidated_at = $now
            RETURN a.id, b.id, r.type, r.confidence
            """,
            {"eid": edge_id, "now": now},
        )
        if not result.has_next():
            raise ValueError(f"Edge {edge_id} not found")
        row = result.get_next()
        from_id, to_id, edge_type_str, confidence = row[0], row[1], row[2], row[3]

        return Edge(
            edge_id=edge_id, from_node=from_id, to_node=to_id,
            type=EdgeType(edge_type_str), confidence=confidence, invalidated_at=now,
        )

    def get_node_history(self, node_id: str) -> list[NodeState]:
        """All NodeState records for the node in chronological order (version ASC)."""
        result = self._conn.execute(
            """
            MATCH (e:NodeEntity)-[:HAS_STATE]->(s:NodeState)
            WHERE e.id = $nid
            RETURN s.id, s.version, s.content, s.confidence, s.trigger, s.created_at
            ORDER BY s.version ASC
            """,
            {"nid": node_id},
        )
        states: list[NodeState] = []
        while result.has_next():
            row = result.get_next()
            states.append(NodeState(
                id=row[0], node_id=node_id, version=row[1],
                content=row[2], confidence=row[3], trigger=row[4], created_at=row[5],
            ))
        return states
