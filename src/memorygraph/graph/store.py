from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from memorygraph.graph.models import Edge, EdgeType, NodeEntity, NodeState, NodeType
from memorygraph.graph.schema import init_schema


class GraphStore:
    """Unico punto di accesso al graph store Kuzu. Thread-unsafe — una istanza per processo."""

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
        """Crea un NodeEntity con il primo NodeState (version=1)."""
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
        """Crea un nuovo NodeState (version = max + 1). Non modifica mai i precedenti."""
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
        Snapshot attuale del grafo utente.
        Ritorna: {"nodes": list[tuple[NodeEntity, NodeState]], "edges": list[Edge]}
        Solo nodi non deleted con il loro stato più recente. Solo archi non invalidati.
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

    def get_node_history(self, node_id: str) -> list[NodeState]:
        """Tutti i NodeState del nodo in ordine cronologico (version ASC)."""
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
