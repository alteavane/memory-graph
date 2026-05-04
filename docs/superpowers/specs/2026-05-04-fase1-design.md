# MemoryGraph — Fase 1: Graph Store — Design Spec

**Data:** 2026-05-04  
**Stato:** Approvato  
**Scope:** Fase 1 — fondamenta del graph store locale

---

## Obiettivo

Costruire il layer di persistenza fondamentale di MemoryGraph:
un graph store embedded (Kuzu) che modella credenze come nodi versionati,
con isolamento multi-tenant, immutabilità della storia, e una CLI base per interazione diretta.

---

## Stack

| Componente | Scelta |
|---|---|
| Linguaggio | Python 3.11+ con type hints ovunque |
| Graph DB | Kuzu (embedded, file locale) |
| Package manager | uv |
| CLI framework | Typer |
| Output formatting | rich (human-readable) + json (--json flag) |
| Test | pytest con fixture `tmp_path` |

---

## Schema Kuzu

### Node Tables

```cypher
CREATE NODE TABLE NodeEntity (
    id STRING,
    user_id STRING,
    type STRING,
    created_at TIMESTAMP,
    is_deleted BOOLEAN,
    PRIMARY KEY (id)
)

CREATE NODE TABLE NodeState (
    id STRING,
    version INT64,
    content STRING,
    confidence DOUBLE,
    trigger STRING,
    created_at TIMESTAMP,
    PRIMARY KEY (id)
)
```

### Rel Tables

```cypher
CREATE REL TABLE HAS_STATE (FROM NodeEntity TO NodeState)

CREATE REL TABLE CONNECTS (
    FROM NodeEntity TO NodeEntity,
    edge_id STRING,
    type STRING,
    confidence DOUBLE,
    invalidated_at TIMESTAMP
)
```

**Nota su `invalidated_at`:** gli archi non vengono mai cancellati permanentemente.
Per invalidare un arco: delete della relazione + re-insert con `invalidated_at = now()`.
Questo preserva la storia mantenendo la semantica graph-native di Kuzu.

---

## Modelli Python (`models.py`)

```python
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
    id: str                  # UUID as str
    user_id: str
    type: NodeType
    created_at: datetime
    is_deleted: bool = False

@dataclass
class NodeState:
    id: str                  # UUID as str
    node_id: str             # FK logico a NodeEntity (usato in Python)
    version: int             # incrementale da 1
    content: str
    confidence: float        # 0.0 – 1.0
    trigger: str
    created_at: datetime

@dataclass
class Edge:
    edge_id: str             # UUID as str
    from_node: str
    to_node: str
    type: EdgeType
    confidence: float
    invalidated_at: datetime | None = None
```

---

## GraphStore API (`store.py`)

```python
class GraphStore:
    def __init__(self, db_path: str) -> None:
        """Apre connessione Kuzu e crea tabelle se non esistono (idempotente)."""

    # --- Nodi ---

    def create_node(
        self,
        user_id: str,
        type: NodeType,
        content: str,
        confidence: float,
        trigger: str,
    ) -> NodeEntity:
        """Crea NodeEntity + primo NodeState (version=1). Ritorna l'entity."""

    def update_node(
        self,
        node_id: str,
        content: str,
        confidence: float,
        trigger: str,
    ) -> NodeState:
        """Crea un nuovo NodeState (version = max_version + 1). Non modifica mai i precedenti."""

    def get_node_history(self, node_id: str) -> list[NodeState]:
        """Ritorna tutti i NodeState del nodo in ordine cronologico (version ASC)."""

    def get_graph(self, user_id: str) -> dict:
        """
        Snapshot attuale del grafo utente:
        {
            "nodes": list[tuple[NodeEntity, NodeState]],  # entity + ultimo state
            "edges": list[Edge],                           # solo archi non invalidati
        }
        """

    # --- Archi ---

    def create_edge(
        self,
        from_id: str,
        to_id: str,
        type: EdgeType,
        confidence: float,
    ) -> Edge:
        """Crea una relazione CONNECTS tra due NodeEntity."""

    def invalidate_edge(self, edge_id: str) -> Edge:
        """
        Invalida un arco: delete + re-insert con invalidated_at = now().
        Mai DELETE permanente — la storia è immutabile.
        """
```

---

## CLI (`cli/main.py`)

Framework: Typer. Entry point: `mg` (configurato in `pyproject.toml`).

### Comandi

```bash
mg create   --user-id <str> --type <NodeType> --content <str> --confidence <float> --trigger <str>
mg update   --node-id <str> --content <str> --confidence <float> --trigger <str>
mg history  --node-id <str> [--json]
mg show     --user-id <str> [--json]
mg edge-create      --from <str> --to <str> --type <EdgeType> --confidence <float>
mg edge-invalidate  --edge-id <str>
```

### Output

- **Default (human-readable):** tabelle `rich`, timestamp leggibili, confidence come `0.70`
- **`--json`:** `json.dumps` degli stessi dati, per script e debug

---

## Testing (`tests/test_graph/`)

### Strategia

- Ogni test istanzia un `GraphStore` su `tmp_path` pytest → nessun DB condiviso, zero mock
- Un test per ogni metodo pubblico di `GraphStore`
- Target copertura: >80%

### Casi da coprire

| Metodo | Casi |
|---|---|
| `create_node` | crea entity + state, version=1, campi corretti |
| `update_node` | incrementa version, non modifica state precedente |
| `get_node_history` | ordine cronologico, tutti gli state |
| `get_graph` | solo nodi non deleted, solo archi non invalidati, isolamento user_id |
| `create_edge` | arco creato, confidence corretta |
| `invalidate_edge` | invalidated_at valorizzato, arco non più in get_graph |

---

## Struttura file

```
memorygraph/
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── src/
│   └── memorygraph/
│       ├── __init__.py
│       ├── config.py
│       └── graph/
│           ├── __init__.py
│           ├── models.py
│           ├── schema.py
│           └── store.py
├── tests/
│   └── test_graph/
│       ├── __init__.py
│       ├── test_models.py
│       └── test_store.py
├── cli/
│   └── main.py
└── data/
    └── .gitkeep
```

---

## Vincoli architetturali (da CLAUDE.md)

- **Mai `DELETE`** su NodeEntity, NodeState, o archi — solo soft delete / invalidazione
- **Isolamento multi-tenant** — ogni query filtra per `user_id`
- **UUID come `str`** — compatibilità Kuzu
- **Type hints ovunque**
- **Docstring su ogni classe pubblica**
