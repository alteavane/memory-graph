# MemoryGraph Fase 1b — Context Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere il Context Layer al graph store esistente: `Project` con visibilità differenziata `summary`/`full_context`, `WikiPage` versionata con titolo stabile, `DocumentIndex` con metadati bibliografici, e 4 nuovi comandi CLI.

**Architecture:** `ContextStore(db_path)` è il facade: apre una connessione Kuzu indipendente da `GraphStore`, inizializza entrambi gli schema (graph + context), e istanzia i tre sub-store con la connessione condivisa. `ProjectStore`, `WikiStore`, `DocumentStore` ricevono `conn: kuzu.Connection` nel costruttore. `GraphStore` rimane invariato — zero regressioni sui test esistenti.

**Tech Stack:** Python 3.11+, kuzu, typer, rich, pytest (fixture `tmp_path`)

---

## File Map

| File | Azione | Responsabilità |
|---|---|---|
| `src/memorygraph/graph/models.py` | Modifica | +`Project`, `WikiEntity`, `WikiState`, `DocumentIndex` dataclass |
| `src/memorygraph/context/__init__.py` | Crea | `ContextStore` — facade con `attach_node` |
| `src/memorygraph/context/schema.py` | Crea | `init_context_schema(conn)` — 4 node + 4 rel tables |
| `src/memorygraph/context/project.py` | Crea | `ProjectStore` — CRUD + `agent_context` guard |
| `src/memorygraph/context/wiki.py` | Crea | `WikiStore` — versionamento WikiPage |
| `src/memorygraph/context/documents.py` | Crea | `DocumentStore` — DocumentIndex + REFERENCES_DOC |
| `tests/test_context/__init__.py` | Crea | Package marker |
| `tests/test_context/test_project.py` | Crea | Test `ProjectStore` incl. architectural invariant |
| `tests/test_context/test_wiki.py` | Crea | Test `WikiStore` |
| `tests/test_context/test_documents.py` | Crea | Test `DocumentStore` |
| `tests/test_context/test_context_store.py` | Crea | Test `ContextStore` + `attach_node` |
| `cli/main.py` | Modifica | +`project-create`, `project-assign`, `wiki-add`, `doc-add` |
| `CLAUDE.md` | Modifica | Roadmap: Fase 1b completata |

---

## Task 1: Nuovi dataclass in `models.py`

**Files:**
- Modify: `src/memorygraph/graph/models.py`
- Modify: `tests/test_graph/test_models.py`

- [ ] **Step 1: Aggiungere test in `tests/test_graph/test_models.py`**

Aggiungi in coda al file:

```python
# ── Context Layer models ──────────────────────────────────────────────────────

def test_project_fields():
    now = datetime.now(timezone.utc)
    p = Project(
        id="p1", user_id="u1", title="T", objective="O",
        summary="S", full_context="FC", created_at=now, updated_at=now,
    )
    assert p.summary == "S"
    assert p.full_context == "FC"
    assert p.updated_at == now


def test_wiki_entity_defaults():
    now = datetime.now(timezone.utc)
    w = WikiEntity(id="w1", user_id="u1", project_id="p1", title="Title", created_at=now)
    assert w.is_deleted is False


def test_wiki_state_has_summary_not_trigger():
    now = datetime.now(timezone.utc)
    s = WikiState(id="s1", wiki_id="w1", version=1, content="C", summary="Cosa è cambiato", created_at=now)
    assert s.summary == "Cosa è cambiato"
    assert s.version == 1


def test_document_index_optional_fields_none():
    now = datetime.now(timezone.utc)
    d = DocumentIndex(id="d1", user_id="u1", title="Paper", doi=None,
                      url=None, authors=None, pub_date=None, created_at=now)
    assert d.doi is None
    assert d.pub_date is None


def test_document_index_with_all_fields():
    now = datetime.now(timezone.utc)
    d = DocumentIndex(id="d1", user_id="u1", title="Paper",
                      doi="10.1000/xyz", url="https://example.com",
                      authors="Rossi M, Bianchi A", pub_date="2024-01-15",
                      created_at=now)
    assert d.doi == "10.1000/xyz"
    assert d.authors == "Rossi M, Bianchi A"
```

Aggiungi anche gli import necessari in testa al file (dopo gli import esistenti):

```python
from memorygraph.graph.models import (
    Edge, EdgeType, NodeEntity, NodeState, NodeType,
    Project, WikiEntity, WikiState, DocumentIndex,
)
```

- [ ] **Step 2: Eseguire il test per verificare che fallisce**

```bash
uv run pytest tests/test_graph/test_models.py -v -k "project or wiki or document"
```

Expected: `ImportError: cannot import name 'Project'`

- [ ] **Step 3: Aggiungere i 4 dataclass a `src/memorygraph/graph/models.py`**

Aggiungi in coda al file (dopo la classe `Edge`):

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
```

- [ ] **Step 4: Aggiornare l'import in testa a `test_models.py`**

Sostituisci la riga import esistente con:

```python
from memorygraph.graph.models import (
    Edge, EdgeType, NodeEntity, NodeState, NodeType,
    Project, WikiEntity, WikiState, DocumentIndex,
)
```

- [ ] **Step 5: Eseguire i test**

```bash
uv run pytest tests/test_graph/test_models.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/memorygraph/graph/models.py tests/test_graph/test_models.py
git commit -m "feat: Project, WikiEntity, WikiState, DocumentIndex dataclasses"
```

---

## Task 2: `context/schema.py` — schema Kuzu del Context Layer

**Files:**
- Create: `src/memorygraph/context/__init__.py` (vuoto per ora)
- Create: `src/memorygraph/context/schema.py`

- [ ] **Step 1: Creare il package marker**

```bash
mkdir -p src/memorygraph/context
touch src/memorygraph/context/__init__.py
```

- [ ] **Step 2: Creare `src/memorygraph/context/schema.py`**

```python
import kuzu

_CONTEXT_SCHEMA_STATEMENTS = [
    """
    CREATE NODE TABLE IF NOT EXISTS Project (
        id           STRING,
        user_id      STRING,
        title        STRING,
        objective    STRING,
        summary      STRING,
        full_context STRING,
        created_at   TIMESTAMP,
        updated_at   TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS WikiEntity (
        id         STRING,
        user_id    STRING,
        project_id STRING,
        title      STRING,
        created_at TIMESTAMP,
        is_deleted BOOLEAN,
        PRIMARY KEY (id)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS WikiState (
        id         STRING,
        version    INT64,
        content    STRING,
        summary    STRING,
        created_at TIMESTAMP,
        PRIMARY KEY (id)
    )
    """,
    """
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
    """,
    """
    CREATE REL TABLE IF NOT EXISTS WIKI_HAS_STATE (
        FROM WikiEntity TO WikiState
    )
    """,
    # BELONGS_TO richiede che NodeEntity esista — chiamare dopo init_schema()
    """
    CREATE REL TABLE IF NOT EXISTS BELONGS_TO (
        FROM NodeEntity TO Project
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS WIKI_COVERS (
        FROM WikiEntity TO NodeEntity
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS REFERENCES_DOC (
        FROM NodeEntity TO DocumentIndex
    )
    """,
]


def init_context_schema(conn: kuzu.Connection) -> None:
    """Crea le tabelle del context layer. Idempotente. Deve essere chiamata dopo init_schema()."""
    for stmt in _CONTEXT_SCHEMA_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
```

- [ ] **Step 3: Verificare che lo schema si crea senza errori**

```bash
uv run python -c "
import kuzu, tempfile, os
from memorygraph.graph.schema import init_schema
from memorygraph.context.schema import init_context_schema
with tempfile.TemporaryDirectory() as d:
    db = kuzu.Database(os.path.join(d, 'test.kuzu'))
    conn = kuzu.Connection(db)
    init_schema(conn)           # NodeEntity deve esistere prima di BELONGS_TO
    init_context_schema(conn)
    init_context_schema(conn)   # seconda chiamata: idempotente
    print('Context schema OK')
"
```

Expected: `Context schema OK`

- [ ] **Step 4: Commit**

```bash
git add src/memorygraph/context/__init__.py src/memorygraph/context/schema.py
git commit -m "feat: context/schema.py — 4 node tables + 4 rel tables (idempotente)"
```

---

## Task 3: `ProjectStore` — tutti i metodi

**Files:**
- Create: `src/memorygraph/context/project.py`
- Create: `tests/test_context/__init__.py`
- Create: `tests/test_context/test_project.py`

- [ ] **Step 1: Creare `tests/test_context/__init__.py`**

```bash
mkdir -p tests/test_context
touch tests/test_context/__init__.py
```

- [ ] **Step 2: Creare `tests/test_context/test_project.py`**

```python
from __future__ import annotations

import time

import kuzu
import pytest

from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_context_schema(c)
    return c


@pytest.fixture
def store(conn):
    return ProjectStore(conn)


# ── create_project ────────────────────────────────────────────────────────────

class TestCreateProject:
    def test_returns_project_with_all_fields(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary", "FullCtx")
        assert p.id is not None
        assert p.user_id == "u1"
        assert p.title == "Titolo"
        assert p.objective == "Obiettivo"
        assert p.summary == "Summary"
        assert p.full_context == "FullCtx"

    def test_created_at_equals_updated_at_on_creation(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC")
        assert p.created_at == p.updated_at

    def test_each_project_unique_id(self, store):
        p1 = store.create_project("u1", "T1", "O", "S", "FC")
        p2 = store.create_project("u1", "T2", "O", "S", "FC")
        assert p1.id != p2.id


# ── get_project ───────────────────────────────────────────────────────────────

class TestGetProject:
    def test_returns_none_for_missing(self, store):
        assert store.get_project("nonexistent") is None

    def test_default_strips_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "private")
        result = store.get_project(p.id)
        assert result is not None
        assert result.full_context == ""

    def test_agent_context_returns_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "private")
        result = store.get_project(p.id, agent_context=True)
        assert result is not None
        assert result.full_context == "private"

    def test_public_fields_always_present(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary pub", "FC")
        result = store.get_project(p.id)
        assert result.title == "Titolo"
        assert result.summary == "Summary pub"


# ── get_project_summary ───────────────────────────────────────────────────────

class TestGetProjectSummary:
    def test_returns_dict_with_public_fields(self, store):
        p = store.create_project("u1", "Titolo", "Obiettivo", "Summary", "private")
        s = store.get_project_summary(p.id)
        assert s is not None
        assert s["id"] == p.id
        assert s["title"] == "Titolo"
        assert s["objective"] == "Obiettivo"
        assert s["summary"] == "Summary"

    def test_full_context_not_in_dict(self, store):
        p = store.create_project("u1", "T", "O", "S", "DATI_PRIVATI")
        s = store.get_project_summary(p.id)
        assert "full_context" not in s
        assert "DATI_PRIVATI" not in str(s)

    def test_returns_none_for_missing(self, store):
        assert store.get_project_summary("nonexistent") is None


# ── update_project ────────────────────────────────────────────────────────────

class TestUpdateProject:
    def test_updates_only_specified_fields(self, store):
        p = store.create_project("u1", "Old", "ObjOld", "S", "FC")
        updated = store.update_project(p.id, title="New")
        assert updated.title == "New"
        assert updated.objective == "ObjOld"   # invariato
        assert updated.summary == "S"          # invariato

    def test_updated_at_changes(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC")
        time.sleep(0.01)
        updated = store.update_project(p.id, summary="Nuova summary")
        assert updated.updated_at >= p.updated_at

    def test_raises_for_missing_project(self, store):
        with pytest.raises(ValueError, match="not found"):
            store.update_project("nonexistent", title="X")

    def test_update_full_context(self, store):
        p = store.create_project("u1", "T", "O", "S", "FC_old")
        updated = store.update_project(p.id, full_context="FC_new")
        result = store.get_project(updated.id, agent_context=True)
        assert result.full_context == "FC_new"


# ── list_projects ─────────────────────────────────────────────────────────────

class TestListProjects:
    def test_returns_all_projects_for_user(self, store):
        store.create_project("u1", "T1", "O", "S", "FC")
        store.create_project("u1", "T2", "O", "S", "FC")
        assert len(store.list_projects("u1")) == 2

    def test_isolates_by_user_id(self, store):
        store.create_project("u1", "T1", "O", "S", "FC")
        store.create_project("u2", "T2", "O", "S", "FC")
        assert len(store.list_projects("u1")) == 1
        assert len(store.list_projects("u2")) == 1

    def test_default_strips_full_context(self, store):
        store.create_project("u1", "T", "O", "S", "private")
        for p in store.list_projects("u1"):
            assert p.full_context == ""

    def test_agent_context_returns_full_context(self, store):
        store.create_project("u1", "T", "O", "S", "private")
        for p in store.list_projects("u1", agent_context=True):
            assert p.full_context == "private"

    def test_empty_list_for_user_without_projects(self, store):
        assert store.list_projects("nobody") == []


# ── Architectural Invariant ───────────────────────────────────────────────────

class TestArchitecturalInvariant:
    def test_full_context_never_in_public_output(self, store):
        """
        Guardrail architetturale: full_context NON deve mai comparire
        nell'output pubblico di ProjectStore per default.
        Se questo test rompe, qualcuno ha esposto full_context per sbaglio.
        """
        p = store.create_project("u1", "T", "O", "S", "DATI_SEGRETI")

        # get_project senza agent_context
        result = store.get_project(p.id)
        assert result.full_context == ""

        # get_project_summary
        summary = store.get_project_summary(p.id)
        assert "full_context" not in summary
        assert "DATI_SEGRETI" not in str(summary)

        # list_projects senza agent_context
        for proj in store.list_projects("u1"):
            assert proj.full_context == ""
```

- [ ] **Step 3: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_context/test_project.py -v
```

Expected: `ModuleNotFoundError: No module named 'memorygraph.context.project'`

- [ ] **Step 4: Creare `src/memorygraph/context/project.py`**

```python
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
```

- [ ] **Step 5: Eseguire i test**

```bash
uv run pytest tests/test_context/test_project.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/memorygraph/context/project.py tests/test_context/__init__.py tests/test_context/test_project.py
git commit -m "feat: ProjectStore — CRUD + agent_context guard + architectural invariant test"
```

---

## Task 4: `WikiStore` — `create_wiki_page`, `update_wiki_page`, `get_wiki_history`

**Files:**
- Create: `src/memorygraph/context/wiki.py`
- Create: `tests/test_context/test_wiki.py`

- [ ] **Step 1: Creare `tests/test_context/test_wiki.py`**

```python
from __future__ import annotations

import kuzu
import pytest

from memorygraph.context.schema import init_context_schema
from memorygraph.context.wiki import WikiStore
from memorygraph.context.project import ProjectStore
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_context_schema(c)
    return c


@pytest.fixture
def project_id(conn):
    return ProjectStore(conn).create_project(
        "u1", "Progetto Test", "Obiettivo", "Summary", "FC"
    ).id


@pytest.fixture
def wiki(conn):
    return WikiStore(conn)


# ── create_wiki_page ──────────────────────────────────────────────────────────

class TestCreateWikiPage:
    def test_returns_wiki_entity(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "Titolo", "Contenuto", "Prima versione")
        assert entity.id is not None
        assert entity.title == "Titolo"
        assert entity.project_id == project_id
        assert entity.user_id == "u1"
        assert entity.is_deleted is False

    def test_creates_first_state_version_1(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "Contenuto v1", "Creazione")
        history = wiki.get_wiki_history(entity.id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].content == "Contenuto v1"
        assert history[0].summary == "Creazione"
        assert history[0].wiki_id == entity.id

    def test_each_page_has_unique_id(self, wiki, project_id):
        w1 = wiki.create_wiki_page("u1", project_id, "T1", "C", "S")
        w2 = wiki.create_wiki_page("u1", project_id, "T2", "C", "S")
        assert w1.id != w2.id


# ── update_wiki_page ──────────────────────────────────────────────────────────

class TestUpdateWikiPage:
    def test_increments_version(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        state = wiki.update_wiki_page(entity.id, "v2", "Aggiunto paragrafo")
        assert state.version == 2
        assert state.content == "v2"
        assert state.summary == "Aggiunto paragrafo"

    def test_preserves_previous_states(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        history = wiki.get_wiki_history(entity.id)
        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].content == "v1"
        assert history[1].version == 2
        assert history[1].content == "v2"

    def test_multiple_updates_increment_correctly(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        state3 = wiki.update_wiki_page(entity.id, "v3", "s3")
        assert state3.version == 3
        history = wiki.get_wiki_history(entity.id)
        assert [s.version for s in history] == [1, 2, 3]


# ── get_wiki_history ──────────────────────────────────────────────────────────

class TestGetWikiHistory:
    def test_returns_states_in_version_order(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        history = wiki.get_wiki_history(entity.id)
        assert history[0].version == 1
        assert history[1].version == 2

    def test_returns_empty_for_unknown_wiki(self, wiki):
        assert wiki.get_wiki_history("nonexistent") == []
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_context/test_wiki.py -v
```

Expected: `ModuleNotFoundError: No module named 'memorygraph.context.wiki'`

- [ ] **Step 3: Creare `src/memorygraph/context/wiki.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu

from memorygraph.graph.models import WikiEntity, WikiState


class WikiStore:
    """Gestisce WikiPage: creazione, versionamento, link a nodi epistemici."""

    def __init__(self, conn: kuzu.Connection) -> None:
        self._conn = conn

    def create_wiki_page(
        self,
        user_id: str,
        project_id: str,
        title: str,
        content: str,
        summary: str,
    ) -> WikiEntity:
        """Crea WikiEntity + primo WikiState (version=1)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        wiki_id = str(uuid.uuid4())
        state_id = str(uuid.uuid4())
        self._conn.execute(
            """
            CREATE (w:WikiEntity {
                id: $id, user_id: $uid, project_id: $pid,
                title: $title, created_at: $now, is_deleted: false
            })
            """,
            {"id": wiki_id, "uid": user_id, "pid": project_id, "title": title, "now": now},
        )
        self._conn.execute(
            """
            CREATE (s:WikiState {
                id: $id, version: 1, content: $content, summary: $summary, created_at: $now
            })
            """,
            {"id": state_id, "content": content, "summary": summary, "now": now},
        )
        self._conn.execute(
            "MATCH (w:WikiEntity), (s:WikiState) WHERE w.id = $wid AND s.id = $sid "
            "CREATE (w)-[:WIKI_HAS_STATE]->(s)",
            {"wid": wiki_id, "sid": state_id},
        )
        return WikiEntity(
            id=wiki_id, user_id=user_id, project_id=project_id,
            title=title, created_at=now,
        )

    def update_wiki_page(self, wiki_id: str, content: str, summary: str) -> WikiState:
        """Crea un nuovo WikiState (version = max + 1). Non modifica i precedenti."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        state_id = str(uuid.uuid4())
        result = self._conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState) "
            "WHERE w.id = $wid RETURN MAX(s.version) AS max_v",
            {"wid": wiki_id},
        )
        row = result.get_next()
        max_version: int = row[0] if row[0] is not None else 0
        new_version = max_version + 1
        self._conn.execute(
            """
            CREATE (s:WikiState {
                id: $id, version: $version, content: $content,
                summary: $summary, created_at: $now
            })
            """,
            {"id": state_id, "version": new_version, "content": content,
             "summary": summary, "now": now},
        )
        self._conn.execute(
            "MATCH (w:WikiEntity), (s:WikiState) WHERE w.id = $wid AND s.id = $sid "
            "CREATE (w)-[:WIKI_HAS_STATE]->(s)",
            {"wid": wiki_id, "sid": state_id},
        )
        return WikiState(
            id=state_id, wiki_id=wiki_id, version=new_version,
            content=content, summary=summary, created_at=now,
        )

    def get_wiki_history(self, wiki_id: str) -> list[WikiState]:
        """Tutti i WikiState del nodo in ordine cronologico (version ASC)."""
        result = self._conn.execute(
            """
            MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState)
            WHERE w.id = $wid
            RETURN s.id, s.version, s.content, s.summary, s.created_at
            ORDER BY s.version ASC
            """,
            {"wid": wiki_id},
        )
        states: list[WikiState] = []
        while result.has_next():
            row = result.get_next()
            states.append(WikiState(
                id=row[0], wiki_id=wiki_id, version=row[1],
                content=row[2], summary=row[3], created_at=row[4],
            ))
        return states
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_context/test_wiki.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/context/wiki.py tests/test_context/test_wiki.py
git commit -m "feat: WikiStore — create_wiki_page, update_wiki_page, get_wiki_history"
```

---

## Task 5: `WikiStore` — `list_wiki_pages`, `link_to_nodes`

**Files:**
- Modify: `src/memorygraph/context/wiki.py`
- Modify: `tests/test_context/test_wiki.py`

- [ ] **Step 1: Aggiungere i test in `tests/test_context/test_wiki.py`**

Aggiungi in coda al file (dopo `TestGetWikiHistory`):

```python
# ── list_wiki_pages ───────────────────────────────────────────────────────────

class TestListWikiPages:
    def test_returns_latest_state_only(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "v1", "s1")
        wiki.update_wiki_page(entity.id, "v2", "s2")
        pages = wiki.list_wiki_pages(project_id)
        assert len(pages) == 1
        _, state = pages[0]
        assert state.version == 2
        assert state.content == "v2"

    def test_returns_entity_and_state_pair(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "Titolo", "C", "S")
        pages = wiki.list_wiki_pages(project_id)
        ent, state = pages[0]
        assert ent.title == "Titolo"
        assert ent.id == entity.id
        assert state.version == 1

    def test_excludes_deleted_pages(self, wiki, project_id, conn):
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        conn.execute(
            "MATCH (w:WikiEntity) WHERE w.id = $id SET w.is_deleted = true",
            {"id": entity.id},
        )
        assert wiki.list_wiki_pages(project_id) == []

    def test_multiple_pages_returned(self, wiki, project_id):
        wiki.create_wiki_page("u1", project_id, "T1", "C1", "S1")
        wiki.create_wiki_page("u1", project_id, "T2", "C2", "S2")
        assert len(wiki.list_wiki_pages(project_id)) == 2


# ── link_to_nodes ─────────────────────────────────────────────────────────────

class TestLinkToNodes:
    def _make_node(self, conn):
        """Helper: crea un NodeEntity nel DB per i test cross-layer."""
        import uuid as _uuid
        from datetime import datetime, timezone
        nid = str(_uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute(
            "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
            "created_at: $ts, is_deleted: false})",
            {"id": nid, "ts": now},
        )
        return nid

    def test_creates_wiki_covers_edges(self, wiki, project_id, conn):
        node_id = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [node_id])
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 1

    def test_idempotent_double_call(self, wiki, project_id, conn):
        node_id = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [node_id])
        wiki.link_to_nodes(entity.id, [node_id])   # seconda chiamata
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 1

    def test_links_multiple_nodes(self, wiki, project_id, conn):
        n1 = self._make_node(conn)
        n2 = self._make_node(conn)
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [n1, n2])
        result = conn.execute(
            "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
            "WHERE w.id = $wid RETURN count(*) AS c",
            {"wid": entity.id},
        )
        assert result.get_next()[0] == 2

    def test_empty_list_is_noop(self, wiki, project_id):
        entity = wiki.create_wiki_page("u1", project_id, "T", "C", "S")
        wiki.link_to_nodes(entity.id, [])   # deve completare senza errori
```

- [ ] **Step 2: Eseguire per verificare che i nuovi test falliscono**

```bash
uv run pytest tests/test_context/test_wiki.py::TestListWikiPages tests/test_context/test_wiki.py::TestLinkToNodes -v
```

Expected: `AttributeError: 'WikiStore' object has no attribute 'list_wiki_pages'`

- [ ] **Step 3: Aggiungere i metodi a `src/memorygraph/context/wiki.py`**

Aggiungi dopo `get_wiki_history`:

```python
    def list_wiki_pages(
        self,
        project_id: str,
    ) -> list[tuple[WikiEntity, WikiState]]:
        """WikiPage del progetto con lo stato più recente. Escluse le deleted."""
        result = self._conn.execute(
            """
            MATCH (w:WikiEntity)-[:WIKI_HAS_STATE]->(s:WikiState)
            WHERE w.project_id = $pid AND w.is_deleted = false
            RETURN w.id, w.user_id, w.project_id, w.title, w.created_at, w.is_deleted,
                   s.id, s.version, s.content, s.summary, s.created_at
            ORDER BY w.id ASC, s.version DESC
            """,
            {"pid": project_id},
        )
        seen: dict[str, tuple[WikiEntity, WikiState]] = {}
        while result.has_next():
            row = result.get_next()
            wiki_id = row[0]
            if wiki_id not in seen:
                entity = WikiEntity(
                    id=row[0], user_id=row[1], project_id=row[2],
                    title=row[3], created_at=row[4], is_deleted=row[5],
                )
                state = WikiState(
                    id=row[6], wiki_id=wiki_id, version=row[7],
                    content=row[8], summary=row[9], created_at=row[10],
                )
                seen[wiki_id] = (entity, state)
        return list(seen.values())

    def link_to_nodes(self, wiki_id: str, node_ids: list[str]) -> None:
        """Crea archi WIKI_COVERS (WikiEntity → NodeEntity). Idempotente."""
        for node_id in node_ids:
            result = self._conn.execute(
                "MATCH (w:WikiEntity)-[:WIKI_COVERS]->(n:NodeEntity) "
                "WHERE w.id = $wid AND n.id = $nid RETURN count(*) AS c",
                {"wid": wiki_id, "nid": node_id},
            )
            if result.get_next()[0] > 0:
                continue
            self._conn.execute(
                "MATCH (w:WikiEntity), (n:NodeEntity) "
                "WHERE w.id = $wid AND n.id = $nid "
                "CREATE (w)-[:WIKI_COVERS]->(n)",
                {"wid": wiki_id, "nid": node_id},
            )
```

- [ ] **Step 4: Eseguire tutti i test WikiStore**

```bash
uv run pytest tests/test_context/test_wiki.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/context/wiki.py tests/test_context/test_wiki.py
git commit -m "feat: WikiStore — list_wiki_pages, link_to_nodes (idempotente)"
```

---

## Task 6: `DocumentStore` — tutti i metodi

**Files:**
- Create: `src/memorygraph/context/documents.py`
- Create: `tests/test_context/test_documents.py`

- [ ] **Step 1: Creare `tests/test_context/test_documents.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import kuzu
import pytest

from memorygraph.context.documents import DocumentStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.schema import init_schema


@pytest.fixture
def conn(tmp_path):
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    c = kuzu.Connection(db)
    init_schema(c)
    init_context_schema(c)
    return c


@pytest.fixture
def docs(conn):
    return DocumentStore(conn)


def _make_node(conn):
    """Helper: crea un NodeEntity nel DB per i test cross-layer."""
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
        "created_at: $ts, is_deleted: false})",
        {"id": nid, "ts": now},
    )
    return nid


# ── add_document ──────────────────────────────────────────────────────────────

class TestAddDocument:
    def test_returns_document_with_required_fields(self, docs):
        d = docs.add_document("u1", "Paper sul pH")
        assert d.id is not None
        assert d.user_id == "u1"
        assert d.title == "Paper sul pH"
        assert d.doi is None
        assert d.url is None
        assert d.authors is None
        assert d.pub_date is None

    def test_returns_document_with_all_fields(self, docs):
        d = docs.add_document(
            "u1", "Paper completo",
            doi="10.1000/xyz123",
            url="https://example.com/paper",
            authors="Rossi M, Bianchi A",
            pub_date="2024-01-15",
        )
        assert d.doi == "10.1000/xyz123"
        assert d.url == "https://example.com/paper"
        assert d.authors == "Rossi M, Bianchi A"
        assert d.pub_date == "2024-01-15"

    def test_each_document_unique_id(self, docs):
        d1 = docs.add_document("u1", "P1")
        d2 = docs.add_document("u1", "P2")
        assert d1.id != d2.id


# ── get_document ──────────────────────────────────────────────────────────────

class TestGetDocument:
    def test_returns_document(self, docs):
        d = docs.add_document("u1", "Paper", doi="10.1/x")
        result = docs.get_document(d.id)
        assert result is not None
        assert result.id == d.id
        assert result.doi == "10.1/x"

    def test_optional_fields_round_trip_as_none(self, docs):
        d = docs.add_document("u1", "Paper senza metadati")
        result = docs.get_document(d.id)
        assert result.doi is None
        assert result.url is None
        assert result.authors is None
        assert result.pub_date is None

    def test_returns_none_for_missing(self, docs):
        assert docs.get_document("nonexistent") is None


# ── list_documents ────────────────────────────────────────────────────────────

class TestListDocuments:
    def test_returns_all_documents_for_user(self, docs):
        docs.add_document("u1", "P1")
        docs.add_document("u1", "P2")
        assert len(docs.list_documents("u1")) == 2

    def test_isolates_by_user_id(self, docs):
        docs.add_document("u1", "P1")
        docs.add_document("u2", "P2")
        assert len(docs.list_documents("u1")) == 1
        assert len(docs.list_documents("u2")) == 1

    def test_empty_list_for_user_without_documents(self, docs):
        assert docs.list_documents("nobody") == []


# ── reference_document ────────────────────────────────────────────────────────

class TestReferenceDocument:
    def test_creates_references_doc_edge(self, docs, conn):
        node_id = _make_node(conn)
        d = docs.add_document("u1", "Paper")
        docs.reference_document(node_id, d.id)
        result = conn.execute(
            "MATCH (n:NodeEntity)-[:REFERENCES_DOC]->(d:DocumentIndex) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1

    def test_idempotent_double_call(self, docs, conn):
        node_id = _make_node(conn)
        d = docs.add_document("u1", "Paper")
        docs.reference_document(node_id, d.id)
        docs.reference_document(node_id, d.id)   # seconda chiamata
        result = conn.execute(
            "MATCH (n:NodeEntity)-[:REFERENCES_DOC]->(d:DocumentIndex) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_context/test_documents.py -v
```

Expected: `ModuleNotFoundError: No module named 'memorygraph.context.documents'`

- [ ] **Step 3: Creare `src/memorygraph/context/documents.py`**

```python
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
```

- [ ] **Step 4: Eseguire i test**

```bash
uv run pytest tests/test_context/test_documents.py -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/context/documents.py tests/test_context/test_documents.py
git commit -m "feat: DocumentStore — add_document, get_document, list_documents, reference_document"
```

---

## Task 7: `ContextStore` — facade + `attach_node`

**Files:**
- Modify: `src/memorygraph/context/__init__.py`
- Create: `tests/test_context/test_context_store.py`

- [ ] **Step 1: Creare `tests/test_context/test_context_store.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from memorygraph.context import ContextStore
from memorygraph.context.project import ProjectStore
from memorygraph.context.wiki import WikiStore
from memorygraph.context.documents import DocumentStore


@pytest.fixture
def ctx(tmp_path):
    return ContextStore(str(tmp_path / "test.kuzu"))


def _make_node(ctx):
    """Helper: crea un NodeEntity tramite connessione condivisa di ContextStore."""
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ctx._conn.execute(
        "CREATE (n:NodeEntity {id: $id, user_id: 'u1', type: 'Observation', "
        "created_at: $ts, is_deleted: false})",
        {"id": nid, "ts": now},
    )
    return nid


class TestContextStoreInit:
    def test_projects_is_project_store(self, ctx):
        assert isinstance(ctx.projects, ProjectStore)

    def test_wiki_is_wiki_store(self, ctx):
        assert isinstance(ctx.wiki, WikiStore)

    def test_documents_is_document_store(self, ctx):
        assert isinstance(ctx.documents, DocumentStore)

    def test_sub_stores_share_connection(self, ctx):
        # Verifica che i dati scritti da un sub-store siano visibili agli altri
        # creando un Project e verificando che sia leggibile dalla stessa connessione
        p = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        result = ctx._conn.execute(
            "MATCH (p:Project) WHERE p.id = $pid RETURN p.title",
            {"pid": p.id},
        )
        assert result.get_next()[0] == "T"


class TestAttachNode:
    def test_creates_belongs_to_edge(self, ctx):
        node_id = _make_node(ctx)
        project = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        ctx.attach_node(node_id, project.id)
        result = ctx._conn.execute(
            "MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project) "
            "WHERE n.id = $nid RETURN count(*) AS c",
            {"nid": node_id},
        )
        assert result.get_next()[0] == 1

    def test_multiple_nodes_can_belong_to_same_project(self, ctx):
        n1 = _make_node(ctx)
        n2 = _make_node(ctx)
        project = ctx.projects.create_project("u1", "T", "O", "S", "FC")
        ctx.attach_node(n1, project.id)
        ctx.attach_node(n2, project.id)
        result = ctx._conn.execute(
            "MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project) "
            "WHERE p.id = $pid RETURN count(*) AS c",
            {"pid": project.id},
        )
        assert result.get_next()[0] == 2
```

- [ ] **Step 2: Eseguire per verificare che fallisce**

```bash
uv run pytest tests/test_context/test_context_store.py -v
```

Expected: `ImportError` perché `context/__init__.py` è vuoto.

- [ ] **Step 3: Implementare `src/memorygraph/context/__init__.py`**

```python
from __future__ import annotations

from pathlib import Path

import kuzu

from memorygraph.graph.schema import init_schema
from memorygraph.context.schema import init_context_schema
from memorygraph.context.project import ProjectStore
from memorygraph.context.wiki import WikiStore
from memorygraph.context.documents import DocumentStore


class ContextStore:
    """Facade del context layer. Unico punto d'ingresso per CLI e agente."""

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        init_schema(self._conn)           # NodeEntity deve esistere prima di BELONGS_TO
        init_context_schema(self._conn)
        self.projects = ProjectStore(self._conn)
        self.wiki = WikiStore(self._conn)
        self.documents = DocumentStore(self._conn)

    def attach_node(self, node_id: str, project_id: str) -> None:
        """Crea arco BELONGS_TO (NodeEntity → Project). Unica operazione cross-layer."""
        self._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) "
            "WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": node_id, "pid": project_id},
        )
```

- [ ] **Step 4: Eseguire tutti i test del context layer**

```bash
uv run pytest tests/test_context/ -v
```

Expected: tutti `PASSED`

- [ ] **Step 5: Eseguire anche i test della Fase 1 per verificare zero regressioni**

```bash
uv run pytest tests/test_graph/ -v
```

Expected: tutti `PASSED` — `GraphStore` non è stato toccato.

- [ ] **Step 6: Commit**

```bash
git add src/memorygraph/context/__init__.py tests/test_context/test_context_store.py
git commit -m "feat: ContextStore — facade con attach_node (BELONGS_TO cross-layer)"
```

---

## Task 8: CLI — `project-create`, `project-assign`

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Aggiungere import e helper in `cli/main.py`**

Aggiungi dopo `from memorygraph.graph.store import GraphStore`:

```python
from memorygraph.context import ContextStore
```

Aggiungi dopo la funzione `_get_store()`:

```python
def _get_context() -> ContextStore:
    return ContextStore(DB_PATH)
```

- [ ] **Step 2: Aggiungere i due comandi in coda a `cli/main.py`** (prima di `if __name__ == "__main__":`)

```python
@app.command(name="project-create")
def project_create(
    user_id: str = typer.Option(..., help="ID utente"),
    title: str = typer.Option(..., help="Titolo del progetto"),
    objective: str = typer.Option(..., help="Obiettivo della ricerca"),
    summary: str = typer.Option(..., help="Summary pubblico (viaggia con SubgraphToken)"),
    full_context: str = typer.Option(..., help="Contesto completo — PRIVATO, solo agente"),
) -> None:
    """Crea un nuovo Project con visibilità differenziata summary/full_context."""
    ctx = _get_context()
    project = ctx.projects.create_project(user_id, title, objective, summary, full_context)
    console.print(f"[green]✓[/green] Project creato: [bold]{project.id}[/bold]")
    console.print(f"  Titolo: {project.title}")
    console.print(f"  Summary: {project.summary}")


@app.command(name="project-assign")
def project_assign(
    node_id: str = typer.Option(..., help="ID del nodo epistemico"),
    project_id: str = typer.Option(..., help="ID del Project"),
) -> None:
    """Assegna un nodo a un Project (crea arco appartiene_a)."""
    ctx = _get_context()
    ctx.attach_node(node_id, project_id)
    console.print(
        f"[green]✓[/green] Nodo [bold]{node_id[:8]}[/bold] "
        f"assegnato al project [bold]{project_id[:8]}[/bold]"
    )
```

- [ ] **Step 3: Smoke test manuale**

```bash
# Crea un project
uv run python cli/main.py project-create \
  --user-id anna \
  --title "Studio ACE2" \
  --objective "Meccanismo entrata virale" \
  --summary "Focus sul ruolo del pH nel legame ACE2" \
  --full-context "Esperimento fallito a pH 6.8 — dati da riverificare con nuovo anticorpo"
```

Copia l'ID del project stampato (es. `abc12345`).

```bash
# Crea un nodo epistemico
uv run python cli/main.py create \
  --user-id anna \
  --type Hypothesis \
  --content "Il pH ottimale per il legame è tra 7.0 e 7.4" \
  --confidence 0.7 \
  --trigger "Osservazione esperimento #3"
```

Copia l'ID del nodo stampato.

```bash
# Assegna il nodo al project
uv run python cli/main.py project-assign \
  --node-id <ID_NODO> \
  --project-id <ID_PROJECT>
```

Expected: `✓ Nodo <id[:8]> assegnato al project <id[:8]>`

- [ ] **Step 4: Commit**

```bash
git add cli/main.py
git commit -m "feat: CLI project-create, project-assign"
```

---

## Task 9: CLI — `wiki-add`, `doc-add`

**Files:**
- Modify: `cli/main.py`

- [ ] **Step 1: Aggiungere i due comandi in coda a `cli/main.py`** (prima di `if __name__ == "__main__":`)

```python
@app.command(name="wiki-add")
def wiki_add(
    user_id: str = typer.Option(..., help="ID utente"),
    project_id: str = typer.Option(..., help="ID del Project a cui appartiene"),
    title: str = typer.Option(..., help="Titolo della pagina (stabile tra versioni)"),
    content: str = typer.Option(..., help="Contenuto della pagina"),
    summary: str = typer.Option(..., help="Cosa descrive questa versione?"),
    node_ids: str | None = typer.Option(
        None, help="Nodi da collegare, comma-separated — crea archi documenta"
    ),
) -> None:
    """Crea una nuova WikiPage (v1). Con --node-ids crea anche gli archi documenta."""
    ctx = _get_context()
    entity = ctx.wiki.create_wiki_page(user_id, project_id, title, content, summary)
    if node_ids:
        ids = [n.strip() for n in node_ids.split(",") if n.strip()]
        ctx.wiki.link_to_nodes(entity.id, ids)
        console.print(
            f"[green]✓[/green] WikiPage creata: [bold]{entity.id}[/bold] "
            f"— {len(ids)} nod{'o' if len(ids) == 1 else 'i'} collegat{'o' if len(ids) == 1 else 'i'}"
        )
    else:
        console.print(f"[green]✓[/green] WikiPage creata: [bold]{entity.id}[/bold] (v1)")
    console.print(f"  Titolo: {entity.title}")


@app.command(name="doc-add")
def doc_add(
    user_id: str = typer.Option(..., help="ID utente"),
    title: str = typer.Option(..., help="Titolo del documento"),
    doi: str | None = typer.Option(None, help="DOI (es. 10.1000/xyz123)"),
    url: str | None = typer.Option(None, help="URL del documento"),
    authors: str | None = typer.Option(None, help="Autori comma-separated (es. 'Rossi M, Bianchi A')"),
    pub_date: str | None = typer.Option(None, help="Data pubblicazione YYYY-MM-DD"),
) -> None:
    """Aggiunge un documento al DocumentIndex."""
    ctx = _get_context()
    doc = ctx.documents.add_document(
        user_id, title, doi=doi, url=url, authors=authors, pub_date=pub_date
    )
    console.print(f"[green]✓[/green] Documento aggiunto: [bold]{doc.id}[/bold]")
    console.print(f"  Titolo: {doc.title}")
    if doc.doi:
        console.print(f"  DOI: {doc.doi}")
    if doc.authors:
        console.print(f"  Autori: {doc.authors}")
```

- [ ] **Step 2: Smoke test manuale**

```bash
# Crea una WikiPage (con i nodi collegati — usa gli ID dell'esercizio del Task 8)
uv run python cli/main.py wiki-add \
  --user-id anna \
  --project-id <ID_PROJECT> \
  --title "Stato dell'arte sul ruolo del pH" \
  --content "Il pH influenza il legame ACE2 in modo critico..." \
  --summary "Prima stesura"
```

Expected: `✓ WikiPage creata: <id> (v1)`

```bash
# Aggiungi un documento senza metadati
uv run python cli/main.py doc-add \
  --user-id anna \
  --title "Review: pH and viral entry"
```

Expected: `✓ Documento aggiunto: <id>`

```bash
# Aggiungi un documento con tutti i metadati
uv run python cli/main.py doc-add \
  --user-id anna \
  --title "ACE2 binding mechanism" \
  --doi "10.1016/j.cell.2024.01.001" \
  --authors "Rossi M, Bianchi A" \
  --pub-date "2024-01-15"
```

Expected: `✓ Documento aggiunto: <id>` con DOI e autori stampati.

- [ ] **Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat: CLI wiki-add (con --node-ids opzionale), doc-add"
```

---

## Task 10: Coverage check + aggiornamento `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Eseguire tutti i test con coverage**

```bash
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing -v
```

Expected: copertura totale >80%. Se sotto, identificare i gap nel report e aggiungere test mirati prima di procedere.

- [ ] **Step 2: Verificare zero regressioni sulla Fase 1**

```bash
uv run pytest tests/test_graph/ -v
```

Expected: tutti `PASSED` — `GraphStore`, `models`, `schema` della Fase 1 invariati.

- [ ] **Step 3: Aggiornare la roadmap in `CLAUDE.md`**

Sostituisci la sezione `### 🔨 Fase 1b — Context Layer (IN CORSO)` con:

```markdown
### ✅ Fase 1b — Context Layer (COMPLETATA)
- [x] Nodo `Project` con `title`, `objective`, `summary`, `full_context`
- [x] Nodo `WikiPage` versionato (WikiEntity + WikiState — stesso pattern di NodeState)
- [x] Nodo `DocumentIndex` con metadati (DOI, URL, autori, data)
- [x] Arco `appartiene_a` — NodeEntity → Project (via ContextStore.attach_node)
- [x] Arco `referenzia` — NodeEntity → DocumentIndex (via DocumentStore.reference_document)
- [x] Arco `documenta` — WikiEntity → NodeEntity (via WikiStore.link_to_nodes)
- [x] CLI: `project-create`, `project-assign`, `wiki-add`, `doc-add`
- [x] `agent_context=False` default — full_context mai esposto per default
- [x] Architectural invariant test — guardrail su full_context in CI
- [x] Test copertura >80%
```

Aggiorna anche la riga finale del file:

```markdown
*Ultima modifica: Maggio 2026 — RFC v0.2 — Fase 1b completa*
```

- [ ] **Step 4: Commit finale**

```bash
git add CLAUDE.md
git commit -m "chore: Fase 1b completa — Context Layer, CLI, test coverage >80%"
```
