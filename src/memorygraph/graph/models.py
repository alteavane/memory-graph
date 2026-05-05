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
    SUPPORTA = "supporta"
    CONTRADDICE = "contraddice"
    DERIVA_DA = "deriva_da"
    FALSIFICA = "falsifica"
    APRE_DOMANDA = "apre_domanda"
    RISOLVE = "risolve"


@dataclass
class NodeEntity:
    """Un'unità epistemica nel grafo — immutabile come identità, aggiornabile come stato."""

    id: str
    user_id: str
    type: NodeType
    created_at: datetime
    is_deleted: bool = False


@dataclass
class NodeState:
    """Una credenza catturata in un momento nel tempo. Mai modificata — solo aggiunta."""

    id: str
    node_id: str
    version: int
    content: str
    confidence: float
    trigger: str
    created_at: datetime


@dataclass
class Edge:
    """Relazione tipizzata tra due nodi. Invalidata con timestamp, mai cancellata."""

    edge_id: str
    from_node: str
    to_node: str
    type: EdgeType
    confidence: float
    invalidated_at: datetime | None = None


@dataclass
class Project:
    """Contenitore della ricerca. full_context è privato — solo agente."""

    id: str
    user_id: str
    title: str
    objective: str
    summary: str
    full_context: str    # mai serializzare in output pubblico o SubgraphToken
    created_at: datetime
    updated_at: datetime


@dataclass
class WikiEntity:
    """Identità stabile di una pagina Wiki. Il titolo non cambia tra versioni."""

    id: str
    user_id: str
    project_id: str
    title: str
    created_at: datetime
    is_deleted: bool = False


@dataclass
class WikiState:
    """Una versione del contenuto di una WikiPage. summary ≠ trigger — descrive il cambiamento."""

    id: str
    wiki_id: str      # FK logico → WikiEntity (non in Kuzu, popolato dalla query)
    version: int
    content: str
    summary: str
    created_at: datetime


@dataclass
class DocumentIndex:
    """Ancora al mondo esterno — paper, dataset, protocollo."""

    id: str
    user_id: str
    title: str
    doi: str | None
    url: str | None
    authors: str | None    # comma-separated, es. "Rossi M, Bianchi A"
    pub_date: str | None   # YYYY-MM-DD
    created_at: datetime
