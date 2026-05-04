# MemoryGraph — CLAUDE.md

> Questo file è il contesto permanente del progetto.
> Leggilo interamente prima di qualsiasi azione.

---

## Chi sei

Sei il più esperto product Archittet Developer di tutto il mondo
---

## Cos'è MemoryGraph

MemoryGraph è un sistema di conoscenza personale basato su grafo nativo,
dove ogni unità di pensiero vive come nodo con una storia temporale completa.
Non è un tool di note. Non è un RAG migliore.
È un'infrastruttura per il processo del pensiero — catturato automaticamente,
condivisibile consensualmente, immutabile nel tempo.

**Principio fondante: nessun punto di buio.**
Ogni cambiamento di credenza, ogni fallimento, ogni svolta è un dato.
Niente viene mai cancellato — solo invalidato con timestamp.

---

## Filosofia di sviluppo

- **Semplicità prima di tutto.** Se una cosa può essere semplice, deve essere semplice.
- **Niente over-engineering.** Siamo in Fase 1. Non anticipare la Fase 4.
- **Il grafo è il dato primario.** Non markdown, non file flat, non JSON sparsi.
- **Immutabilità della storia.** Mai `DELETE`. Solo `invalidated_at = now()`.
- **Il consenso è architetturale.** Non un layer aggiunto dopo — è nel core dal giorno 1.
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
│       ├── graph/             ← FASE 1: Graph Store
│       │   ├── __init__.py
│       │   ├── schema.py      ← definizione nodi/archi Kuzu
│       │   ├── store.py       ← GraphStore class — CRUD + query
│       │   ├── models.py      ← dataclass Python (NodeEntity, NodeState, Edge...)
│       │   └── migrations/    ← versioning schema
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
│   ├── test_agent/
│   ├── test_auth/
│   └── test_engine/
│
├── cli/
│   └── main.py                ← CLI base (Fase 1)
│
└── data/
    └── .gitkeep               ← qui vive il file Kuzu locale (non committare)
```

---

## Schema del grafo — riferimento completo

### Entità principali

```python
# Tipi di nodo
NodeType = Enum(
    "Observation",      # fatto empirico osservato
    "Hypothesis",       # ipotesi da verificare
    "Conclusion",       # validata, alta certezza
    "DeadEnd",          # falsificata — dato prezioso
    "OpenQuestion",     # domanda senza risposta ancora
    "Paper",            # fonte esterna
    "Experiment",       # esperimento con metodo/risultato
    "MethodDecision",   # scelta metodologica con ragionamento
)

# Tipi di arco
EdgeType = Enum(
    "supporta",         # aumenta la credibilità
    "contraddice",      # tensione esplicita
    "deriva_da",        # tracciabilità dell'origine
    "falsifica",        # chiude un'ipotesi
    "apre_domanda",     # genera una domanda aperta
    "risolve",          # chiude una domanda aperta
)

# Pattern traiettoria (calcolato, non inserito manualmente)
PatternType = Enum(
    "consolidating",    # confidence in crescita stabile
    "collapsing",       # confidence in caduta
    "recovered",        # era collapsing, poi risalita
    "oscillating",      # instabile, non risolta
    "terminal_deadend", # DeadEnd definitivo
)
```

### Campi critici da non dimenticare mai

- `NodeState.confidence` → Float 0.0–1.0. È IL segnale centrale del sistema.
- `NodeState.trigger` → Testo libero. "Perché è cambiato questo?" È la memoria del processo.
- `NodeState.created_at` → Questo È il timestamp di evoluzione. Non è metadata — è dato.
- `Edge.invalidated_at` → null se valido. Mai DELETE. Solo invalidazione con timestamp.
- `NodeEntity.is_deleted` → soft delete. La storia rimane sempre.
- `SubgraphToken.signature` → hash di integrità. Sempre verificato prima dell'import.

---

## Roadmap — stato attuale

### ✅ Completato
- Vision e RFC (README.md + README.it.md)
- Schema completo di tutti i layer
- 4 use case narrativi (UC-01 → UC-04)
- CLAUDE.md (questo file)

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

### ⏳ Fase 2 — Memory Agent
- LLM extractor, quality gate, confidence estimator, contradiction detector

### ⏳ Fase 3 — Auth & Consent Layer
- SubgraphToken, firma, UserNetworkConsent, REST API

### ⏳ Fase 4 — Fork/Merge Engine
- TrajectoryPattern, embedding, cross-user matching, MergeProposal

---

## Regole di sviluppo

### Cosa fare sempre
- Type hints su ogni funzione e metodo
- Docstring su ogni classe pubblica
- Un test per ogni metodo pubblico di GraphStore
- Commit atomici con messaggio descrittivo
- Aggiornare questo CLAUDE.md quando lo stato della roadmap cambia

### Cosa non fare mai
- `DELETE` su NodeEntity, NodeState, o Edge → usa `is_deleted` o `invalidated_at`
- Accedere al grafo di un utente senza verificare `user_id` → isolamento multi-tenant
- Scrivere nel grafo senza passare per il quality gate (dalla Fase 2 in poi)
- Hard-codare il nome del modello LLM → sempre da config
- Committare il file `.kuzu` del database → è in `.gitignore`

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

# Aprire Python con il progetto
uv run python
```

---

## Contesto decisionale — perché abbiamo scelto X

**Kuzu invece di Neo4j**
Per il prototipo vogliamo zero infrastruttura. Kuzu è embedded come SQLite —
gira in processo, salva su file locale, nessun server da gestire.
Quando il sistema scala o richiede multi-istanza, si migra a Neo4j o FalkorDB.

**Fork come copia invece di link live**
Il destinatario deve poter sperimentare liberamente senza compromettere il grafo
dell'emittente. La copia preserva anche il momento storico — il destinatario
riceve lo stato del grafo in quel preciso istante, e qualsiasi divergenza
successiva è tracciabile. È esattamente il modello Git.

**`confidence` come Float invece di Enum**
La certezza è continua, non categorica. Un Enum (alto/medio/basso) perde
la granularità che rende il sistema utile — la differenza tra 0.71 e 0.69
dopo un esperimento è un segnale reale.

**`trigger` come testo libero invece di strutturato**
Il "perché" di un cambiamento di credenza è spesso narrativo e contestuale.
Un campo strutturato lo impoverirebbe. Il testo libero permette sia
all'utente che all'agente di esprimersi naturalmente.

---

## Use case di riferimento (sintesi)

**UC-01 — Anna e Bruno, virologi**
Anna ha un crollo di confidence (0.7 → 0.2). L'agente trova nel grafo di Bruno
un pattern `recovered` semanticamente simile. Proposta → approvazione →
SubgraphToken → fork. Bruno aveva risolto correggendo il calcolo del pH.

**UC-02 — Il ricercatore solitario**
Utilità pre-rete. Time travel nel proprio pensiero.
"Come si è evoluta la mia confidence sull'ipotesi X nelle ultime 8 settimane?"

**UC-03 — Il team di lab**
5 ricercatori, grafi separati, autonomia preservata.
Il sistema segnala sovrapposizioni e conflitti senza esporre contenuto.

**UC-04 — Il momento del paper**
Il grafo ricostruisce la narrativa completa della ricerca.
I DeadEnd diventano supplementary material strutturato.
La materia oscura diventa dato pubblicato.

---

*Ultima modifica: Maggio 2026 — RFC v0.1*
*Aggiorna questo file a ogni cambio di stato della roadmap.*
