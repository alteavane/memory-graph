"""Context Layer — Project, Wiki, DocumentIndex."""

from __future__ import annotations

from pathlib import Path

import kuzu

from memorygraph.graph.schema import init_schema
from memorygraph.context.schema import init_context_schema
from memorygraph.context.project import ProjectStore
from memorygraph.context.wiki import WikiStore
from memorygraph.context.documents import DocumentStore


class ContextStore:
    """Facade del context layer. Unico punto d'ingresso per CLI e agente."""

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        init_schema(self._conn)           # NodeEntity deve esistere prima di BELONGS_TO
        init_context_schema(self._conn)
        self.projects = ProjectStore(self._conn)
        self.wiki = WikiStore(self._conn)
        self.documents = DocumentStore(self._conn)

    def attach_node(self, node_id: str, project_id: str) -> None:
        """Crea arco BELONGS_TO (NodeEntity → Project). Unica operazione cross-layer."""
        self._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) "
            "WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": node_id, "pid": project_id},
        )


__all__ = ["ContextStore"]
