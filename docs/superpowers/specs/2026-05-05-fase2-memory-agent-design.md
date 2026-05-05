# MemoryGraph — Fase 2: Memory Agent — Design Spec

**Data:** 2026-05-05
**Stato:** Approvato
**Scope:** Fase 2 — Memory Agent: extractor, quality gate, confidence estimator, contradiction detector

---

## Obiettivo

Costruire il Memory Agent — il componente che trasforma testo libero in nodi candidati,
li filtra, rileva contraddizioni, e li propone all'utente per approvazione esplicita prima
di qualsiasi scrittura nel grafo.

Principio invariante: **l'agente suggerisce, l'umano decide.**
Il Memory Agent non scrive mai nel grafo senza approvazione esplicita dell'utente.

---

## Stack

| Componente | Scelta |
|---|---|
| Linguaggio | Python 3.11+ con type hints ovunque |
| Graph DB | Kuzu (stesso file di Fase 1 e 1b — non toccato) |
| LLM | agnostico — `LLMCallable = Callable[[str], str]` |
| Embedding | agnostico — `EmbedCallable = Callable[[str], list[float]]` opzionale |
| Package manager | uv |
| CLI | Typer (esteso — nuovi comandi in `cli/main.py`) |
| Test | pytest — mock LLM con lambda, copertura minima 80% |

---

## Architettura

```
src/memorygraph/agent/
    __init__.py     ← esporta MemoryAgent
    extractor.py    ← LLM → lista[CandidateNode] (JSON parsing + validazione)
    quality.py      ← filtra candidati sotto soglia di confidence
    detector.py     ← contradiction detection (progetto-scoped, embed opzionale)
    agent.py        ← MemoryAgent: orchestrazione + loop di approvazione CLI
```

**Regole invarianti:**
- `GraphStore` e `ContextStore` non vengono modificati — il Memory Agent li usa
- `MemoryAgent` non scrive mai senza approvazione esplicita
- `Project.full_context` è accessibile al Memory Agent tramite `agent_context=True`
- Nessuna dipendenza hard da provider LLM o embedding

---

## Tipi fondamentali

```python
LLMCallable = Callable[[str], str]
EmbedCallable = Callable[[str], list[float]]

@dataclass
class CandidateNode:
    type: NodeType
    content: str
    confidence: float
    trigger: str
    project_id: str | None = None  # scoper la contradiction detection

@dataclass
class ContradictionHint:
    existing_node_id: str
    reason: str   # spiegazione in testo libero dal LLM

@dataclass
class ProposedNode:
    candidate: CandidateNode
    hint: ContradictionHint | None = None  # None se nessuna contraddizione rilevata
```

`CandidateNode.project_id` porta il contesto con sé attraverso la pipeline,
evitando di passarlo come parametro separato.
`ProposedNode` è il tipo di output del quality gate + detector — candidato + eventuale hint
in un unico oggetto prima del loop CLI.

---

## Interfaccia pubblica

```python
class MemoryAgent:
    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.3,
    ) -> None: ...

    def extract(self, text: str, project_id: str | None = None) -> list[CandidateNode]:
        """Chiama LLM → parsifica JSON → ritorna candidati non filtrati."""

    def propose(self, text: str, project_id: str | None = None) -> list[ProposedNode]:
        """extract → quality gate → contradiction detection → lista ProposedNode per il loop CLI."""

    def run(self, text: str, project_id: str | None = None, user_id: str = "") -> list[str]:
        """Esegue propose + loop di approvazione CLI → scrive nodi approvati → ritorna node_id[]."""
```

Nei test il mock LLM diventa banale:
```python
mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "...", "confidence": 0.7, "trigger": "..."}]}'
agent = MemoryAgent(db_path, llm=mock_llm)
```

---

## Flusso dati completo

```
testo libero
    ↓ extractor.py — una chiamata LLM
lista[CandidateNode]   (JSON parsed, confidence calibrata)
    ↓ quality.py
lista[CandidateNode]   (filtrati: confidence >= min_confidence, content non vuoto)
    ↓ detector.py
lista[ProposedNode]    (candidato + eventuale ContradictionHint)
    ↓ agent.py — loop CLI
per ogni candidato → mostra → y/n/s/a
    ↓ solo approvati
GraphStore.create_node(user_id, type, content, confidence, trigger)
se ContradictionHint approvato → GraphStore.create_edge(CONTRADDICE)
```

---

## Extractor (`extractor.py`)

### Interfaccia

```python
def extract(text: str, llm: LLMCallable, project_context: str | None = None) -> list[CandidateNode]:
    """Chiama LLM con il prompt strutturato, parsifica JSON, ritorna candidati."""
```

### Struttura del prompt

Il prompt include in ordine:

1. **Istruzioni di ruolo** — "Sei un estrattore di credenze da testo scientifico."
2. **NodeType validi con criteri di scelta:**
   ```
   NodeType validi: Observation, Hypothesis, Conclusion, DeadEnd,
   OpenQuestion, Paper, Experiment, MethodDecision

   Scegli il tipo più specifico:
   - Observation  → fatto empirico osservato direttamente
   - Hypothesis   → ipotesi da verificare, anche se il testo usa "forse", "potrebbe"
   - Conclusion   → validata, alta certezza
   - DeadEnd      → fallimento, strada chiusa, falsificazione
   - OpenQuestion → domanda senza risposta ancora
   - Paper        → citazione di fonte esterna, articolo, dataset
   - Experiment   → descrizione di un esperimento con metodo/risultato
   - MethodDecision → scelta metodologica con ragionamento

   Se il testo esprime incertezza esplicita → Hypothesis o OpenQuestion.
   Se descrive un fallimento → DeadEnd.
   Se cita una fonte esterna → Paper.
   ```
3. **Scala di confidence esplicita:**
   ```
   Scala confidence:
   0.9+    → fatto empirico osservato direttamente
   0.6–0.9 → ipotesi con evidenza parziale
   0.3–0.6 → speculazione o evidenza debole
   < 0.3   → dubbio esplicito — includi solo se il contenuto è significativo
   ```
4. **Contesto del progetto** (se `project_context` presente — `Project.full_context`):
   ```
   Contesto del progetto:
   {project_context}
   ```
5. **Testo da analizzare:**
   ```
   Testo:
   {text}
   ```
6. **Formato output atteso:**
   ```
   Rispondi SOLO con JSON valido in questo formato:
   {"nodes": [{"type": "...", "content": "...", "confidence": 0.0, "trigger": "..."}]}
   Se non trovi nodi significativi, rispondi: {"nodes": []}
   ```

### JSON parsing

Il parser deve essere robusto a:
- LLM che wrappa il JSON in backtick markdown (strip ` ```json ... ``` `)
- Campi mancanti → `CandidateNode` con valori default sicuri o skip del nodo
- `type` non riconosciuto → skip del nodo (log warning)
- `confidence` fuori range [0.0, 1.0] → clamp

---

## Quality Gate (`quality.py`)

### Interfaccia

```python
def filter_candidates(
    candidates: list[CandidateNode],
    min_confidence: float = 0.3,
) -> list[CandidateNode]:
    """Filtra i candidati che non soddisfano i criteri minimi."""
```

### Criteri di filtro (Fase 2)

| Criterio | Comportamento |
|---|---|
| `confidence < min_confidence` | Scartato |
| `content` vuoto o solo whitespace | Scartato |
| `type` non valido | Scartato (già gestito da extractor) |

La deduplicazione non è in scope per Fase 2 — il grafo gestisce la storia e
due nodi con contenuto simile possono essere entrambi validi.

---

## Contradiction Detector (`detector.py`)

### Interfaccia

```python
def detect(
    candidate: CandidateNode,
    project_nodes: list[NodeState],   # pre-caricati dall'agente — più testabile
    llm: LLMCallable,
    embed: EmbedCallable | None = None,
    top_k: int = 5,
) -> ContradictionHint | None:
    """Rileva se il candidato contraddice nodi esistenti nel progetto."""
```

`project_nodes` viene pre-caricato da `MemoryAgent` prima di chiamare `detect`.
`MemoryAgent` usa una query Kuzu diretta `MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project)
WHERE p.id = $pid` — nessuna modifica a GraphStore necessaria.

### Flusso

```
Se candidate.project_id è None o project_nodes è vuoto → return None (skip)
    ↓
Se embed=None:
    Prepara prompt con candidato + tutti i nodi del progetto
    LLM risponde: {"contradiction": true/false, "node_id": "...", "reason": "..."}
    Se contradiction=true → return ContradictionHint(...)

Se embed!=None:
    embed(candidate.content) → vettore candidato
    calcola cosine similarity contro embed di tutti i nodi progetto
    prendi top_k più simili
    LLM conferma se c'è contraddizione reale tra candidato e top-k
    Se confermata → return ContradictionHint(...)
```

### Semantica

La contraddizione è un **segnale, non un veto.**
Un `ContradictionHint` non blocca il nodo — lo annota nella proposta.
L'utente decide se approvare il nodo con o senza l'arco `CONTRADDICE`.

---

## Loop di approvazione CLI (`agent.py`)

### Prompt per ogni candidato

```
[2/5] Nodo candidato:
  Tipo:       Hypothesis
  Contenuto:  Il virus entra legandosi ad ACE2
  Confidence: 0.70
  Trigger:    Lettura paper Zhang et al.
  ⚠ Possibile contraddizione con nodo abc-123:
    "ACE2 non è il recettore primario" (rilevata dall'agente)

Approva questo nodo? [y/n/s/a]:
```

### Opzioni

| Tasto | Comportamento |
|---|---|
| `y` | Approva questo nodo. Se ContradictionHint presente → chiede "Creare arco CONTRADDICE? [y/n]" |
| `n` | Scarta questo nodo — non viene scritto nel grafo |
| `s` | Salta tutti i rimanenti (batch reject) |
| `a` | Approva tutti i rimanenti senza ulteriori prompt (batch approve) |

`s` e `a` sono simmetrici: l'utente sta sempre decidendo, solo in bulk.
Il batch approve non viola "l'agente suggerisce, l'umano decide" — l'utente ha già visto
i candidati e sceglie consapevolmente di approvare il resto.

---

## Testing

### Strategia

```python
mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "...", "confidence": 0.7, "trigger": "..."}]}'
mock_embed = lambda t: [0.1, 0.2, 0.3, ...]  # vettore fisso
agent = MemoryAgent(db_path, llm=mock_llm, embed=None)
```

### Test richiesti

| Modulo | Test |
|---|---|
| `extractor.py` | extract ritorna CandidateNode validi |
| `extractor.py` | JSON con backtick markdown viene parsificato correttamente |
| `extractor.py` | type non riconosciuto → nodo skippato |
| `extractor.py` | confidence fuori range → clampata |
| `extractor.py` | full_context incluso nel prompt se project_id presente |
| `quality.py` | candidato sotto soglia → filtrato |
| `quality.py` | content vuoto → filtrato |
| `quality.py` | candidato valido → passato |
| `detector.py` | project_id=None o project_nodes vuoto → None ritornato |
| `detector.py` | LLM rileva contraddizione → ContradictionHint ritornato |
| `detector.py` | LLM non rileva contraddizione → None ritornato |
| `detector.py` | embed presente → top-k calcolato, LLM chiamato solo su top-k |
| `agent.py` | run con y → nodo scritto in GraphStore |
| `agent.py` | run con n → nodo non scritto |
| `agent.py` | run con s → solo nodi già approvati scritti |
| `agent.py` | run con a → tutti i rimanenti scritti |
| `agent.py` | ContradictionHint approvato → arco CONTRADDICE creato |

Copertura minima: 80% — obiettivo 95%+ come le fasi precedenti.

---

## CLI — nuovi comandi

```bash
# Analizza un testo e propone nodi interattivamente
uv run python cli/main.py agent-extract \
  --user-id <uuid> \
  --text "Il pH ottimale per la reazione è 7.4, ma ho osservato..." \
  --project-id <uuid>   # opzionale

# Legge il testo da stdin
echo "Il virus entra legandosi ad ACE2..." | \
  uv run python cli/main.py agent-extract --user-id <uuid> --stdin
```

---

## Regole di sviluppo invarianti (Fase 2)

- Mai `DELETE` — solo `is_deleted=True` o `invalidated_at=now()`
- `GraphStore` e `ContextStore` non vengono modificati
- `MemoryAgent` non scrive mai senza `y` o `a` esplicito dall'utente
- `Project.full_context` accessibile solo con `agent_context=True`
- Nessun import da `anthropic`, `openai`, o qualsiasi provider LLM
- Un test per ogni metodo pubblico

---

*Ultima modifica: 2026-05-05 — Design approvato — pronto per writing-plans*
