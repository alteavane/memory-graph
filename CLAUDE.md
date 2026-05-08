# MemoryGraph — CLAUDE.md

> Questo file è il contesto permanente del progetto.
> Leggilo interamente prima di qualsiasi azione.

---

## Cos'è MemoryGraph

MemoryGraph è un sistema di conoscenza personale basato su grafo nativo,
dove ogni unità di pensiero vive come nodo con una storia temporale completa.
Non è un tool di note. Non è un RAG migliore. Non è un wiki.
È un'infrastruttura per il processo del pensiero — catturato automaticamente,
condivisibile consensualmente, immutabile nel tempo.

**Principio fondante: nessun punto di buio.**
Ogni cambiamento di credenza, ogni fallimento, ogni svolta è un dato.
Niente viene mai cancellato — solo invalidato con timestamp.

---

## I 4 layer del sistema

```
Project                    ← contenitore della ricerca
├── Wiki                   ← documentazione narrativa, evolve con versioni
├── Document Index         ← paper, fonti, dataset, protocolli referenziati
└── MemoryGraph            ← il processo del pensiero con storia temporale
```

**Project** — punto di ingresso. Titolo, obiettivo, descrizione della ricerca.
Tutti i nodi appartengono a un Project tramite arco `appartiene_a`.
Ha due livelli di visibilità: `summary` (pubblico) e `full_context` (solo agente).

**Wiki** — la narrazione evolutiva. Non si riscrive — si versiona.
Documenta lo stato dell'arte, come è evoluta la comprensione, le decisioni prese.
Pagine specifiche possono essere incluse nel SubgraphToken su scelta esplicita.

**Document Index** — le ancore al mondo esterno.
Ogni paper letto, dataset usato, protocollo seguito è un nodo `Paper` o `Experiment`
con metadati (DOI, URL, data, autori). I nodi del grafo lo referenziano esplicitamente.

**MemoryGraph** — il processo del pensiero.
Ipotesi, osservazioni, dead end, conclusioni — con confidence evolutiva e trigger.
È il layer che non esiste in nessun altro sistema.

---

## Principio di visibilità — CRITICO

Questo è il principio architetturale più importante del sistema.
**Non violarlo mai, in nessun layer.**

```
┌─────────────────────────────────────────────────────────────┐
│  AGENTE (estensione del proprietario)                       │
│  Vede tutto: Project completo, Wiki, DocumentIndex,         │
│  MemoryGraph, storia, trigger, dead end.                    │
│  Usa il contesto completo per fare matching intelligente.   │
├─────────────────────────────────────────────────────────────┤
│  COLLABORATORE UMANO (destinatario del subgrafo)            │
│  Vede solo: Project.summary + nodi esplicitamente           │
│  selezionati nel SubgraphToken.                             │
│  Non vede mai: full_context, Wiki non incluse,              │
│  DocumentIndex non referenziato, altri nodi del grafo.      │
└─────────────────────────────────────────────────────────────┘
```

**Regola pratica:**
- `Project.summary` → viaggia sempre con il SubgraphToken → visibile a Bruno
- `Project.full_context` → mai nel SubgraphToken → visibile solo all'agente di Anna
- `WikiPage` → inclusa solo se Anna la seleziona esplicitamente → non automatica
- `DocumentIndex` → incluso solo se referenziato dai nodi condivisi → non automatico

---

## Filosofia di sviluppo

- **Semplicità prima di tutto.** Se una cosa può essere semplice, deve essere semplice.
- **Niente over-engineering.** Non anticipare fasi future.
- **Il grafo è il dato primario.** Non markdown, non file flat, non JSON sparsi.
- **Immutabilità della storia.** Mai `DELETE`. Solo `invalidated_at = now()`.
- **Il consenso è architetturale.** Non un layer aggiunto dopo — è nel core dal giorno 1.
- **Il contesto minimo viaggia con i nodi.** Solo il summary, mai il full context.
- **L'agente conosce tutto. L'umano vede solo quello che gli viene mostrato.**
- **LLM-agnostico.** Nessuna dipendenza hard da un provider specifico.

---

## Stack

| Layer | Tecnologia | Note |
|---|---|---|
| Linguaggio | Python 3.11+ | type hints ovunque |
| Graph DB | Kuzu (embedded) | zero infra, file locale |
| LLM | agnostico | via prompt strutturato |
| Embedding | agnostico | qualsiasi provider o locale |
| API | FastAPI | solo dalla Fase 3 |
| Test | pytest | copertura minima 80% |
| Package manager | uv | veloce, moderno |

---

## Struttura del progetto

```
memorygraph/
├── CLAUDE.md                  ← sei qui
├── README.md                  ← inglese
├── README.it.md               ← italiano
├── pyproject.toml
├── uv.lock
├── .env.example
│
├── src/
│   └── memorygraph/
│       ├── __init__.py
│       ├── config.py          ← configurazione globale
│       │
│       ├── graph/             ← FASE 1: Graph Store ✅
│       │   ├── __init__.py
│       │   ├── schema.py      ← definizione nodi/archi Kuzu
│       │   ├── store.py       ← GraphStore class (100% coverage)
│       │   ├── models.py      ← dataclass Python
│       │   └── migrations/    ← versioning schema
│       │
│       ├── context/           ← FASE 1b: Project + Wiki + Document Index
│       │   ├── __init__.py
│       │   ├── project.py     ← Project con summary/full_context separati
│       │   ├── wiki.py        ← WikiPage versionata
│       │   └── documents.py   ← DocumentIndex con metadati
│       │
│       ├── agent/             ← FASE 2: Memory Agent
│       │   ├── __init__.py
│       │   ├── extractor.py   ← LLM → entità → nodi
│       │   ├── quality.py     ← quality gate prima della scrittura
│       │   ├── confidence.py  ← stima confidence dal linguaggio
│       │   └── detector.py    ← rilevamento contraddizioni
│       │
│       ├── auth/              ← FASE 3: Consent Layer
│       │   ├── __init__.py
│       │   ├── token.py       ← SubgraphToken — generazione e verifica
│       │   ├── consent.py     ← UserNetworkConsent
│       │   └── crypto.py      ← firma e integrità
│       │
│       └── engine/            ← FASE 4: Fork/Merge Engine
│           ├── __init__.py
│           ├── fork.py        ← fork import nel grafo isolato
│           ├── merge.py       ← MergeProposal + diff semantico
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
│   └── main.py                ← CLI completa
│
└── data/
    └── .gitkeep               ← qui vive il file Kuzu locale (non committare)
```

---

## Schema del grafo — riferimento completo

### Tipi di nodo

```python
NodeType = Enum(
    # Layer MemoryGraph — processo del pensiero
    "Observation",      # fatto empirico osservato
    "Hypothesis",       # ipotesi da verificare
    "Conclusion",       # validata, alta certezza
    "DeadEnd",          # falsificata — dato prezioso, mai nascondere
    "OpenQuestion",     # domanda senza risposta ancora

    # Layer Document Index — fonti esterne
    "Paper",            # articolo scientifico (DOI, autori, data)
    "Experiment",       # esperimento con metodo e risultato
    "MethodDecision",   # scelta metodologica con ragionamento esplicito

    # Layer Context — contenitore e narrazione
    "Project",          # contenitore della ricerca (vedi schema sotto)
    "WikiPage",         # documento narrativo versionato
    "DocumentIndex",    # indice di fonti con metadati
)
```

### Schema Project — visibilità differenziata

```python
Project:
  id                UUID
  user_id           UUID
  title             TEXT        # pubblico — nel summary
  objective         TEXT        # pubblico — nel summary
  summary           TEXT        # pubblico — viaggia con SubgraphToken
                                # contesto minimo per il collaboratore
  full_context      TEXT        # PRIVATO — visibile solo all'agente
                                # mai incluso nel SubgraphToken
  created_at        TIMESTAMP
  updated_at        TIMESTAMP
```

### Schema SubgraphToken — visibilità esplicita

```python
SubgraphToken:
  id                UUID
  issuer_id         UUID
  recipient_id      UUID
  node_ids          JSONB       # [{id, include_history: bool}]
  project_summary   TEXT        # copia del summary al momento della condivisione
                                # NON un riferimento live — snapshot immutabile
  wiki_page_ids     UUID[]      # pagine Wiki incluse — scelta esplicita di Anna
                                # default: lista vuota
  forkable          BOOL
  expires_at        TIMESTAMP
  signature         TEXT        # hash di integrità
```

### Tipi di arco

```python
EdgeType = Enum(
    # Relazioni epistemiche
    "supporta",         # aumenta la credibilità di un nodo
    "contraddice",      # tensione esplicita tra due nodi
    "deriva_da",        # tracciabilità dell'origine
    "falsifica",        # chiude un'ipotesi (DeadEnd)
    "apre_domanda",     # genera una OpenQuestion
    "risolve",          # chiude una OpenQuestion

    # Relazioni contestuali
    "appartiene_a",     # nodo → Project
    "documenta",        # WikiPage → cluster di nodi
    "referenzia",       # nodo → Paper o DocumentIndex
)
```

### Pattern traiettoria (calcolato dall'agente)

```python
PatternType = Enum(
    "consolidating",    # confidence in crescita stabile
    "collapsing",       # confidence in caduta — trigger match cross-utente
    "recovered",        # era collapsing, poi risalita — dato prezioso per altri
    "oscillating",      # instabile, domanda aperta irrisolta
    "terminal_deadend", # DeadEnd definitivo
)
```

### Campi critici — non dimenticare mai

- `NodeState.confidence` → Float 0.0–1.0. È IL segnale centrale del sistema.
- `NodeState.trigger` → Testo libero. "Perché è cambiato questo?" È la memoria del processo.
- `NodeState.created_at` → Questo È il timestamp di evoluzione. Non è metadata — è dato.
- `Edge.invalidated_at` → null se valido. Mai DELETE. Solo invalidazione con timestamp.
- `NodeEntity.is_deleted` → soft delete. La storia rimane sempre.
- `Project.summary` → l'unica parte del Project che viaggia con il SubgraphToken.
- `Project.full_context` → MAI nel SubgraphToken. Solo l'agente lo vede.
- `SubgraphToken.project_summary` → snapshot al momento della condivisione, non riferimento live.
- `SubgraphToken.wiki_page_ids` → default vuoto. Wiki inclusa solo su scelta esplicita.

---

## Roadmap — stato attuale

### ✅ Fase 0 — Vision e RFC
- [x] Vision e RFC (README.md + README.it.md)
- [x] Schema completo di tutti i layer
- [x] 4 use case narrativi (UC-01 → UC-04)
- [x] CLAUDE.md

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
- [x] CLI base: `create`, `update`, `history`, `show`, `edge-create`, `edge-invalidate`, `link`
- [x] `update --content` opzionale — riusa il contenuto dell'ultimo stato se omesso
- [x] Test unitari GraphStore (copertura >80%) — attuale: 98%, `store.py` 100%

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

### ✅ Fase 2 — Memory Agent (COMPLETATA)
- [x] LLM extractor (extractor.py) — CandidateNode, extract()
- [x] Quality gate (quality.py) — filter_candidates()
- [x] Contradiction detector (detector.py) — detect() + cosine similarity
- [x] MemoryAgent (agent.py) — extract(), propose(), run() loop y/n/s/a
- [x] CLI: agent-extract
- [x] Test copertura ≥ 80%

### ✅ Fase 2b — Link Agent (COMPLETATA)
- [x] LinkAgent (link_agent.py) — CandidateEdge, ProposedEdge, propose(), run()
- [x] Quality gate archi: confidence, self-loop, node non in grafo, type invalido, duplicati
- [x] Tabella Rich interattiva: n/t/c/y/N
- [x] Integrazione in MemoryAgent.run() — lazy import, attivato solo se nodi scritti
- [x] GraphStore condiviso — evita doppia connessione Kuzu
- [x] Test copertura ≥ 80% (link_agent.py 88%, totale 94%)

### ⏳ Fase 3 — Auth & Consent Layer
- SubgraphToken con `project_summary` snapshot
- `wiki_page_ids` selection UI
- UserNetworkConsent, REST API

### ⏳ Fase 4 — Fork/Merge Engine
- TrajectoryPattern, embedding, cross-user matching, MergeProposal

---

## Regole di sviluppo

### Cosa fare sempre
- Type hints su ogni funzione e metodo
- Docstring su ogni classe pubblica
- Un test per ogni metodo pubblico
- Commit atomici con messaggio descrittivo
- Aggiornare questo CLAUDE.md quando lo stato della roadmap cambia

### Cosa non fare mai
- `DELETE` su NodeEntity, NodeState, o Edge → usa `is_deleted` o `invalidated_at`
- Accedere al grafo di un utente senza verificare `user_id` → isolamento multi-tenant
- Scrivere nel grafo senza passare per il quality gate (dalla Fase 2 in poi)
- Hard-codare il nome del modello LLM → sempre da config
- Committare il file `.kuzu` del database → è in `.gitignore`
- Includere `Project.full_context` nel SubgraphToken → è PRIVATO, solo per l'agente
- Includere WikiPage nel SubgraphToken senza selezione esplicita → default è lista vuota
- Usare riferimento live al Project nel token → sempre snapshot al momento della condivisione
- **Aprire una connessione Kuzu diretta da un componente secondario** → Kuzu embedded è
  single-writer per processo. Ogni componente (LinkAgent, SubgraphToken, fork engine, merge
  engine) riceve un `GraphStore` già inizializzato dall'esterno — mai `GraphStore(db_path)`
  interno. La connessione vive nel processo principale e viene passata esplicitamente.

### Convenzioni naming
- Classi: `PascalCase`
- Funzioni/variabili: `snake_case`
- Costanti: `UPPER_SNAKE_CASE`
- File: `snake_case.py`
- UUID: sempre `str`, non oggetti UUID nativi (compatibilità Kuzu)

---

## Comandi utili

```bash
# Setup iniziale
uv sync

# Avviare la CLI
uv run python cli/main.py

# Test
uv run pytest tests/ -v

# Test con coverage
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing

# Cancellare il database locale (solo sviluppo)
rm -rf data/memorygraph.kuzu
```

---

## Contesto decisionale — perché abbiamo scelto X

**Kuzu invece di Neo4j**
Per il prototipo vogliamo zero infrastruttura. Kuzu è embedded come SQLite —
gira in processo, salva su file locale, nessun server da gestire.
Quando il sistema scala o richiede multi-istanza, si migra a Neo4j o FalkorDB.

**Project.summary vs Project.full_context**
Il collaboratore umano non deve vedere tutta la ricerca di Anna — solo il contesto
minimo per capire i nodi che riceve. L'agente invece conosce tutto e usa il contesto
completo per fare matching intelligente senza esporre nulla.
Questa separazione è architetturale — non un filtro aggiunto dopo.

**project_summary come snapshot invece di riferimento live**
Il SubgraphToken è immutabile nel tempo. Bruno deve ricevere il contesto
esattamente come era al momento della condivisione, non come evolve dopo.
Se Anna aggiorna il suo Project, il token di Bruno non cambia.

**WikiPage opzionale nel SubgraphToken**
La Wiki contiene la narrazione completa della ricerca di Anna — spesso troppo
per un collaboratore esterno. Anna sceglie esplicitamente quali pagine includere.
Il default è lista vuota: nessuna Wiki condivisa a meno di scelta deliberata.

**Fork come copia invece di link live**
Il destinatario deve poter sperimentare liberamente senza compromettere il grafo
dell'emittente. La copia preserva anche il momento storico. È esattamente il modello Git.

**`confidence` come Float invece di Enum**
La certezza è continua, non categorica. Un Enum (alto/medio/basso) perde
la granularità che rende il sistema utile — la differenza tra 0.71 e 0.69
dopo un esperimento è un segnale reale.

**`trigger` come testo libero invece di strutturato**
Il "perché" di un cambiamento di credenza è spesso narrativo e contestuale.
Un campo strutturato lo impoverirebbe. Il testo libero permette sia
all'utente che all'agente di esprimersi naturalmente.

**WikiPage con stesso modello di NodeState**
La Wiki non è un documento statico — evolve come il grafo.
Usare lo stesso modello di versionamento di NodeState mantiene
la coerenza architetturale e abilita lo stesso "time travel" sulla narrativa.

---

## Use case di riferimento (sintesi)

**UC-01 — Anna e Bruno, virologi**
Anna ha pattern `collapsing` sul pH (0.60 → 0.85 → 0.35).
L'agente di Anna usa il `full_context` del Project per capire il dominio preciso
e trova nel grafo di Bruno un pattern `consolidated` semanticamente correlato.
Proposta → Anna approva → SubgraphToken emesso con:
  - `project_summary`: "Studio meccanismo entrata virale — focus ACE2"
  - `node_ids`: solo i nodi rilevanti sul pH
  - `wiki_page_ids`: vuoto (Anna non include la Wiki)
Bruno riceve il contesto minimo — non vede nulla della ricerca completa di Anna.

**UC-02 — Il ricercatore solitario**
Utilità pre-rete. Time travel nel proprio pensiero.
Il Wiki ricostruisce la narrazione, il grafo ricostruisce il processo.
`full_context` disponibile solo all'agente personale.

**UC-03 — Il team di lab**
5 ricercatori, grafi separati, autonomia preservata.
Ogni Project ha un `summary` condiviso nel team e un `full_context` privato.
Il sistema segnala sovrapposizioni senza esporre contenuto.

**UC-04 — Il momento del paper**
Wiki → bozza introduzione. DocumentIndex → bibliografia strutturata.
DeadEnd → supplementary material. La materia oscura diventa dato pubblicato.
L'agente usa `full_context` per ricostruire la narrativa completa.

---

*Ultima modifica: Maggio 2026 — RFC v0.2 — Fase 2b completa*
*Aggiorna questo file a ogni cambio di stato della roadmap.*
