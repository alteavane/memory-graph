from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu

from memorygraph.graph.models import Project


class ProjectStore:
    """Gestisce Project: creazione, lettura con visibilità controllata, aggiornamento."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def create_project(
        self,
        user_id: str,
        title: str,
        objective: str,
        summary: str,
        full_context: str,
    ) -> Project:
        """Crea un nuovo Project. Ritorna il Project completo."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        project_id = str(uuid.uuid4())
        self._conn.execute(
            """
            CREATE (p:Project {
                id: $id, user_id: $uid, title: $title, objective: $obj,
                summary: $summary, full_context: $fc,
                created_at: $now, updated_at: $now
            })
            """,
            {
                "id": project_id, "uid": user_id, "title": title,
                "obj": objective, "summary": summary, "fc": full_context,
                "now": now,
            },
        )
        return Project(
            id=project_id, user_id=user_id, title=title, objective=objective,
            summary=summary, full_context=full_context,
            created_at=now, updated_at=now,
        )

    def get_project(
        self,
        project_id: str,
        *,
        agent_context: bool = False,
    ) -> Project | None:
        """
        Ritorna il Project.
        agent_context=False (default): full_context = "" — default sicuro.
        agent_context=True: full_context incluso — solo per il Memory Agent.
        """
        result = self._conn.execute(
            """
            MATCH (p:Project) WHERE p.id = $pid
            RETURN p.id, p.user_id, p.title, p.objective, p.summary,
                   p.full_context, p.created_at, p.updated_at
            """,
            {"pid": project_id},
        )
        if not result.has_next():
            return None
        row = result.get_next()
        return Project(
            id=row[0], user_id=row[1], title=row[2], objective=row[3],
            summary=row[4],
            full_context=row[5] if agent_context else "",
            created_at=row[6], updated_at=row[7],
        )

    def get_project_summary(self, project_id: str) -> dict | None:
        """
        Ritorna solo i campi pubblici: {id, title, objective, summary}.
        Ritorna dict (non Project) — il tipo rende esplicito che full_context non c'è.
        """
        result = self._conn.execute(
            """
            MATCH (p:Project) WHERE p.id = $pid
            RETURN p.id, p.title, p.objective, p.summary
            """,
            {"pid": project_id},
        )
        if not result.has_next():
            return None
        row = result.get_next()
        return {"id": row[0], "title": row[1], "objective": row[2], "summary": row[3]}

    def update_project(
        self,
        project_id: str,
        *,
        title: str | None = None,
        objective: str | None = None,
        summary: str | None = None,
        full_context: str | None = None,
    ) -> Project:
        """Aggiorna i campi specificati. Ritorna Project completo (uso interno)."""
        existing = self.get_project(project_id, agent_context=True)
        if existing is None:
            raise ValueError(f"Project {project_id} not found")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        new_title = title if title is not None else existing.title
        new_obj = objective if objective is not None else existing.objective
        new_summary = summary if summary is not None else existing.summary
        new_fc = full_context if full_context is not None else existing.full_context
        self._conn.execute(
            """
            MATCH (p:Project) WHERE p.id = $pid
            SET p.title = $title, p.objective = $obj, p.summary = $summary,
                p.full_context = $fc, p.updated_at = $now
            """,
            {
                "pid": project_id, "title": new_title, "obj": new_obj,
                "summary": new_summary, "fc": new_fc, "now": now,
            },
        )
        return Project(
            id=project_id, user_id=existing.user_id,
            title=new_title, objective=new_obj,
            summary=new_summary, full_context=new_fc,
            created_at=existing.created_at, updated_at=now,
        )

    def list_projects(
        self,
        user_id: str,
        *,
        agent_context: bool = False,
    ) -> list[Project]:
        """
        Lista tutti i Project dell'utente.
        agent_context=False (default): full_context = "" in ogni Project.
        """
        result = self._conn.execute(
            """
            MATCH (p:Project) WHERE p.user_id = $uid
            RETURN p.id, p.user_id, p.title, p.objective, p.summary,
                   p.full_context, p.created_at, p.updated_at
            ORDER BY p.created_at ASC
            """,
            {"uid": user_id},
        )
        projects: list[Project] = []
        while result.has_next():
            row = result.get_next()
            projects.append(Project(
                id=row[0], user_id=row[1], title=row[2], objective=row[3],
                summary=row[4],
                full_context=row[5] if agent_context else "",
                created_at=row[6], updated_at=row[7],
            ))
        return projects
