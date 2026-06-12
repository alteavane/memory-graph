# MemoryGraph — CLAUDE.md

> This file is the permanent context for the project.
> Read it in full before taking any action.

---

## What MemoryGraph is

MemoryGraph is a personal knowledge system built on a native graph,
where every unit of thought lives as a node with a complete temporal history.
It is not a note-taking tool. It is not a better RAG. It is not a wiki.
It is an infrastructure for the thinking process — captured automatically,
shareable by consent, immutable over time.

**Founding principle: no dark spots.**
Every change of belief, every failure, every turning point is data.
Nothing is ever deleted — only invalidated with a timestamp.

---

## The system's 4 layers

```
Project                    ← container of the research
├── Wiki                   ← narrative documentation, evolves with versions
├── Document Index         ← papers, sources, datasets, referenced protocols
└── MemoryGraph            ← the thinking process with temporal history
```

**Project** — entry point. Title, objective, description of the research.
All nodes belong to a Project through the `belongs_to` edge.
It has two levels of visibility: `summary` (public) and `full_context` (agent only).

**Wiki** — the evolving narrative. It is not rewritten — it is versioned.
It documents the state of the art, how understanding has evolved, the decisions made.
Specific pages can be included in the SubgraphToken by explicit choice.

**Document Index** — the anchors to the external world.
Every paper read, dataset used, protocol followed is a `Paper` or `Experiment` node
with metadata (DOI, URL, date, authors). The graph nodes reference it explicitly.

**MemoryGraph** — the thinking process.
Hypotheses, observations, dead ends, conclusions — with evolving confidence and triggers.
It is the layer that does not exist in any other system.

---

## Visibility principle — CRITICAL

This is the most important architectural principle of the system.
**Never violate it, in any layer.**

```
┌─────────────────────────────────────────────────────────────┐
│  AGENT (extension of the owner)                             │
│  Sees everything: full Project, Wiki, DocumentIndex,        │
│  MemoryGraph, history, triggers, dead ends.                 │
│  Uses the full context to do intelligent matching.          │
├─────────────────────────────────────────────────────────────┤
│  HUMAN COLLABORATOR (recipient of the subgraph)             │
│  Sees only: Project.summary + nodes explicitly              │
│  selected in the SubgraphToken.                             │
│  Never sees: full_context, Wikis not included,              │
│  unreferenced DocumentIndex, other graph nodes.             │
└─────────────────────────────────────────────────────────────┘
```

**Practical rule:**
- `Project.summary` → always travels with the SubgraphToken → visible to Bruno
- `Project.full_context` → never in the SubgraphToken → visible only to Anna's agent
- `WikiPage` → included only if Anna explicitly selects it → not automatic
- `DocumentIndex` → included only if referenced by the shared nodes → not automatic

---

## Development philosophy

- **Simplicity first.** If something can be simple, it must be simple.
- **No over-engineering.** Do not anticipate future phases.
- **The graph is the primary data.** Not markdown, not flat files, not scattered JSON.
- **Immutability of history.** Never `DELETE`. Only `invalidated_at = now()`.
- **Consent is architectural.** Not a layer added later — it is in the core from day 1.
- **The minimal context travels with the nodes.** Only the summary, never the full context.
- **The agent knows everything. The human sees only what is shown to them.**
- **LLM-agnostic.** No hard dependency on a specific provider.

---

## Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | type hints everywhere |
| Graph DB | Kuzu (embedded) | zero infra, local file |
| LLM | agnostic | via structured prompt |
| Embedding | agnostic | any provider or local |
| API | FastAPI | only from Phase 3 |
| Test | pytest | minimum coverage 80% |
| Package manager | uv | fast, modern |

---

## Project structure

```
memorygraph/
├── CLAUDE.md                  ← you are here
├── README.md                  ← English
├── README.it.md               ← Italian
├── pyproject.toml
├── uv.lock
├── .env.example
│
├── src/
│   └── memorygraph/
│       ├── __init__.py
│       ├── config.py          ← global configuration
│       │
│       ├── graph/             ← PHASE 1: Graph Store ✅
│       │   ├── __init__.py
│       │   ├── schema.py      ← Kuzu node/edge definitions
│       │   ├── store.py       ← GraphStore class (100% coverage)
│       │   ├── models.py      ← Python dataclasses
│       │   └── migrations/    ← schema versioning
│       │
│       ├── context/           ← PHASE 1b: Project + Wiki + Document Index
│       │   ├── __init__.py
│       │   ├── project.py     ← Project with separate summary/full_context
│       │   ├── wiki.py        ← versioned WikiPage
│       │   └── documents.py   ← DocumentIndex with metadata
│       │
│       ├── agent/             ← PHASE 2: Memory Agent
│       │   ├── __init__.py
│       │   ├── extractor.py   ← LLM → entities → nodes
│       │   ├── quality.py     ← quality gate before writing
│       │   ├── confidence.py  ← confidence estimation from language
│       │   └── detector.py    ← contradiction detection
│       │
│       ├── auth/              ← PHASE 3: Consent Layer
│       │   ├── __init__.py
│       │   ├── token.py       ← SubgraphToken — generation and verification
│       │   ├── consent.py     ← UserNetworkConsent
│       │   └── crypto.py      ← signing and integrity
│       │
│       └── engine/            ← PHASE 4: Fork/Merge Engine
│           ├── __init__.py
│           ├── fork.py        ← fork import into the isolated graph
│           ├── merge.py       ← MergeProposal + semantic diff
│           └── patterns.py    ← TrajectoryPattern + matching
│
├── tests/
│   ├── test_graph/
│   ├── test_context/
│   ├── test_agent/
│   ├── test_auth/
│   └── test_engine/
│
├── cli/
│   └── main.py                ← full CLI
│
└── data/
    └── .gitkeep               ← the local Kuzu file lives here (do not commit)
```

---

## Graph schema — full reference

### Node types

```python
NodeType = Enum(
    # MemoryGraph layer — thinking process
    "Observation",      # observed empirical fact
    "Hypothesis",       # hypothesis to be verified
    "Conclusion",       # validated, high certainty
    "DeadEnd",          # falsified — valuable data, never hide it
    "OpenQuestion",     # question still unanswered

    # Document Index layer — external sources
    "Paper",            # scientific article (DOI, authors, date)
    "Experiment",       # experiment with method and result
    "MethodDecision",   # methodological choice with explicit reasoning

    # Context layer — container and narrative
    "Project",          # research container (see schema below)
    "WikiPage",         # versioned narrative document
    "DocumentIndex",    # index of sources with metadata
)
```

### Project schema — differentiated visibility

```python
Project:
  id                UUID
  user_id           UUID
  title             TEXT        # public — in the summary
  objective         TEXT        # public — in the summary
  summary           TEXT        # public — travels with SubgraphToken
                                # minimal context for the collaborator
  full_context      TEXT        # PRIVATE — visible only to the agent
                                # never included in the SubgraphToken
  created_at        TIMESTAMP
  updated_at        TIMESTAMP
```

### SubgraphToken schema — explicit visibility

```python
SubgraphToken:
  id                UUID
  issuer_id         UUID
  recipient_id      UUID
  node_ids          JSONB       # [{id, include_history: bool}]
  project_summary   TEXT        # copy of the summary at the moment of sharing
                                # NOT a live reference — immutable snapshot
  wiki_page_ids     UUID[]      # included Wiki pages — Anna's explicit choice
                                # default: empty list
  forkable          BOOL
  expires_at        TIMESTAMP
  signature         TEXT        # integrity hash
```

### Edge types

```python
EdgeType = Enum(
    # Epistemic relations
    "supports",         # increases a node's credibility
    "contradicts",      # explicit tension between two nodes
    "derives_from",     # traceability of the origin
    "falsifies",        # closes a hypothesis (DeadEnd)
    "opens_question",   # generates an OpenQuestion
    "resolves",         # closes an OpenQuestion

    # Contextual relations
    "belongs_to",       # node → Project
    "documents",        # WikiPage → cluster of nodes
    "references",       # node → Paper or DocumentIndex
)
```

### Trajectory pattern (computed by the agent)

```python
PatternType = Enum(
    "consolidating",    # steadily rising confidence
    "collapsing",       # falling confidence — cross-user trigger match
    "recovered",        # was collapsing, then rose again — valuable data for others
    "oscillating",      # unstable, unresolved open question
    "terminal_deadend", # definitive DeadEnd
)
```

### Critical fields — never forget

- `NodeState.confidence` → Float 0.0–1.0. It is THE central signal of the system.
- `NodeState.trigger` → Free text. "Why did this change?" It is the memory of the process.
- `NodeState.created_at` → This IS the evolution timestamp. It is not metadata — it is data.
- `Edge.invalidated_at` → null if valid. Never DELETE. Only invalidation with a timestamp.
- `NodeEntity.is_deleted` → soft delete. The history always remains.
- `Project.summary` → the only part of the Project that travels with the SubgraphToken.
- `Project.full_context` → NEVER in the SubgraphToken. Only the agent sees it.
- `SubgraphToken.project_summary` → snapshot at the moment of sharing, not a live reference.
- `SubgraphToken.wiki_page_ids` → default empty. Wiki included only by explicit choice.

---

## Roadmap — current status

### ✅ Phase 0 — Vision and RFC
- [x] Vision and RFC (README.md + README.it.md)
- [x] Complete schema of all layers
- [x] 4 narrative use cases (UC-01 → UC-04)
- [x] CLAUDE.md

### ✅ Phase 1 — Graph Store (COMPLETED)
- [x] Python project setup with `uv`
- [x] Kuzu installation and configuration
- [x] Kuzu schema definition (`schema.py`)
- [x] Python dataclasses (`models.py`)
- [x] `GraphStore` class with basic operations:
  - [x] `create_node(user_id, type, content, confidence, trigger)`
  - [x] `update_node(node_id, content, confidence, trigger)` → creates a new NodeState
  - [x] `get_node_history(node_id)` → all NodeStates in chronological order
  - [x] `get_graph(user_id)` → current snapshot of the user's graph
  - [x] `create_edge(from_id, to_id, type, confidence)`
  - [x] `invalidate_edge(edge_id)` → never delete
- [x] Basic CLI: `create`, `update`, `history`, `show`, `edge-create`, `edge-invalidate`, `link`
- [x] `update --content` optional — reuses the content of the last state if omitted
- [x] GraphStore unit tests (coverage >80%) — current: 98%, `store.py` 100%

### ✅ Phase 1b — Context Layer (COMPLETED)
- [x] `Project` node with `title`, `objective`, `summary`, `full_context`
- [x] Versioned `WikiPage` node (WikiEntity + WikiState — same pattern as NodeState)
- [x] `DocumentIndex` node with metadata (DOI, URL, authors, date)
- [x] Edge `belongs_to` — NodeEntity → Project (via ContextStore.attach_node)
- [x] Edge `references` — NodeEntity → DocumentIndex (via DocumentStore.reference_document)
- [x] Edge `documents` — WikiEntity → NodeEntity (via WikiStore.link_to_nodes)
- [x] CLI: `project-create`, `project-assign`, `wiki-add`, `doc-add`
- [x] `agent_context=False` default — full_context never exposed by default
- [x] Architectural invariant test — guardrail on full_context in CI
- [x] Test coverage >80%

### ✅ Phase 2 — Memory Agent (COMPLETED)
- [x] LLM extractor (extractor.py) — CandidateNode, extract()
- [x] Quality gate (quality.py) — filter_candidates()
- [x] Contradiction detector (detector.py) — detect() + cosine similarity
- [x] MemoryAgent (agent.py) — extract(), propose(), run() loop y/n/s/a
- [x] CLI: agent-extract
- [x] Test coverage ≥ 80%

### ✅ Phase 2b — Link Agent (COMPLETED)
- [x] LinkAgent (link_agent.py) — CandidateEdge, ProposedEdge, propose(), run()
- [x] Edge quality gate: confidence, self-loop, node not in graph, invalid type, duplicates
- [x] Interactive Rich table: n/t/c/y/N
- [x] Integration into MemoryAgent.run() — lazy import, activated only if nodes were written
- [x] Shared GraphStore — avoids a double Kuzu connection
- [x] Test coverage ≥ 80% (link_agent.py 88%, total 94%)

### ✅ Phase 3a — Identity Layer (COMPLETED)
- [x] Ed25519 keypair generation + deterministic canonical signing (`auth/crypto.py`)
- [x] `UserIdentity` dataclass + Kuzu table
- [x] `IdentityStore.create_identity` / `get_identity` (private key hidden by default) / `get_public_key`
- [x] CLI: `identity-create`, `identity-show`

### ✅ Phase 3b — SubgraphToken + Consent (COMPLETED)
- [x] `SubgraphToken` + `UserNetworkConsent` dataclasses + Kuzu tables
- [x] `ConsentStore` (get/set, all-false defaults = max privacy, partial upsert)
- [x] `build_token` — materializes selected node states, snapshots `project_summary`,
      applies consent (DeadEnd excluded + triggers stripped when not consented), Ed25519-signs
- [x] **Decision A**: token embeds materialized content in `node_ids` JSON → offline cross-instance verification
- [x] `serialize` / `deserialize` (deterministic JSON) + `verify_token` (expiry + signature, never raises)
- [x] `TokenStore` persist/retrieve
- [x] §8 invariant guardrails: `full_context`/`private_key` never serialized, frozen summary snapshot,
      `wiki_page_ids` empty by default, consent enforced on DeadEnds/triggers
- [x] CLI: `token-issue`, `token-verify`, `consent-show`, `consent-set` (naive-UTC clock throughout)
- [x] Test coverage: auth module 98% (`token.py` 100%)

### ✅ Phase 3c — REST API (COMPLETED)
- [x] Federated deployment: one instance per user (one writer per instance) — `docs/superpowers/specs/2026-06-12-phase-3c-rest-api-design.md`
- [x] `WriterManager` (`api/writer.py`) — in-process, lazy `user_id→GraphStore`, per-user lock; sole Kuzu constructor; every DB touch (reads too) goes through `submit()`
- [x] Pydantic schemas (`api/schemas.py`) + app factory `create_app(owner_id, db_path)` (`api/app.py`, auto-provisions owner identity)
- [x] 5 endpoints: `GET /identity/{id}`, `GET|PUT /consent`, `POST /tokens`, `POST /inbox/tokens`, `GET /shared/{id}`
- [x] `IdentityStore.register_peer` — public-key-only upsert so `/shared` re-verifies offline
- [x] Read-only `/shared`: returns only token-embedded content; 403 tampered/expired, 404 unknown
- [x] §8 guardrails over HTTP + two-instance integration test (in-process, two FastAPI apps + TestClient)
- [x] `GraphStore.close()` / `WriterManager.close()` + GC sweep — bound Kuzu mmap reservations across tests
- [x] README Phase 3/4 boundary realigned (fork import → Phase 4)
- [x] Test coverage: `api/` 100%, auth module 100% (except schema idempotency branch)

### ⏳ Phase 4 — Fork/Merge Engine
- TrajectoryPattern, embedding, cross-user matching, MergeProposal

---

## Development rules

### What to always do
- Type hints on every function and method
- Docstring on every public class
- One test per public method
- Atomic commits with a descriptive message
- Update this CLAUDE.md whenever the roadmap status changes

### What to never do
- `DELETE` on NodeEntity, NodeState, or Edge → use `is_deleted` or `invalidated_at`
- Access a user's graph without verifying `user_id` → multi-tenant isolation
- Write to the graph without going through the quality gate (from Phase 2 onward)
- Hard-code the LLM model name → always from config
- Commit the database `.kuzu` file → it is in `.gitignore`
- Include `Project.full_context` in the SubgraphToken → it is PRIVATE, agent only
- Include a WikiPage in the SubgraphToken without explicit selection → default is empty list
- Use a live reference to the Project in the token → always a snapshot at the moment of sharing
- **Open a direct Kuzu connection from a secondary component** → embedded Kuzu is
  single-writer per process. Every component (LinkAgent, SubgraphToken, fork engine, merge
  engine) receives a `GraphStore` already initialized from the outside — never an internal
  `GraphStore(db_path)`. The connection lives in the main process and is passed explicitly.

### Naming conventions
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`
- UUID: always `str`, not native UUID objects (Kuzu compatibility)

---

## Useful commands

```bash
# Initial setup
uv sync

# Start the CLI
uv run python cli/main.py

# Tests
uv run pytest tests/ -v

# Tests with coverage
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing

# Delete the local database (development only)
rm -rf data/memorygraph.kuzu
```

---

## Decision context — why we chose X

**Kuzu instead of Neo4j**
For the prototype we want zero infrastructure. Kuzu is embedded like SQLite —
it runs in-process, saves to a local file, no server to manage.
When the system scales or requires multi-instance, we migrate to Neo4j or FalkorDB.

**Project.summary vs Project.full_context**
The human collaborator should not see all of Anna's research — only the minimal
context needed to understand the nodes they receive. The agent, on the other hand, knows
everything and uses the full context to do intelligent matching without exposing anything.
This separation is architectural — not a filter added later.

**project_summary as a snapshot instead of a live reference**
The SubgraphToken is immutable over time. Bruno must receive the context
exactly as it was at the moment of sharing, not as it evolves afterward.
If Anna updates her Project, Bruno's token does not change.

**WikiPage optional in the SubgraphToken**
The Wiki contains the complete narrative of Anna's research — often too much
for an external collaborator. Anna explicitly chooses which pages to include.
The default is an empty list: no Wiki shared unless deliberately chosen.

**Fork as a copy instead of a live link**
The recipient must be able to experiment freely without compromising the issuer's
graph. The copy also preserves the historical moment. It is exactly the Git model.

**`confidence` as a Float instead of an Enum**
Certainty is continuous, not categorical. An Enum (high/medium/low) loses
the granularity that makes the system useful — the difference between 0.71 and 0.69
after an experiment is a real signal.

**`trigger` as free text instead of structured**
The "why" of a change of belief is often narrative and contextual.
A structured field would impoverish it. Free text lets both
the user and the agent express themselves naturally.

**WikiPage with the same model as NodeState**
The Wiki is not a static document — it evolves like the graph.
Using the same versioning model as NodeState keeps
architectural coherence and enables the same "time travel" over the narrative.

---

## Reference use cases (summary)

**UC-01 — Anna and Bruno, virologists**
Anna has a `collapsing` pattern on pH (0.60 → 0.85 → 0.35).
Anna's agent uses the Project's `full_context` to understand the precise domain
and finds in Bruno's graph a `consolidated` pattern that is semantically related.
Proposal → Anna approves → SubgraphToken issued with:
  - `project_summary`: "Study of viral entry mechanism — focus on ACE2"
  - `node_ids`: only the nodes relevant to pH
  - `wiki_page_ids`: empty (Anna does not include the Wiki)
Bruno receives the minimal context — he sees nothing of Anna's complete research.

**UC-02 — The solitary researcher**
Pre-network utility. Time travel through one's own thinking.
The Wiki reconstructs the narrative, the graph reconstructs the process.
`full_context` available only to the personal agent.

**UC-03 — The lab team**
5 researchers, separate graphs, autonomy preserved.
Each Project has a `summary` shared within the team and a private `full_context`.
The system flags overlaps without exposing content.

**UC-04 — The paper moment**
Wiki → introduction draft. DocumentIndex → structured bibliography.
DeadEnd → supplementary material. The dark matter becomes published data.
The agent uses `full_context` to reconstruct the complete narrative.

---

*Last modified: June 2026 — RFC v0.2 — Phase 3c complete*
*Update this file at every change of roadmap status.*
