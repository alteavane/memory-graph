# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from memorygraph.agent.extractor import LLMCallable, EmbedCallable
from memorygraph.graph.models import EdgeType
from memorygraph.graph.store import GraphStore

console = Console()


@dataclass
class CandidateEdge:
    from_node_id: str
    to_node_id: str
    type: EdgeType
    confidence: float
    reason: str
    is_new_node: bool = False


@dataclass
class ProposedEdge:
    candidate: CandidateEdge
    from_content: str
    to_content: str
    approved: bool = True
    edited_type: EdgeType | None = None
    edited_confidence: float | None = None

    @property
    def effective_type(self) -> EdgeType:
        return self.edited_type or self.candidate.type

    @property
    def effective_confidence(self) -> float:
        return self.edited_confidence if self.edited_confidence is not None else self.candidate.confidence


def _strip_markdown(text: str) -> str:
    return re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()


def _clamp(val: float) -> float:
    return max(0.0, min(1.0, val))


class LinkAgent:
    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.4,
        max_edges: int = 10,
        store: GraphStore | None = None,
    ) -> None:
        self._db_path = db_path
        self._llm = llm
        self._embed = embed
        self._min_confidence = min_confidence
        self._max_edges = max_edges
        self._store = store or GraphStore(db_path)

    def propose(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[ProposedEdge]:
        """Load context → LLM → filter → enrich → return ProposedEdge."""
        node_contents = self._load_all_nodes(user_id, project_id)
        if not node_contents:
            return []

        valid_ids = set(node_contents.keys())
        # verify that the new_node_ids are actually in the graph
        new_node_ids = [nid for nid in new_node_ids if nid in valid_ids]
        if not new_node_ids:
            return []

        new_block = "\n".join(
            f'[id: {nid}] "{node_contents[nid]["content"][:80]}"'
            for nid in new_node_ids
        )
        existing_ids = [nid for nid in valid_ids if nid not in new_node_ids]
        existing_block = "\n".join(
            f'[id: {nid}] ({node_contents[nid]["type"]}, conf {node_contents[nid]["confidence"]:.2f}) "{node_contents[nid]["content"][:80]}"'
            for nid in existing_ids
        ) or "(no existing nodes besides the new ones)"

        prompt = _build_prompt(new_block, existing_block, self._max_edges)
        raw = self._llm(prompt)
        candidates = _parse_candidates(raw, valid_ids, self._min_confidence)
        return _enrich(candidates, node_contents, new_node_ids)

    def run(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[str]:
        """propose → interactive table → write."""
        proposed = self.propose(new_node_ids, user_id=user_id, project_id=project_id)
        if not proposed:
            return []

        _render_table(proposed)
        edge_ids = _interactive_loop(proposed, self._store)
        return edge_ids

    def _load_all_nodes(
        self,
        user_id: str,
        project_id: str | None,
    ) -> dict[str, dict]:
        """
        Return {node_id: {content, type, confidence}} for all of the user's active nodes.
        If project_id is provided, filter by project (via BELONGS_TO).
        """
        graph = self._store.get_graph(user_id)
        result = {}
        for entity, state in graph["nodes"]:
            result[entity.id] = {
                "content": state.content,
                "type": entity.type.value,
                "confidence": state.confidence,
            }
        return result


def _build_prompt(new_block: str, existing_block: str, max_edges: int) -> str:
    return f"""You are an analyst of scientific knowledge graphs.
You have a set of newly added nodes and a set of existing nodes in the graph.
Your task is to identify significant semantic relationships between them.

Valid EdgeTypes:
- supports       → A provides evidence in favor of B
- contradicts    → A is in tension or conflict with B
- derives_from   → A is a logical consequence or deduction of B
- falsifies      → A is empirical evidence that invalidates B
- opens_question → A generates an open question represented by B
- resolves       → A answers or closes the open question B

Confidence scale:
0.9+    → evident and direct relationship
0.6–0.9 → plausible relationship with clear motivation
0.4–0.6 → possible relationship, worth signaling
< 0.4   → do not propose

Newly added nodes:
{new_block}

Existing nodes in the graph:
{existing_block}

Propose ONLY semantically significant edges. No more than {max_edges} in total.

Reply ONLY with valid JSON:
{{"edges": [{{"from": "<node_id>", "to": "<node_id>", "type": "<EdgeType>", "confidence": 0.0, "reason": "<brief explanation>"}}]}}
If no edges found: {{"edges": []}}"""


def _parse_candidates(
    raw: str,
    valid_ids: set[str],
    min_confidence: float,
) -> list[CandidateEdge]:
    text = _strip_markdown(raw)
    try:
        data = json.loads(text)
        edges = data.get("edges", [])
    except (json.JSONDecodeError, AttributeError):
        return []

    result = []
    seen: set[tuple[str, str, str]] = set()
    for e in edges:
        try:
            from_id = e.get("from", "")
            to_id = e.get("to", "")
            edge_type_str = e.get("type", "")
            confidence = _clamp(float(e.get("confidence", 0.0)))
            reason = e.get("reason", "")
        except (TypeError, ValueError):
            continue

        # validations
        if from_id not in valid_ids or to_id not in valid_ids:
            continue
        if from_id == to_id:
            continue
        if confidence < min_confidence:
            continue
        try:
            edge_type = EdgeType(edge_type_str)
        except ValueError:
            continue
        key = (from_id, to_id, edge_type_str)
        if key in seen:
            continue
        seen.add(key)

        result.append(CandidateEdge(
            from_node_id=from_id,
            to_node_id=to_id,
            type=edge_type,
            confidence=confidence,
            reason=reason,
        ))
    return result


def _enrich(
    candidates: list[CandidateEdge],
    node_contents: dict[str, dict],
    new_node_ids: list[str],
) -> list[ProposedEdge]:
    new_set = set(new_node_ids)
    return [
        ProposedEdge(
            candidate=c,
            from_content=node_contents[c.from_node_id]["content"],
            to_content=node_contents[c.to_node_id]["content"],
            approved=True,
        )
        for c in candidates
        if c.from_node_id in node_contents and c.to_node_id in node_contents
    ]


def _render_table(proposed: list[ProposedEdge]) -> None:
    table = Table(title=f"Candidate edges detected ({len(proposed)})", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("✓", width=2)
    table.add_column("From", max_width=36)
    table.add_column("Type", width=13)
    table.add_column("To", max_width=36)
    table.add_column("Conf", width=5)
    table.add_column("Reason", max_width=36)

    for i, p in enumerate(proposed, 1):
        check = "✓" if p.approved else " "
        table.add_row(
            str(i),
            check,
            f"[{p.candidate.from_node_id[:8]}] {p.from_content}",
            f"{p.effective_type.value} →",
            f"[{p.candidate.to_node_id[:8]}] {p.to_content}",
            f"{p.effective_confidence:.2f}",
            p.candidate.reason,
        )
    console.print(table)
    console.print(
        "Commands: [n <num>] deselect  [t <num> <type>] change type  "
        "[c <num> <val>] change confidence  [y] approve  [N] cancel",
        markup=False,
        style="dim",
    )


def _interactive_loop(proposed: list[ProposedEdge], store: GraphStore) -> list[str]:
    while True:
        raw = input("> ").strip()
        if raw == "y":
            break
        if raw == "N":
            return []
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0]
        try:
            if cmd == "n" and len(parts) >= 2:
                for idx_str in parts[1:]:
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(proposed):
                        proposed[idx].approved = False
            elif cmd == "t" and len(parts) == 3:
                idx = int(parts[1]) - 1
                new_type = EdgeType(parts[2])
                if 0 <= idx < len(proposed):
                    proposed[idx].edited_type = new_type
            elif cmd == "c" and len(parts) == 3:
                idx = int(parts[1]) - 1
                new_conf = _clamp(float(parts[2]))
                if 0 <= idx < len(proposed):
                    proposed[idx].edited_confidence = new_conf
        except (ValueError, IndexError):
            console.print("[red]Invalid command.[/red]")
            continue
        _render_table(proposed)

    edge_ids = []
    for p in proposed:
        if p.approved:
            edge = store.create_edge(
                p.candidate.from_node_id,
                p.candidate.to_node_id,
                p.effective_type,
                p.effective_confidence,
            )
            edge_ids.append(edge.edge_id)
    if edge_ids:
        console.print(f"✓ Wrote {len(edge_ids)} edge(s).")
    return edge_ids
