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
