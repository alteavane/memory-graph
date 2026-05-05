from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu

from memorygraph.graph.models import DocumentIndex


class DocumentStore:
    """Gestisce DocumentIndex: ancore al mondo esterno con metadati bibliografici."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def add_document(
        self,
        user_id: str,
        title: str,
        *,
        doi: str | None = None,
        url: str | None = None,
        authors: str | None = None,
        pub_date: str | None = None,
    ) -> DocumentIndex:
        """Crea un nuovo DocumentIndex."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        doc_id = str(uuid.uuid4())
        self._conn.execute(
            """
            CREATE (d:DocumentIndex {
                id: $id, user_id: $uid, title: $title,
                doi: $doi, url: $url, authors: $authors,
                pub_date: $pub_date, created_at: $now
            })
            """,
            {
                "id": doc_id, "uid": user_id, "title": title,
                "doi": doi or "", "url": url or "",
                "authors": authors or "", "pub_date": pub_date or "",
                "now": now,
            },
        )
        return DocumentIndex(
            id=doc_id, user_id=user_id, title=title,
            doi=doi, url=url, authors=authors, pub_date=pub_date,
            created_at=now,
        )

    def get_document(self, doc_id: str) -> DocumentIndex | None:
        """Ritorna il DocumentIndex o None se non esiste."""
        result = self._conn.execute(
            """
            MATCH (d:DocumentIndex) WHERE d.id = $did
            RETURN d.id, d.user_id, d.title, d.doi, d.url,
                   d.authors, d.pub_date, d.created_at
            """,
            {"did": doc_id},
        )
        if not result.has_next():
            return None
        row = result.get_next()
        return DocumentIndex(
            id=row[0], user_id=row[1], title=row[2],
            doi=row[3] or None, url=row[4] or None,
            authors=row[5] or None, pub_date=row[6] or None,
            created_at=row[7],
        )

    def list_documents(self, user_id: str) -> list[DocumentIndex]:
        """Lista tutti i documenti dell'utente."""
        result = self._conn.execute(
            """
            MATCH (d:DocumentIndex) WHERE d.user_id = $uid
            RETURN d.id, d.user_id, d.title, d.doi, d.url,
                   d.authors, d.pub_date, d.created_at
            ORDER BY d.created_at ASC
            """,
            {"uid": user_id},
        )
        docs: list[DocumentIndex] = []
        while result.has_next():
            row = result.get_next()
            docs.append(DocumentIndex(
                id=row[0], user_id=row[1], title=row[2],
                doi=row[3] or None, url=row[4] or None,
                authors=row[5] or None, pub_date=row[6] or None,
                created_at=row[7],
            ))
        return docs

    def reference_document(self, node_id: str, doc_id: str) -> None:
        """Crea arco REFERENCES_DOC (NodeEntity → DocumentIndex). Idempotente."""
        result = self._conn.execute(
            "MATCH (n:NodeEntity)-[:REFERENCES_DOC]->(d:DocumentIndex) "
            "WHERE n.id = $nid AND d.id = $did RETURN count(*) AS c",
            {"nid": node_id, "did": doc_id},
        )
        if result.get_next()[0] > 0:
            return
        self._conn.execute(
            "MATCH (n:NodeEntity), (d:DocumentIndex) "
            "WHERE n.id = $nid AND d.id = $did "
            "CREATE (n)-[:REFERENCES_DOC]->(d)",
            {"nid": node_id, "did": doc_id},
        )
