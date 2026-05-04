# MemoryGraph Fase 1 — Graph Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire il layer di persistenza fondamentale di MemoryGraph: graph store embedded (Kuzu), modelli Python tipizzati, operazioni CRUD immutabili, e CLI base multi-utente.

**Architecture:** Kuzu embedded come graph DB (due node table: NodeEntity, NodeState; due rel table: HAS_STATE, CONNECTS). GraphStore è l'unico punto di accesso al DB. La CLI (Typer) è un thin wrapper sopra GraphStore.

**Tech Stack:** Python 3.11+, uv, kuzu, typer, rich, pytest

---

## File Map

| File | Responsabilità |
|---|---|
| `pyproject.toml` | Dipendenze, entry point CLI, config pytest |
| `.gitignore` | Esclude `data/`, `.kuzu`, `__pycache__`, `.env` |
| `src/memorygraph/__init__.py` | Package marker |
| `src/memorygraph/config.py` | `DB_PATH` da env var con fallback |
| `src/memorygraph/graph/__init__.py` | Package marker |
| `src/memorygraph/graph/models.py` | `NodeType`, `EdgeType`, `NodeEntity`, `NodeState`, `Edge` |
| `src/memorygraph/graph/schema.py` | `init_schema(conn)` — crea tabelle Kuzu se non esistono |
| `src/memorygraph/graph/store.py` | `GraphStore` — tutti i metodi CRUD |
| `tests/__init__.py` | Package marker |
| `tests/test_graph/__init__.py` | Package marker |
| `tests/test_graph/test_models.py` | Test enum e dataclass |
| `tests/test_graph/test_store.py` | Test ogni metodo GraphStore (fixture `tmp_path`) |
| `cli/main.py` | App Typer — 6 comandi, output rich + `--json` |
| `data/.gitkeep` | Placeholder directory DB locale |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `data/.gitkeep`
- Create: `src/memorygraph/__init__.py`
- Create: `src/memorygraph/graph/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_graph/__init__.py`
- Create: `cli/__init__.py` (vuoto)

- [ ] **Step 1: Creare `pyproject.toml`**

```toml
[project]
name = "memorygraph"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "kuzu>=0.7.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/memorygraph"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Creare `.gitignore`**

```
data/*.kuzu
data/memorygraph.kuzu*
__pycache__/
*.pyc
.env
.venv/
dist/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 3: Creare `.env.example`**

```
MEMORYGRAPH_DB_PATH=data/memorygraph.kuzu
```

- [ ] **Step 4: Creare directory e file `__init__.py` vuoti**

```bash
mkdir -p src/memorygraph/graph tests/test_graph cli data
touch src/memorygraph/__init__.py
touch src/memorygraph/graph/__init__.py
touch tests/__init__.py
touch tests/test_graph/__init__.py
touch cli/__init__.py
touch data/.gitkeep
```

- [ ] **Step 5: Installare dipendenze**

```bash
uv sync --dev
```

Expected: `uv.lock` creato, nessun errore.

- [ ] **Step 6: Verificare che Python trova i package**

```bash
uv run python -c "import kuzu; import typer; import rich; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git init
git add pyproject.toml .gitignore .env.example data/.gitkeep src/ tests/ cli/
git commit -m "chore: project scaffolding — uv, kuzu, typer, rich"
```

---

## Task 2: models.py

**Files:**
- Create: `src/memorygraph/graph/models.py`
- Create: `tests/test_graph/test_models.py`

- [ ] **Step 1: Scrivere il test**

Crea `tests/test_graph/test_models.py`:

```python
from datetime import datetime, timezone

import pytest

from memorygraph.graph.models import Edge, EdgeType, NodeEntity, NodeState, NodeType


def test_node_type_values():
    assert NodeType.HYPOTHESIS.value == "Hypothesis"
    assert NodeType.DEAD_END.value == "DeadEnd"
    assert NodeType.METHOD_DECISION.value == "MethodDecision"


def test_edge_type_values():
    assert EdgeType.SUPPORTA.value == "supporta"
    assert EdgeType.APRE_DOMANDA.value == "apre_domanda"


def test_node_entity_defaults():
    entity = NodeEntity(
        id="abc",
        user_id="user1",
        type=NodeType.HYPOTHESIS,
        created_at=datetime.now(timezone.utc),
    )
    assert entity.is_deleted is False


def test_node_state_fields():
    state = NodeState(
        id="s1",
        node_id="abc",
        version=1,
        content="test content",
        confidence=0.7,
        trigger="test trigger",
        created_at=datetime.now(timezone.utc),
    )
    assert state.version == 1
    assert state.confidence == 0.7


def test_edge_defaults():
    edge = Edge(
        edge_id="e1",
        from_node="n1",
        to_node="n2",
        type=EdgeType.SUPPORTA,
        confidence=0.9,
    )
    assert edge.invalidated_at is None


def test_node_type_from_str():
    t = NodeType("Hypothesis")
    assert t == NodeType.HYPOTHESIS


def test_edge_type_from_str():
    t = EdgeType("supporta")
    assert t == EdgeType.SUPPORTA
```

- [ ] **Step 2: Eseguire il test per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'memorygraph'` (o simile)

- [ ] **Step 3: Implementare `src/memorygraph/graph/models.py`**

```python
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
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_graph/test_models.py -v
```

Expected: tutti i test `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/graph/models.py tests/test_graph/test_models.py
git commit -m "feat: NodeType, EdgeType, NodeEntity, NodeState, Edge dataclasses"
```

---

## Task 3: config.py + schema.py

**Files:**
- Create: `src/memorygraph/config.py`
- Create: `src/memorygraph/graph/schema.py`

- [ ] **Step 1: Creare `src/memorygraph/config.py`**

```python
import os
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
DB_PATH = os.getenv(
    "MEMORYGRAPH_DB_PATH",
    str(_project_root / "data" / "memorygraph.kuzu"),
)
```

- [ ] **Step 2: Creare `src/memorygraph/graph/schema.py`**

```python
import kuzu

_SCHEMA_STATEMENTS = [
    """
    CREATE NODE TABLE IF NOT EXISTS NodeEntity (
        id STRING,
        user_id STRING,
        type STRING,
        created_at TIMESTAMP,
        is_deleted BOOLEAN,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS NodeState (
        id STRING,
        version INT64,
        content STRING,
        confidence DOUBLE,
        trigger STRING,
        created_at TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS HAS_STATE (
        FROM NodeEntity TO NodeState
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS CONNECTS (
        FROM NodeEntity TO NodeEntity,
        edge_id STRING,
        type STRING,
        confidence DOUBLE,
        invalidated_at TIMESTAMP
    )
    """,
]


def init_schema(conn: kuzu.Connection) -> None:
    """Crea tutte le tabelle Kuzu se non esistono. Idempotente."""
    for stmt in _SCHEMA_STATEMENTS:
        conn.execute(stmt)
```

- [ ] **Step 3: Verificare che lo schema si crea senza errori**

```bash
uv run python -c "
import kuzu, tempfile, os
from memorygraph.graph.schema import init_schema
with tempfile.TemporaryDirectory() as d:
    db = kuzu.Database(os.path.join(d, 'test.kuzu'))
    conn = kuzu.Connection(db)
    init_schema(conn)
    init_schema(conn)  # seconda chiamata: deve essere idempotente
    print('Schema OK')
"
```

Expected: `Schema OK`

- [ ] **Step 4: Commit**

```bash
git add src/memorygraph/config.py src/memorygraph/graph/schema.py
git commit -m "feat: config.py + Kuzu schema init (idempotente)"
```

---

## Task 4: GraphStore — create_node

**Files:**
- Create: `src/memorygraph/graph/store.py`
- Create: `tests/test_graph/test_store.py`

- [ ] **Step 1: Scrivere il test**

Crea `tests/test_graph/test_store.py`:

```python
import pytest

from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore


@pytest.fixture
def store(tmp_path):
    return GraphStore(str(tmp_path / "test.kuzu"))


class TestCreateNode:
    def test_returns_node_entity(self, store):
        entity = store.create_node(
            user_id="user1",
            type=NodeType.HYPOTHESIS,
            content="Il pH influenza il legame proteico",
            confidence=0.7,
            trigger="Osservazione esperimento #3",
        )
        assert entity.id is not None
        assert entity.user_id == "user1"
        assert entity.type == NodeType.HYPOTHESIS
        assert entity.is_deleted is False

    def test_creates_first_state_version_1(self, store):
        entity = store.create_node("u1", NodeType.OBSERVATION, "contenuto", 0.5, "trigger")
        history = store.get_node_history(entity.id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].content == "contenuto"
        assert history[0].confidence == 0.5
        assert history[0].trigger == "trigger"

    def test_each_node_has_unique_id(self, store):
        e1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        e2 = store.create_node("u1", NodeType.HYPOTHESIS, "B", 0.6, "t")
        assert e1.id != e2.id
```

- [ ] **Step 2: Eseguire il test per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_store.py -v
```

Expected: `ImportError` o `AttributeError` — `GraphStore` non esiste ancora.

- [ ] **Step 3: Implementare `store.py` con `__init__` e `create_node`**

Crea `src/memorygraph/graph/store.py`:

```python
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
        now = datetime.now(timezone.utc)
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
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_graph/test_store.py::TestCreateNode -v
```

Expected: tutti i test `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/graph/store.py tests/test_graph/test_store.py
git commit -m "feat: GraphStore.create_node + get_node_history (TDD)"
```

---

## Task 5: GraphStore — update_node

**Files:**
- Modify: `tests/test_graph/test_store.py` — aggiungere `TestUpdateNode`
- Modify: `src/memorygraph/graph/store.py` — aggiungere `update_node`

- [ ] **Step 1: Aggiungere i test in `test_store.py`**

Aggiungi dopo `TestCreateNode`:

```python
class TestUpdateNode:
    def test_increments_version(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        state = store.update_node(entity.id, "v2", 0.7, "nuova evidenza")
        assert state.version == 2
        assert state.content == "v2"
        assert state.confidence == 0.7

    def test_preserves_previous_states(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        store.update_node(entity.id, "v2", 0.7, "t2")
        history = store.get_node_history(entity.id)
        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].content == "v1"
        assert history[1].version == 2
        assert history[1].content == "v2"

    def test_multiple_updates_increment_correctly(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.3, "t1")
        store.update_node(entity.id, "v2", 0.5, "t2")
        state3 = store.update_node(entity.id, "v3", 0.8, "t3")
        assert state3.version == 3
        history = store.get_node_history(entity.id)
        assert [s.version for s in history] == [1, 2, 3]
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_store.py::TestUpdateNode -v
```

Expected: `AttributeError: 'GraphStore' object has no attribute 'update_node'`

- [ ] **Step 3: Aggiungere `update_node` a `store.py`**

Aggiungi dopo `create_node`:

```python
    def update_node(
        self,
        node_id: str,
        content: str,
        confidence: float,
        trigger: str,
    ) -> NodeState:
        """Crea un nuovo NodeState (version = max + 1). Non modifica mai i precedenti."""
        now = datetime.now(timezone.utc)
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
```

- [ ] **Step 4: Eseguire tutti i test store**

```bash
uv run pytest tests/test_graph/test_store.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/graph/store.py tests/test_graph/test_store.py
git commit -m "feat: GraphStore.update_node — versioning immutabile"
```

---

## Task 6: GraphStore — get_graph

**Files:**
- Modify: `tests/test_graph/test_store.py` — aggiungere `TestGetGraph`
- Modify: `src/memorygraph/graph/store.py` — aggiungere `get_graph`

- [ ] **Step 1: Aggiungere i test**

Aggiungi in `test_store.py`:

```python
class TestGetGraph:
    def test_returns_nodes_with_latest_state(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        store.update_node(entity.id, "v2", 0.8, "t2")
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 1
        _, state = graph["nodes"][0]
        assert state.version == 2
        assert state.content == "v2"

    def test_isolates_by_user_id(self, store):
        store.create_node("alice", NodeType.HYPOTHESIS, "alice content", 0.5, "t")
        store.create_node("bob", NodeType.OBSERVATION, "bob content", 0.6, "t")
        graph = store.get_graph("alice")
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0][0].user_id == "alice"

    def test_excludes_deleted_nodes(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "content", 0.5, "t")
        store._conn.execute(
            "MATCH (n:NodeEntity) WHERE n.id = $id SET n.is_deleted = true",
            {"id": entity.id},
        )
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 0

    def test_returns_empty_edges_when_none(self, store):
        store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        graph = store.get_graph("u1")
        assert graph["edges"] == []

    def test_multiple_nodes_returned(self, store):
        store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        store.create_node("u1", NodeType.OBSERVATION, "B", 0.7, "t")
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 2
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_store.py::TestGetGraph -v
```

Expected: `AttributeError: 'GraphStore' object has no attribute 'get_graph'`

- [ ] **Step 3: Aggiungere `get_graph` a `store.py`**

Aggiungi dopo `update_node`:

```python
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
            WHERE a.user_id = $uid AND r.invalidated_at IS NULL
            RETURN r.edge_id, a.id, b.id, r.type, r.confidence, r.invalidated_at
            """,
            {"uid": user_id},
        )
        edges: list[Edge] = []
        while edge_result.has_next():
            row = edge_result.get_next()
            edges.append(Edge(
                edge_id=row[0], from_node=row[1], to_node=row[2],
                type=EdgeType(row[3]), confidence=row[4], invalidated_at=row[5],
            ))

        return {"nodes": list(seen.values()), "edges": edges}
```

- [ ] **Step 4: Eseguire tutti i test store**

```bash
uv run pytest tests/test_graph/test_store.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/graph/store.py tests/test_graph/test_store.py
git commit -m "feat: GraphStore.get_graph — snapshot multi-tenant con isolamento user_id"
```

---

## Task 7: GraphStore — create_edge + invalidate_edge

**Files:**
- Modify: `tests/test_graph/test_store.py` — aggiungere `TestEdges`
- Modify: `src/memorygraph/graph/store.py` — aggiungere `create_edge`, `invalidate_edge`

- [ ] **Step 1: Aggiungere i test**

```python
class TestEdges:
    def test_create_edge_returns_edge(self, store):
        n1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = store.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        edge = store.create_edge(n1.id, n2.id, EdgeType.SUPPORTA, 0.9)
        assert edge.edge_id is not None
        assert edge.from_node == n1.id
        assert edge.to_node == n2.id
        assert edge.type == EdgeType.SUPPORTA
        assert edge.confidence == 0.9
        assert edge.invalidated_at is None

    def test_create_edge_appears_in_graph(self, store):
        n1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = store.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        edge = store.create_edge(n1.id, n2.id, EdgeType.SUPPORTA, 0.9)
        graph = store.get_graph("u1")
        assert len(graph["edges"]) == 1
        assert graph["edges"][0].edge_id == edge.edge_id

    def test_invalidate_edge_sets_timestamp(self, store):
        n1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = store.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        edge = store.create_edge(n1.id, n2.id, EdgeType.SUPPORTA, 0.9)
        invalidated = store.invalidate_edge(edge.edge_id)
        assert invalidated.invalidated_at is not None

    def test_invalidated_edge_not_in_graph(self, store):
        n1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = store.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        edge = store.create_edge(n1.id, n2.id, EdgeType.SUPPORTA, 0.9)
        store.invalidate_edge(edge.edge_id)
        graph = store.get_graph("u1")
        assert len(graph["edges"]) == 0

    def test_invalidate_preserves_edge_data(self, store):
        n1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = store.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        edge = store.create_edge(n1.id, n2.id, EdgeType.CONTRADDICE, 0.75)
        invalidated = store.invalidate_edge(edge.edge_id)
        assert invalidated.edge_id == edge.edge_id
        assert invalidated.type == EdgeType.CONTRADDICE
        assert invalidated.confidence == 0.75
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_store.py::TestEdges -v
```

Expected: `AttributeError: 'GraphStore' object has no attribute 'create_edge'`

- [ ] **Step 3: Aggiungere `create_edge` e `invalidate_edge` a `store.py`**

Aggiungi dopo `get_graph`:

```python
    def create_edge(
        self,
        from_id: str,
        to_id: str,
        type: EdgeType,
        confidence: float,
    ) -> Edge:
        """Crea una relazione CONNECTS tra due NodeEntity."""
        edge_id = str(uuid.uuid4())
        self._conn.execute(
            """
            MATCH (a:NodeEntity), (b:NodeEntity)
            WHERE a.id = $from_id AND b.id = $to_id
            CREATE (a)-[:CONNECTS {edge_id: $eid, type: $type, confidence: $conf, invalidated_at: null}]->(b)
            """,
            {"from_id": from_id, "to_id": to_id, "eid": edge_id, "type": type.value, "conf": confidence},
        )
        return Edge(edge_id=edge_id, from_node=from_id, to_node=to_id, type=type, confidence=confidence)

    def invalidate_edge(self, edge_id: str) -> Edge:
        """
        Invalida un arco: delete + re-insert con invalidated_at = now().
        Mai DELETE permanente — la storia è immutabile.
        """
        now = datetime.now(timezone.utc)

        result = self._conn.execute(
            "MATCH (a:NodeEntity)-[r:CONNECTS]->(b:NodeEntity) WHERE r.edge_id = $eid RETURN a.id, b.id, r.type, r.confidence",
            {"eid": edge_id},
        )
        row = result.get_next()
        from_id, to_id, edge_type_str, confidence = row[0], row[1], row[2], row[3]

        self._conn.execute(
            "MATCH (a:NodeEntity)-[r:CONNECTS]->(b:NodeEntity) WHERE r.edge_id = $eid DELETE r",
            {"eid": edge_id},
        )
        self._conn.execute(
            """
            MATCH (a:NodeEntity), (b:NodeEntity)
            WHERE a.id = $from_id AND b.id = $to_id
            CREATE (a)-[:CONNECTS {edge_id: $eid, type: $type, confidence: $conf, invalidated_at: $now}]->(b)
            """,
            {"from_id": from_id, "to_id": to_id, "eid": edge_id, "type": edge_type_str, "conf": confidence, "now": now},
        )

        return Edge(
            edge_id=edge_id, from_node=from_id, to_node=to_id,
            type=EdgeType(edge_type_str), confidence=confidence, invalidated_at=now,
        )
```

- [ ] **Step 4: Eseguire tutti i test**

```bash
uv run pytest tests/test_graph/test_store.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/graph/store.py tests/test_graph/test_store.py
git commit -m "feat: GraphStore.create_edge + invalidate_edge — mai DELETE permanente"
```

---

## Task 8: CLI

**Files:**
- Create: `cli/main.py`

La CLI usa Typer. I comandi chiamano direttamente `GraphStore`. Output human-readable con `rich`, oppure JSON con `--json`.

- [ ] **Step 1: Creare `cli/main.py`**

```python
from __future__ import annotations

import json
import sys
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from memorygraph.config import DB_PATH
from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore

app = typer.Typer(help="MemoryGraph CLI — graph store personale basato su credenze.")
console = Console()


def _get_store() -> GraphStore:
    return GraphStore(DB_PATH)


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_conf(c: float) -> str:
    return f"{c:.2f}"


@app.command()
def create(
    user_id: str = typer.Option(..., help="ID utente"),
    type: NodeType = typer.Option(..., help="Tipo nodo"),
    content: str = typer.Option(..., help="Contenuto della credenza"),
    confidence: float = typer.Option(..., help="Confidence 0.0–1.0"),
    trigger: str = typer.Option(..., help="Perché è stata creata questa credenza?"),
) -> None:
    """Crea un nuovo nodo con il primo stato."""
    store = _get_store()
    entity = store.create_node(user_id, type, content, confidence, trigger)
    console.print(f"[green]✓[/green] Nodo creato: [bold]{entity.id}[/bold] ({entity.type.value})")


@app.command()
def update(
    node_id: str = typer.Option(..., help="ID del nodo da aggiornare"),
    content: str = typer.Option(..., help="Nuovo contenuto"),
    confidence: float = typer.Option(..., help="Nuova confidence 0.0–1.0"),
    trigger: str = typer.Option(..., help="Perché è cambiata questa credenza?"),
) -> None:
    """Aggiorna un nodo creando un nuovo stato (non modifica i precedenti)."""
    store = _get_store()
    state = store.update_node(node_id, content, confidence, trigger)
    console.print(f"[green]✓[/green] Nodo aggiornato: versione [bold]{state.version}[/bold]")


@app.command()
def history(
    node_id: str = typer.Option(..., help="ID del nodo"),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON"),
) -> None:
    """Mostra la storia completa di un nodo (tutti gli stati in ordine cronologico)."""
    store = _get_store()
    states = store.get_node_history(node_id)

    if json_output:
        data = [
            {
                "id": s.id, "version": s.version, "content": s.content,
                "confidence": s.confidence, "trigger": s.trigger,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in states
        ]
        typer.echo(json.dumps(data, indent=2))
        return

    if not states:
        console.print("[yellow]Nessuno stato trovato per questo nodo.[/yellow]")
        return

    table = Table(title=f"Storia nodo: {node_id}", show_lines=True)
    table.add_column("Ver", style="cyan", width=4)
    table.add_column("Conf", width=6)
    table.add_column("Contenuto", min_width=30)
    table.add_column("Trigger", min_width=20)
    table.add_column("Creato", width=19)
    for s in states:
        table.add_row(str(s.version), _fmt_conf(s.confidence), s.content, s.trigger, _fmt_ts(s.created_at))
    console.print(table)


@app.command()
def show(
    user_id: str = typer.Option(..., help="ID utente"),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON"),
) -> None:
    """Mostra lo snapshot attuale del grafo di un utente."""
    store = _get_store()
    graph = store.get_graph(user_id)
    nodes = graph["nodes"]
    edges = graph["edges"]

    if json_output:
        data = {
            "nodes": [
                {
                    "id": e.id, "type": e.type.value, "user_id": e.user_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "latest_state": {
                        "version": s.version, "content": s.content,
                        "confidence": s.confidence, "trigger": s.trigger,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                    },
                }
                for e, s in nodes
            ],
            "edges": [
                {
                    "edge_id": ed.edge_id, "from": ed.from_node, "to": ed.to_node,
                    "type": ed.type.value, "confidence": ed.confidence,
                }
                for ed in edges
            ],
        }
        typer.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Grafo utente:[/bold] {user_id}  ({len(nodes)} nodi, {len(edges)} archi)\n")

    if nodes:
        node_table = Table(title="Nodi (stato più recente)", show_lines=True)
        node_table.add_column("ID", width=8)
        node_table.add_column("Tipo", width=14)
        node_table.add_column("Conf", width=6)
        node_table.add_column("Contenuto", min_width=30)
        node_table.add_column("Trigger", min_width=20)
        for entity, state in nodes:
            node_table.add_row(
                entity.id[:8], entity.type.value,
                _fmt_conf(state.confidence), state.content, state.trigger,
            )
        console.print(node_table)

    if edges:
        edge_table = Table(title="Archi attivi", show_lines=True)
        edge_table.add_column("Da", width=8)
        edge_table.add_column("Tipo", width=14)
        edge_table.add_column("A", width=8)
        edge_table.add_column("Conf", width=6)
        for ed in edges:
            edge_table.add_row(ed.from_node[:8], ed.type.value, ed.to_node[:8], _fmt_conf(ed.confidence))
        console.print(edge_table)


@app.command(name="edge-create")
def edge_create(
    from_node: str = typer.Option(..., "--from", help="ID nodo sorgente"),
    to_node: str = typer.Option(..., "--to", help="ID nodo destinazione"),
    type: EdgeType = typer.Option(..., help="Tipo arco"),
    confidence: float = typer.Option(..., help="Confidence 0.0–1.0"),
) -> None:
    """Crea un arco tra due nodi."""
    store = _get_store()
    edge = store.create_edge(from_node, to_node, type, confidence)
    console.print(f"[green]✓[/green] Arco creato: [bold]{edge.edge_id}[/bold] ({edge.type.value})")


@app.command(name="edge-invalidate")
def edge_invalidate(
    edge_id: str = typer.Option(..., help="ID arco da invalidare"),
) -> None:
    """Invalida un arco (non viene cancellato — viene marcato con timestamp)."""
    store = _get_store()
    edge = store.invalidate_edge(edge_id)
    console.print(f"[yellow]⊘[/yellow] Arco invalidato: [bold]{edge.edge_id}[/bold] alle {_fmt_ts(edge.invalidated_at)}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Smoke test manuale della CLI**

```bash
# Crea un nodo
uv run python cli/main.py create \
  --user-id alice \
  --type Hypothesis \
  --content "Il pH influenza il legame proteico" \
  --confidence 0.7 \
  --trigger "Osservazione esperimento #3"
```

Copia l'ID stampato (es. `abc12345`) e sostituiscilo nei comandi seguenti:

```bash
# Aggiorna il nodo
uv run python cli/main.py update \
  --node-id <ID_NODO> \
  --content "Il pH è critico sopra 7.2" \
  --confidence 0.3 \
  --trigger "Nuovo esperimento contraddice ipotesi iniziale"

# Mostra storia
uv run python cli/main.py history --node-id <ID_NODO>

# Mostra grafo
uv run python cli/main.py show --user-id alice

# JSON output
uv run python cli/main.py show --user-id alice --json
```

Expected: output human-readable con tabelle rich, poi JSON valido.

- [ ] **Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat: CLI Typer — create, update, history, show, edge-create, edge-invalidate"
```

---

## Task 9: Coverage check + commit finale

- [ ] **Step 1: Eseguire tutti i test con coverage**

```bash
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing -v
```

Expected: copertura totale >80%. Se la copertura è sotto l'80%, aggiungere test mancanti prima di procedere.

- [ ] **Step 2: Verificare che tutti i test passano**

```bash
uv run pytest tests/ -v
```

Expected: zero test falliti.

- [ ] **Step 3: Aggiornare `CLAUDE.md` — roadmap Fase 1 completata**

In `CLAUDE.md`, aggiorna la sezione `### 🔨 Fase 1 — IN CORSO` marcando tutte le checkbox come completate:

```markdown
### ✅ Fase 1 — Graph Store (COMPLETATA)
- [x] Setup progetto Python con `uv`
- [x] Installazione e configurazione Kuzu
- [x] Definizione schema Kuzu (`schema.py`)
- [x] Dataclass Python (`models.py`)
- [x] `GraphStore` class con operazioni base:
  - [x] `create_node(user_id, type, content, confidence, trigger)`
  - [x] `update_node(node_id, content, confidence, trigger)` → crea nuovo NodeState
  - [x] `get_node_history(node_id)` → tutti i NodeState in ordine cronologico
  - [x] `get_graph(user_id)` → snapshot attuale del grafo utente
  - [x] `create_edge(from_id, to_id, type, confidence)`
  - [x] `invalidate_edge(edge_id)` → mai delete
- [x] CLI base: `create`, `update`, `history`, `show`, `edge-create`, `edge-invalidate`
- [x] Test unitari GraphStore (copertura >80%)
```

- [ ] **Step 4: Commit finale**

```bash
git add -A
git commit -m "chore: Fase 1 completa — Graph Store, CLI, test coverage >80%"
```
