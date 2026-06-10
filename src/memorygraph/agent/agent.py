# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
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
from memorygraph.graph.models import EdgeType, NodeState
from memorygraph.graph.store import GraphStore

console = Console()


class MemoryAgent:
    """Memory Agent: extracts candidate nodes from text and proposes them for approval."""

    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.3,
        _input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._db_path = db_path
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
        """Call the LLM → parse JSON → return unfiltered candidates."""
        project_context = None
        if project_id:
            project = self._project_store.get_project(project_id, agent_context=True)
            if project:
                project_context = project.full_context
        return _extractor.extract(text, self._llm, project_context=project_context, project_id=project_id)

    def propose(self, text: str, project_id: str | None = None) -> list[ProposedNode]:
        """extract → quality gate → contradiction detection → list of ProposedNode."""
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

    def _write_node(self, user_id: str, candidate: CandidateNode, project_id: str | None) -> str:
        node = self._store.create_node(
            user_id=user_id,
            type=candidate.type,
            content=candidate.content,
            confidence=candidate.confidence,
            trigger=candidate.trigger,
        )
        if project_id:
            self._store._conn.execute(
                "MATCH (n:NodeEntity), (p:Project) "
                "WHERE n.id = $nid AND p.id = $pid "
                "CREATE (n)-[:BELONGS_TO]->(p)",
                {"nid": node.id, "pid": project_id},
            )
        return node.id

    def run(
        self,
        text: str,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> list[str]:
        """Run propose + CLI approval loop → write approved nodes → return node_id[]."""
        if user_id is None:
            raise ValueError("user_id is required")
        proposals = self.propose(text, project_id)
        approved: list[str] = []
        total = len(proposals)

        for i, proposed in enumerate(proposals):
            c = proposed.candidate
            console.print(f"\n[bold cyan][{i + 1}/{total}] Candidate node:[/bold cyan]")
            console.print(f"  Type:       {c.type.value}")
            console.print(f"  Content:    {c.content}")
            console.print(f"  Confidence: {c.confidence:.2f}")
            console.print(f"  Trigger:    {c.trigger}")
            if proposed.hint:
                console.print(
                    f"  [yellow]⚠ Possible contradiction with node "
                    f"{proposed.hint.existing_node_id[:8]}:[/yellow]"
                )
                console.print(f'    "{proposed.hint.reason}" (detected by the agent)')

            response = self._input_fn("Approve this node? [y/n/s/a]: ").strip().lower()

            if response == "n":
                continue
            elif response == "s":
                break
            elif response in ("y", "a"):
                node_id = self._write_node(user_id, c, project_id)
                approved.append(node_id)

                if proposed.hint:
                    edge_resp = self._input_fn("Create a contradiction edge? [y/n]: ").strip().lower()
                    if edge_resp == "y":
                        self._store.create_edge(
                            node_id,
                            proposed.hint.existing_node_id,
                            EdgeType.CONTRADICTS,
                            1.0,
                        )

                if response == "a":
                    for remaining in proposals[i + 1:]:
                        rid = self._write_node(user_id, remaining.candidate, project_id)
                        approved.append(rid)
                    break

        if approved:
            from memorygraph.agent.link_agent import LinkAgent
            link_agent = LinkAgent(self._db_path, self._llm, self._embed, self._min_confidence, store=self._store)
            link_agent.run(approved, user_id=user_id, project_id=project_id)

        return approved
