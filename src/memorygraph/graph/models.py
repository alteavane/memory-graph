# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class NodeType(str, Enum):
    OBSERVATION = "Observation"
    HYPOTHESIS = "Hypothesis"
    CONCLUSION = "Conclusion"
    DEAD_END = "DeadEnd"
    OPEN_QUESTION = "OpenQuestion"
    PAPER = "Paper"
    EXPERIMENT = "Experiment"
    METHOD_DECISION = "MethodDecision"


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVES_FROM = "derives_from"
    FALSIFIES = "falsifies"
    OPENS_QUESTION = "opens_question"
    RESOLVES = "resolves"


@dataclass
class NodeEntity:
    """An epistemic unit in the graph — immutable as identity, updatable as state."""

    id: str
    user_id: str
    type: NodeType
    created_at: datetime
    is_deleted: bool = False


@dataclass
class NodeState:
    """A belief captured at a moment in time. Never modified — only appended."""

    id: str
    node_id: str
    version: int
    content: str
    confidence: float
    trigger: str
    created_at: datetime


@dataclass
class Edge:
    """A typed relationship between two nodes. Invalidated with a timestamp, never deleted."""

    edge_id: str
    from_node: str
    to_node: str
    type: EdgeType
    confidence: float
    invalidated_at: datetime | None = None


@dataclass
class Project:
    """Research container. full_context is private — agent only."""

    id: str
    user_id: str
    title: str
    objective: str
    summary: str
    full_context: str    # never serialize into public output or a SubgraphToken
    created_at: datetime
    updated_at: datetime


@dataclass
class WikiEntity:
    """Stable identity of a Wiki page. The title does not change across versions."""

    id: str
    user_id: str
    project_id: str
    title: str
    created_at: datetime
    is_deleted: bool = False


@dataclass
class WikiState:
    """A version of a WikiPage's content. summary ≠ trigger — it describes the change."""

    id: str
    wiki_id: str      # logical FK → WikiEntity (not in Kuzu, populated by the query)
    version: int
    content: str
    summary: str
    created_at: datetime


@dataclass
class DocumentIndex:
    """Anchor to the external world — paper, dataset, protocol."""

    id: str
    user_id: str
    title: str
    doi: str | None
    url: str | None
    authors: str | None    # comma-separated, e.g. "Rossi M, Bianchi A"
    pub_date: str | None   # YYYY-MM-DD
    created_at: datetime


@dataclass
class UserIdentity:
    """Per-user Ed25519 identity. private_key is PRIVATE — never serialize it to public output."""

    user_id: str
    public_key: str
    private_key: str   # PRIVATE — same rule as Project.full_context
    created_at: datetime
