# MemoryGraph — Fase 1b: Context Layer — Design Spec

**Data:** 2026-05-05
**Stato:** Approvato
**Scope:** Fase 1b — Context Layer: Project, WikiPage, DocumentIndex

---

## Obiettivo

Aggiungere al graph store il layer contestuale: un `Project` come contenitore della ricerca
con visibilità differenziata, una `WikiPage` come documento narrativo versionato,
e un `DocumentIndex` come ancora al mondo esterno.

Il principio architetturale critico di questa fase:
`Project.full_context` non deve mai uscire dal layer agente per default.
Il sistema rende difficile fare la cosa sbagliata — non solo documenta l'intenzione.

---

## Stack

| Componente | Scelta |
|---|---|
| Linguaggio | Python 3.11+ con type hints ovunque |
| Graph DB | Kuzu (stesso file di Fase 1) |
| Package manager | uv |
| CLI framework | Typer (esteso) |
| Test | pytest — fixture `tmp_path`, un test per ogni metodo pubblico |

---

## Architettura

```
src/memorygraph/
├── graph/                      ← Fase 1 (modifiche additive solo)
│   ├── models.py               ← +Project, +WikiEntity, +WikiState, +DocumentIndex
│   ├── schema.py               ← invariato
│   └── store.py                ← invariato
│
└── context/                    ← Fase 1b (nuovo)
    ├── __init__.py             ← esporta ContextStore
    ├── schema.py               ← init_context_schema(conn)
    ├── project.py              ← ProjectStore(conn)
    ├── wiki.py                 ← WikiStore(conn)
    └── documents.py            ← DocumentStore(conn)
```

**Flusso di inizializzazione:**

```
ContextStore(db_path)
  └── kuzu.Database(db_path) + kuzu.Connection(db)
  └── init_context_schema(conn)
  └── self.projects = ProjectStore(conn)
  └── self.wiki     = WikiStore(conn)
  └── self.documents = DocumentStore(conn)
```

**Due connessioni allo stesso file Kuzu** — `GraphStore` e `ContextStore` aprono
connessioni indipendenti. Accettabile per un processo CLI seriale.
Il refactor a connessione condivisa è rinviato alla Fase 2, quando il Memory Agent
avrà bisogno di accedere a entrambi i layer nello stesso contesto.

**`GraphStore` rimane invariato.** Zero dipendenze dal context layer.

---

## Schema Kuzu — `context/schema.py`

### Node Tables

```cypher
CREATE NODE TABLE IF NOT EXISTS Project (
    id         STRING,
    user_id    STRING,
    title      STRING,
    objective  STRING,
    summary    STRING,
    full_context STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    PRIMARY KEY (id)
)

CREATE NODE TABLE IF NOT EXISTS WikiEntity (
    id         STRING,
    user_id    STRING,
    project_id STRING,
    title      STRING,
    created_at TIMESTAMP,
    is_deleted BOOLEAN,
    PRIMARY KEY (id)
)

CREATE NODE TABLE IF NOT EXISTS WikiState (
    id         STRING,
    version    INT64,
    content    STRING,
    summary    STRING,
    created_at TIMESTAMP,
    PRIMARY KEY (id)
)
-- wiki_id NON è in Kuzu: la FK è nel dataclass Python, popolata dalla query su WIKI_HAS_STATE.
-- Stesso pattern di NodeState.node_id nella Fase 1.

CREATE NODE TABLE IF NOT EXISTS DocumentIndex (
    id         STRING,
    user_id    STRING,
    title      STRING,
    doi        STRING,
    url        STRING,
    authors    STRING,
    pub_date   STRING,
    created_at TIMESTAMP,
    PRIMARY KEY (id)
)
```

### Rel Tables

```cypher
CREATE REL TABLE IF NOT EXISTS WIKI_HAS_STATE (
    FROM WikiEntity TO WikiState
)

CREATE REL TABLE IF NOT EXISTS BELONGS_TO (
    FROM NodeEntity TO Project
)

CREATE REL TABLE IF NOT EXISTS WIKI_COVERS (
    FROM WikiEntity TO NodeEntity
)

CREATE REL TABLE IF NOT EXISTS REFERENCES_DOC (
    FROM NodeEntity TO DocumentIndex
)
```

**Note di schema:**
- `WikiEntity.project_id` — FK logico, non un arco Kuzu. La WikiPage appartiene sempre a un Project.
- `WikiState.wiki_id` — FK logico verso WikiEntity, come `NodeState.node_id` nella Fase 1.
- `DocumentIndex.authors` — stringa comma-separated (es. `"Rossi M, Bianchi A"`).
- `DocumentIndex.pub_date` — stringa `YYYY-MM-DD`.
- `BELONGS_TO` collega `NodeEntity` (graph layer) a `Project` (context layer). Creato solo da `ContextStore.attach_node()` — nessun sub-store attraversa il confine di layer.

---

## Modelli Python — aggiunte a `graph/models.py`

```python
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
    """Una versione del contenuto di una WikiPage."""
    id: str
    wiki_id: str
    version: int
    content: str
    summary: str    # "cosa è cambiato in questa versione" — non trigger epistemico
    created_at: datetime


@dataclass
class DocumentIndex:
    """Ancora al mondo esterno — paper, dataset, protocollo."""
    id: str
    user_id: str
    title: str
    doi: str | None
    url: str | None
    authors: str | None    # comma-separated
    pub_date: str | None   # YYYY-MM-DD
    created_at: datetime
```

`NodeType` e `EdgeType` **non vengono modificati.** `Project`, `WikiEntity`, `DocumentIndex`
hanno tabelle Kuzu dedicate — non passano per `NodeEntity`.
Le rel dedicate (`BELONGS_TO`, `WIKI_COVERS`, `REFERENCES_DOC`) hanno il tipo
implicito nel nome della tabella — nessun campo `type` necessario.

---

## API dei Store

### `ContextStore` (`context/__init__.py`)

```python
class ContextStore:
    """Facade del context layer. Unico punto d'ingresso per CLI e agente."""

    projects: ProjectStore
    wiki: WikiStore
    documents: DocumentStore

    def __init__(self, db_path: str) -> None:
        """Apre connessione Kuzu, inizializza schema, istanzia sub-store."""

    def attach_node(self, node_id: str, project_id: str) -> None:
        """
        Crea arco BELONGS_TO (NodeEntity → Project).
        Unica operazione cross-layer — nessun sub-store attraversa il confine.
        """
```

---

### `ProjectStore` (`context/project.py`)

```python
class ProjectStore:
    """Gestisce Project: creazione, lettura con visibilità controllata, aggiornamento."""

    def create_project(
        self,
        user_id: str,
        title: str,
        objective: str,
        summary: str,
        full_context: str,
    ) -> Project:
        """Crea un nuovo Project. Ritorna il Project completo (uso interno)."""

    def get_project(
        self,
        project_id: str,
        *,
        agent_context: bool = False,
    ) -> Project | None:
        """
        Ritorna il Project.
        agent_context=False (default): full_context = "" nel Project restituito.
        agent_context=True: full_context incluso — solo per il Memory Agent.
        Il default sicuro rende impossibile esporre full_context per distrazione.
        """

    def get_project_summary(self, project_id: str) -> dict | None:
        """
        Ritorna solo i campi pubblici: {id, title, objective, summary}.
        Ritorna dict (non Project) per rendere esplicito a livello di tipo
        che full_context non è presente.
        """

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
```

---

### `WikiStore` (`context/wiki.py`)

```python
class WikiStore:
    """Gestisce WikiPage: creazione, versionamento, link a nodi epistemici."""

    def create_wiki_page(
        self,
        user_id: str,
        project_id: str,
        title: str,
        content: str,
        summary: str,
    ) -> WikiEntity:
        """Crea WikiEntity + primo WikiState (version=1)."""

    def update_wiki_page(
        self,
        wiki_id: str,
        content: str,
        summary: str,
    ) -> WikiState:
        """Crea un nuovo WikiState (version = max + 1). Non modifica i precedenti."""

    def get_wiki_history(self, wiki_id: str) -> list[WikiState]:
        """Tutti i WikiState in ordine cronologico (version ASC)."""

    def list_wiki_pages(
        self,
        project_id: str,
    ) -> list[tuple[WikiEntity, WikiState]]:
        """WikiPage del progetto con lo stato più recente. Escluse le deleted."""

    def link_to_nodes(self, wiki_id: str, node_ids: list[str]) -> None:
        """
        Crea archi WIKI_COVERS (WikiEntity → NodeEntity).
        Idempotente: se il link esiste già, non duplica.
        """
```

---

### `DocumentStore` (`context/documents.py`)

```python
class DocumentStore:
    """Gestisce DocumentIndex: ancore al mondo esterno con metadati."""

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

    def get_document(self, doc_id: str) -> DocumentIndex | None:
        """Ritorna il DocumentIndex o None se non esiste."""

    def list_documents(self, user_id: str) -> list[DocumentIndex]:
        """Lista tutti i documenti dell'utente."""

    def reference_document(self, node_id: str, doc_id: str) -> None:
        """
        Crea arco REFERENCES_DOC (NodeEntity → DocumentIndex).
        Idempotente: non duplica se il link esiste già.
        Non esposto in CLI in Fase 1b — uso programmatico o Fase 2.
        """
```

---

## CLI — nuovi comandi

Tutti i comandi della Fase 1 rimangono invariati.

```bash
# Project
mg project-create \
  --user-id <str> --title <str> --objective <str> \
  --summary <str> --full-context <str>
# Output: "✓ Project creato: <id>"
# full_context non compare mai nell'output

# WikiPage
mg wiki-add \
  --user-id <str> --project-id <str> --title <str> \
  --content <str> --summary <str> \
  [--node-ids <n1,n2,...>]
# --node-ids: crea WIKI_COVERS automaticamente
# Output: "✓ WikiPage creata: <id> (v1)"

# DocumentIndex
mg doc-add \
  --user-id <str> --title <str> \
  [--doi <str>] [--url <str>] [--authors <str>] [--pub-date <YYYY-MM-DD>]
# Output: "✓ Documento aggiunto: <id>"

# Project assignment (appartiene_a)
mg project-assign \
  --node-id <str> --project-id <str>
# Output: "✓ Nodo <id[:8]> assegnato al project <id[:8]>"
```

`ref-add` (NodeEntity → DocumentIndex) è implementato nel store ma non esposto in CLI
in Fase 1b — lo espone la Fase 2 quando il Memory Agent popola i reference automaticamente.

---

## Testing

### Strategia

- Ogni test istanzia `ContextStore` su `tmp_path` — nessun DB condiviso, zero mock.
- Un test per ogni metodo pubblico.
- Target copertura: >80% (allineato a Fase 1).
- Test separati per `ProjectStore`, `WikiStore`, `DocumentStore`, `ContextStore`.

### Casi per `ProjectStore`

| Metodo | Casi |
|---|---|
| `create_project` | crea project, ritorna Project completo |
| `get_project` | default: full_context=""; agent_context=True: full_context incluso; None se non esiste |
| `get_project_summary` | ritorna dict con solo campi pubblici; None se non esiste |
| `update_project` | aggiorna solo campi passati; updated_at aggiornato |
| `list_projects` | default: full_context="" in ogni item; agent_context=True: incluso; isolamento user_id |

### Architectural Invariant Test — `ProjectStore`

```python
def test_full_context_not_in_public_output():
    """
    Guardrail architetturale: full_context non deve mai comparire
    nell'output pubblico di ProjectStore per default.
    Se questo test rompe, qualcuno ha esposto full_context per sbaglio.
    """
    store = ProjectStore(conn)
    store.create_project("u1", "Titolo", "Obiettivo",
                         "Summary pubblica", "Contesto privato")

    # get_project senza agent_context
    project = store.get_project(project_id)
    assert project.full_context == ""

    # get_project_summary
    summary = store.get_project_summary(project_id)
    assert "full_context" not in summary
    assert "Contesto privato" not in str(summary)

    # list_projects senza agent_context
    projects = store.list_projects("u1")
    for p in projects:
        assert p.full_context == ""
```

### Casi per `WikiStore`

| Metodo | Casi |
|---|---|
| `create_wiki_page` | crea WikiEntity + WikiState v1, project_id corretto |
| `update_wiki_page` | versione incrementa, stato precedente preservato |
| `get_wiki_history` | ordine ASC, tutti gli stati |
| `list_wiki_pages` | solo non-deleted, stato più recente, isolamento project_id |
| `link_to_nodes` | crea WIKI_COVERS, idempotente (doppia chiamata non duplica) |

### Casi per `DocumentStore`

| Metodo | Casi |
|---|---|
| `add_document` | crea con campi opzionali None, tutti i campi valorizzati |
| `get_document` | ritorna DocumentIndex, None se non esiste |
| `list_documents` | isolamento user_id |
| `reference_document` | crea REFERENCES_DOC, idempotente |

### Casi per `ContextStore`

| Metodo | Casi |
|---|---|
| `attach_node` | crea BELONGS_TO; node_id e project_id esistenti |

---

## Struttura file — delta rispetto a Fase 1

```
src/memorygraph/
├── graph/
│   └── models.py               ← +Project, +WikiEntity, +WikiState, +DocumentIndex
│
└── context/
    ├── __init__.py             ← ContextStore
    ├── schema.py               ← init_context_schema(conn)
    ├── project.py              ← ProjectStore
    ├── wiki.py                 ← WikiStore
    └── documents.py            ← DocumentStore

tests/
└── test_context/
    ├── __init__.py
    ├── test_project.py
    ├── test_wiki.py
    ├── test_documents.py
    └── test_context_store.py

cli/
└── main.py                     ← +project-create, +wiki-add, +doc-add, +project-assign
```

---

## Vincoli architetturali

- `GraphStore` e `graph/store.py` **non vengono modificati** — zero rischio di regressione.
- `Project.full_context` non compare mai in output CLI, log, o dict pubblici.
- `BELONGS_TO` è creato solo da `ContextStore.attach_node()` — nessun sub-store attraversa il confine di layer.
- `WikiEntity.is_deleted = True` è soft delete — mai `DELETE` nel DB.
- `init_context_schema` è idempotente — `IF NOT EXISTS` su ogni `CREATE`.
- UUID: sempre `str`, mai oggetti UUID nativi (compatibilità Kuzu).
- `datetime`: sempre `datetime.now(timezone.utc).replace(tzinfo=None)` (pattern Fase 1).

---

*Ultima modifica: 2026-05-05 — Fase 1b design approvato*
