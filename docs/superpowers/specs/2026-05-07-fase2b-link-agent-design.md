# MemoryGraph — Fase 2b: Link Agent — Design Spec

**Data:** 2026-05-07
**Stato:** Bozza
**Scope:** Fase 2b — Link Agent: suggerimento, editing e approvazione batch degli archi

-----

## Obiettivo

Chiudere la Fase 2 completando il grafo semantico.
Il Memory Agent estrae i nodi — il Link Agent li connette.

Senza archi, il grafo è una lista. Con gli archi, diventa una rete di credenze:
ogni nodo sa cosa supporta, cosa contraddice, da cosa deriva, cosa apre.

Il Link Agent gira automaticamente al termine di ogni `agent-extract`,
propone tutti gli archi candidati in una visualizzazione tabellare,
permette all’utente di modificare tipo/confidence prima dell’approvazione,
e scrive solo dopo conferma esplicita.

**Principio invariante:** l’agente suggerisce, l’umano decide.

-----

## Stack

|Componente     |Scelta                                              |
|---------------|----------------------------------------------------|
|Linguaggio     |Python 3.11+ con type hints ovunque                 |
|Graph DB       |Kuzu (stesso file — invariato)                      |
|LLM            |agnostico — `LLMCallable` da `agent/extractor.py`   |
|Embedding      |agnostico — `EmbedCallable` opzionale, pre-filtering|
|Package manager|uv                                                  |
|CLI            |Typer + Rich — tabella interattiva                  |
|Test           |pytest — mock LLM con lambda, copertura minima 80%  |

-----

## Architettura

```
src/memorygraph/agent/
    __init__.py         ← aggiorna esportazioni: + LinkAgent
    extractor.py        ← invariato
    quality.py          ← invariato
    detector.py         ← invariato
    agent.py            ← invariato (MemoryAgent.run() chiama LinkAgent al termine)
    link_agent.py       ← NUOVO: LinkAgent + CandidateEdge + loop tabellare
```

**Flusso integrato post-extract:**

```
MemoryAgent.run(text, user_id, project_id)
    ↓ [esistente] extract → quality → detect → loop approvazione nodi
    ↓ scrittura nodi approvati → lista new_node_ids
    ↓ [NUOVO] LinkAgent.run(user_id, new_node_ids, project_id)
        ↓ carica nodi esistenti del progetto (o utente se no project_id)
        ↓ LLM propone archi candidati tra new_node_ids e nodi esistenti
        ↓ quality gate archi
        ↓ tabella interattiva con editing inline
        ↓ conferma batch → scrittura archi approvati
```

**Regole invarianti:**

- `GraphStore` non viene modificato — solo `create_edge()` e `invalidate_edge()` esistenti
- `LinkAgent` non scrive mai senza conferma esplicita
- Se non vengono approvati nuovi nodi, il link agent non parte (niente da collegare)
- Il link agent propone archi anche tra nodi pre-esistenti quando contestualizzati dai nuovi
- **`LinkAgent` non apre mai una connessione Kuzu diretta.** Riceve sempre un `GraphStore`
  già inizializzato passato dall'esterno (`store=` parameter). Kuzu embedded è single-writer
  per processo: due istanze `kuzu.Database` sullo stesso path non condividono le scritture.
  Questa regola vale per tutti i componenti futuri — SubgraphToken, fork engine, merge engine.

-----

## Tipi fondamentali

```python
@dataclass
class CandidateEdge:
    from_node_id: str
    to_node_id: str
    type: EdgeType
    confidence: float
    reason: str          # spiegazione leggibile dal LLM: perché questo arco?
    is_new_node: bool    # True se almeno uno dei due è appena stato scritto

@dataclass
class ProposedEdge:
    candidate: CandidateEdge
    from_content: str    # preview contenuto nodo sorgente (per la tabella)
    to_content: str      # preview contenuto nodo destinazione (per la tabella)
    approved: bool = True   # default True — l'utente disabilita ciò che non vuole
    edited_type: EdgeType | None = None        # se l'utente modifica il tipo
    edited_confidence: float | None = None    # se l'utente modifica la confidence
```

`ProposedEdge` è il tipo che vive nella tabella interattiva.
`approved=True` di default perché l’utente sta già confermando con un `y` finale —
il modello mentale è “vedo la tabella, tolgo quello che non voglio, confermo tutto il resto”.

-----

## Interfaccia pubblica

```python
class LinkAgent:
    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.4,   # soglia più alta degli archi rispetto ai nodi
    ) -> None: ...

    def propose(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[ProposedEdge]:
        """
        Carica contesto grafo → chiama LLM → ritorna ProposedEdge con preview.
        Non scrive nulla.
        """

    def run(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[str]:
        """
        propose() → tabella interattiva → scrittura archi approvati.
        Ritorna lista edge_id creati.
        Se non ci sono candidati: stampa messaggio e ritorna [].
        """
```

-----

## Flusso dati completo

```
new_node_ids + contesto grafo esistente
    ↓ _load_context() — query Kuzu
lista[NodeState] (nodi esistenti del progetto/utente con loro contenuto)
    ↓ Se embed disponibile: pre-filtering top-k per similarità ai new_node_ids
    ↓ _build_prompt() — una chiamata LLM
JSON: {"edges": [{"from": "...", "to": "...", "type": "...", "confidence": 0.0, "reason": "..."}]}
    ↓ _parse_edges() — parsing robusto + validazione
lista[CandidateEdge]
    ↓ _filter_edges() — confidence >= min_confidence, nodi esistenti, no self-loop
lista[CandidateEdge]
    ↓ _enrich() — risolve from_content e to_content per la preview
lista[ProposedEdge]
    ↓ _render_table() — Rich table interattiva
[utente modifica / deseleziona righe]
    ↓ conferma batch [y/n]
lista[ProposedEdge dove approved=True]
    ↓ GraphStore.create_edge() per ognuno
lista[edge_id]
```

-----

## Prompt LLM (`link_agent.py`)

### Struttura

```
Sei un analista di grafi di conoscenza scientifica.
Hai un insieme di nodi appena aggiunti e un insieme di nodi esistenti nel grafo.
Il tuo compito è identificare le relazioni semantiche significative tra di essi.

EdgeType validi e quando usarli:
- supporta       → il nodo A fornisce evidenza a favore del nodo B
- contraddice    → il nodo A è in tensione o conflitto con il nodo B
- deriva_da      → il nodo A è una conseguenza logica o deduzione del nodo B
- falsifica      → il nodo A è evidenza empirica che invalida il nodo B
- apre_domanda   → il nodo A genera una domanda aperta rappresentata da B
- risolve        → il nodo A risponde o chiude la domanda aperta B

Scala confidence per gli archi:
0.9+    → relazione evidente e diretta, quasi certa
0.6–0.9 → relazione plausibile con motivazione chiara
0.4–0.6 → relazione possibile, vale la pena segnalare
< 0.4   → non proporre — troppo speculativo

Nodi appena aggiunti (da collegare):
{new_nodes_block}

Nodi esistenti nel grafo (contesto):
{existing_nodes_block}

Proponi SOLO archi con motivazione chiara.
Non proporre archi ovvi per completezza — solo quelli semanticamente significativi.
Non proporre più di {max_edges} archi totali.

Rispondi SOLO con JSON valido:
{{"edges": [{{"from": "<node_id>", "to": "<node_id>", "type": "<EdgeType>", "confidence": 0.0, "reason": "<spiegazione breve>"}}]}}
Se non trovi archi significativi: {{"edges": []}}
```

**`max_edges`** — default 10. Cap per evitare tabelle illeggibili.
Se il grafo ha molti nodi e embed è disponibile, il pre-filtering porta già i candidati più rilevanti.

**`new_nodes_block` e `existing_nodes_block`** — formato:

```
[id: abc123] (Hypothesis, conf 0.60) "Ipotizziamo che la protonazione dell'istidina 34..."
[id: def456] (Observation, conf 0.90) "Il legame ACE2-spike era quasi assente a pH 6.8"
```

### JSON parsing

Robusto identico all’extractor:

- strip backtick markdown
- `type` non valido → skip arco (log warning)
- `confidence` fuori range → clamp
- `from`/`to` non trovati nel grafo → skip arco
- self-loop (`from == to`) → skip

-----

## Tabella interattiva CLI

### Rendering (Rich)

```
Archi candidati rilevati (5):

 #   Da                          Tipo          A                            Conf   Motivo
─────────────────────────────────────────────────────────────────────────────────────────────
 1 ✓ [54211d97] Il legame ACE2-  falsifica  → [c34ddd2a] Il pH 7.2 è        0.85   Obs diretta a pH 6.8
     spike era quasi assente...               condizione ottimale...                contraddice il range
 2 ✓ [54211d97] Il legame ACE2-  supporta   → [cccd2c32] Il pH ottimale     0.80   Conf l'ipotesi sulla
     spike era quasi assente...               per il legame è tra 7.0...           soglia 7.0-7.4
 3 ✓ [3a284cda] Ipotizziamo che  deriva_da  → [54211d97] Il legame ACE2-    0.75   L'ipotesi sul meccani-
     la protonazione dell'...                 spike era quasi assente...           smo deriva dall'obs
 4 ✓ [3a284cda] Ipotizziamo che  contraddice→ [51dd7831] Il virus entra     0.65   Propone meccanismo
     la protonazione dell'...                 nella cellula legandosi...           alternativo all'entry
 5 ✓ [54211d97] Il legame ACE2-  apre_domanda→[6956356f] Il pH del cito-    0.55   Osservazione apre la
     spike era quasi assente...               plasma influenza l'...               questione sul range

Comandi: [n <numero>] deseleziona  [t <numero> <tipo>] modifica tipo  [c <numero> <conf>] modifica confidence
         [y] approva selezionati   [N] annulla tutto

>
```

### Comandi interattivi

|Comando              |Comportamento                                    |
|---------------------|-------------------------------------------------|
|`y`                  |Scrive tutti gli archi con `approved=True` — fine|
|`N`                  |Annulla tutto — nessun arco scritto — fine       |
|`n <num>`            |Deseleziona arco `num` (toglie ✓, non lo scrive) |
|`n <num1> <num2> ...`|Deseleziona più archi in una volta               |
|`t <num> <tipo>`     |Modifica EdgeType dell’arco `num`                |
|`c <num> <valore>`   |Modifica confidence dell’arco `num` (0.0–1.0)    |

Dopo ogni comando di modifica, la tabella viene ridisegnata (Rich live update).

**Nessun loop nodo-per-nodo.** L’utente vede tutto insieme,
modifica ciò che vuole, poi approva con un singolo `y`.

### Caso zero archi

```
✓ Nodi scritti: 2 (54211d97, 3a284cda)
  Nessun arco significativo rilevato — grafo aggiornato.
```

Nessun prompt, nessuna interruzione.

-----

## Integrazione in `MemoryAgent.run()`

```python
# agent.py — modifica minima

def run(
    self,
    text: str,
    project_id: str | None = None,
    user_id: str = "",
) -> list[str]:
    """Estrae nodi → approva → scrive → propone archi."""
    # [logica esistente invariata]
    written_node_ids: list[str] = [...]   # nodi approvati e scritti

    # [NUOVO] Link Agent — solo se ci sono nodi scritti
    if written_node_ids:
        from memorygraph.agent.link_agent import LinkAgent
        link_agent = LinkAgent(self._db_path, self._llm, self._embed, self._min_confidence)
        link_agent.run(written_node_ids, user_id=user_id, project_id=project_id)

    return written_node_ids
```

L’import è locale (dentro `if`) per mantenere la dipendenza lazy
e non rompere nulla se `link_agent.py` non esiste ancora nei test legacy.

-----

## Quality gate archi

```python
def _filter_edges(
    candidates: list[CandidateEdge],
    valid_node_ids: set[str],
    min_confidence: float = 0.4,
) -> list[CandidateEdge]:
```

|Criterio                               |Comportamento       |
|---------------------------------------|--------------------|
|`confidence < min_confidence`          |Scartato            |
|`from_node_id` non in grafo            |Scartato            |
|`to_node_id` non in grafo              |Scartato            |
|`from_node_id == to_node_id`           |Scartato (self-loop)|
|`type` non valido                      |Scartato            |
|Duplicato esatto (stessa coppia + tipo)|Scartato il secondo |

La soglia minima per gli archi (`0.4`) è volutamente più alta di quella dei nodi (`0.3`):
un arco errato è più rumoroso di un nodo errato — introduce relazioni false nel grafo.

-----

## Testing

### Strategia

```python
mock_llm_edges = lambda p: json.dumps({"edges": [
    {"from": "node_a", "to": "node_b", "type": "supporta", "confidence": 0.8, "reason": "..."},
]})
agent = LinkAgent(db_path, llm=mock_llm_edges)
```

### Test richiesti

|Modulo                   |Test                                                    |
|-------------------------|--------------------------------------------------------|
|`link_agent.py` — propose|LLM ritorna archi validi → lista ProposedEdge           |
|`link_agent.py` — propose|JSON con backtick markdown → parsificato correttamente  |
|`link_agent.py` — propose|type non valido → arco skippato                         |
|`link_agent.py` — propose|confidence < min_confidence → arco filtrato             |
|`link_agent.py` — propose|self-loop → arco filtrato                               |
|`link_agent.py` — propose|node_id non in grafo → arco filtrato                    |
|`link_agent.py` — propose|nodi new + existing → from_content e to_content popolati|
|`link_agent.py` — propose|lista vuota se LLM ritorna {“edges”: []}                |
|`link_agent.py` — run    |archi approvati → scritti in GraphStore                 |
|`link_agent.py` — run    |archi deselezionati → non scritti                       |
|`link_agent.py` — run    |nessun candidato → ritorna [] senza prompt              |
|`agent.py` — run         |scrive nodi poi chiama LinkAgent.run()                  |
|`agent.py` — run         |se zero nodi approvati → LinkAgent.run() non chiamato   |

Copertura minima: 80%.

-----

## File modificati / creati

### Nuovo file

|File                                 |Responsabilità                                       |
|-------------------------------------|-----------------------------------------------------|
|`src/memorygraph/agent/link_agent.py`|`LinkAgent`, `CandidateEdge`, `ProposedEdge`, tabella|
|`tests/test_agent/test_link_agent.py`|13 test su LinkAgent                                 |

### File modificati

|File                               |Modifica                                          |
|-----------------------------------|--------------------------------------------------|
|`src/memorygraph/agent/__init__.py`|Aggiunge export `LinkAgent`                       |
|`src/memorygraph/agent/agent.py`   |`run()` chiama `LinkAgent.run()` dopo nodi scritti|
|`cli/main.py`                      |Output aggiornato: stampa anche edge_id scritti   |

### File invariati

`extractor.py`, `quality.py`, `detector.py`, `graph/store.py`, `context/` — zero modifiche.

-----

## Regole di sviluppo invarianti

- Mai `DELETE` — solo `invalidate_edge()` esistente
- `GraphStore` non viene modificato — solo usato tramite API pubblica
- `LinkAgent` non scrive mai senza `y` esplicito dall’utente
- Nessun import da `anthropic`, `openai`, o qualsiasi provider LLM in `link_agent.py`
- Un test per ogni comportamento pubblico significativo
- **Nessun componente apre `GraphStore(db_path)` internamente.** Il `GraphStore` viene
  creato una volta nel processo principale e passato esplicitamente a tutti i componenti
  che ne hanno bisogno. Motivazione: Kuzu embedded è single-writer per processo — due
  istanze concorrenti sullo stesso path producono scritture invisibili alle connessioni
  successive. Confermato in produzione durante Fase 2b.

-----

*Ultima modifica: 2026-05-07 — Fase 2b completata — invariante connessione Kuzu aggiunto*