# src/memorygraph/agent/agent.py
from __future__ import annotations

from typing import Callable

from rich.console import Console

from memorygraph.agent import extractor as _extractor
from memorygraph.agent import quality as _quality
from memorygraph.agent import detector as _detector
from memorygraph.agent.extractor import (
    CandidateNode,
    EmbedCallable,
    LLMCallable,
    ProposedNode,
)
from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.models import NodeState
from memorygraph.graph.store import GraphStore

console = Console()


class MemoryAgent:
    """Memory Agent: estrae nodi candidati dal testo e li propone per approvazione."""

    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.3,
        _input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._store = GraphStore(db_path)
        init_context_schema(self._store._conn)
        self._project_store = ProjectStore(self._store._conn)
        self._llm = llm
        self._embed = embed
        self._min_confidence = min_confidence
        self._input_fn = _input_fn or input

    def _load_project_nodes(self, project_id: str) -> list[NodeState]:
        result = self._store._conn.execute(
            """
            MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project)
            WHERE p.id = $pid AND n.is_deleted = false
            MATCH (n)-[:HAS_STATE]->(s:NodeState)
            RETURN n.id, s.id, s.version, s.content, s.confidence, s.trigger, s.created_at
            ORDER BY n.id ASC, s.version DESC
            """,
            {"pid": project_id},
        )
        seen: set[str] = set()
        states: list[NodeState] = []
        while result.has_next():
            row = result.get_next()
            node_id = row[0]
            if node_id not in seen:
                seen.add(node_id)
                states.append(NodeState(
                    id=row[1], node_id=node_id, version=row[2],
                    content=row[3], confidence=row[4], trigger=row[5], created_at=row[6],
                ))
        return states

    def extract(self, text: str, project_id: str | None = None) -> list[CandidateNode]:
        """Chiama LLM → parsifica JSON → ritorna candidati non filtrati."""
        project_context = None
        if project_id:
            project = self._project_store.get_project(project_id, agent_context=True)
            if project:
                project_context = project.full_context
        return _extractor.extract(text, self._llm, project_context=project_context, project_id=project_id)

    def propose(self, text: str, project_id: str | None = None) -> list[ProposedNode]:
        """extract → quality gate → contradiction detection → lista ProposedNode."""
        candidates = self.extract(text, project_id)
        filtered = _quality.filter_candidates(candidates, self._min_confidence)

        project_nodes: list[NodeState] = []
        if project_id:
            project_nodes = self._load_project_nodes(project_id)

        proposals: list[ProposedNode] = []
        for candidate in filtered:
            hint = _detector.detect(candidate, project_nodes, self._llm, self._embed)
            proposals.append(ProposedNode(candidate=candidate, hint=hint))

        return proposals

    def run(
        self,
        text: str,
        project_id: str | None = None,
        user_id: str = "",
    ) -> list[str]:
        """Esegue propose + loop di approvazione CLI → scrive nodi approvati → ritorna node_id[]."""
        raise NotImplementedError("Implementato nel Task 5")
