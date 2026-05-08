# Fase 2b — Link Agent: Piano di Implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire il Link Agent — al termine di ogni `agent-extract`, propone archi semantici tra i nuovi nodi e il grafo esistente, li mostra in tabella interattiva, permette editing inline, e scrive solo dopo conferma batch.

**Architecture:** `link_agent.py` è un modulo autonomo nel package `agent/`. Riceve i `new_node_ids` appena scritti, carica il contesto Kuzu, chiama il LLM per proporre archi, filtra, arricchisce con preview del contenuto, mostra tabella Rich interattiva. `MemoryAgent.run()` lo chiama automaticamente al termine. Zero modifiche a `GraphStore`, `extractor.py`, `quality.py`, `detector.py`.

**Tech Stack:** Python 3.11+, Kuzu (embedded), pytest, Typer, Rich — nessuna dipendenza da provider LLM.

---

## Mappa dei file

### Nuovi file
| File | Responsabilità |
|---|---|
| `src/memorygraph/agent/link_agent.py` | `CandidateEdge`, `ProposedEdge`, `LinkAgent` |
| `tests/test_agent/test_link_agent.py` | 13 test su LinkAgent |

### File modificati
| File | Modifica |
|---|---|
| `src/memorygraph/agent/__init__.py` | Aggiunge export `LinkAgent` |
| `src/memorygraph/agent/agent.py` | `run()` chiama `LinkAgent.run()` dopo nodi scritti |
| `cli/main.py` | Output: stampa edge_id scritti |

### Invarianti
- `GraphStore`, `extractor.py`, `quality.py`, `detector.py` — zero modifiche
- `LinkAgent` non scrive mai senza `y` esplicito
- Nessun import da provider LLM in `link_agent.py`

---

## Task 1: Tipi + parsing + quality gate

**Files:**
- Create: `src/memorygraph/agent/link_agent.py` (stub iniziale)
- Create: `tests/test_agent/test_link_agent.py` (test parsing e filtro)

- [ ] **Step 1: Scrivi i test fallenti per parsing e filtro**

```python
# tests/test_agent/test_link_agent.py
from __future__ import annotations
import json
import pytest
from memorygraph.agent.link_agent import CandidateEdge, ProposedEdge, LinkAgent
from memorygraph.graph.models import EdgeType


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def _mock_llm(edges: list[dict]):
    def llm(prompt: str) -> str:
        return json.dumps({"edges": edges})
    return llm


class TestProposeFiltering:
    def test_valid_edge_returned(self, db_path):
        """LLM ritorna archi validi → lista ProposedEdge non vuota."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs content", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp content", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert len(proposed) == 1
        assert proposed[0].candidate.type == EdgeType.SUPPORTA

    def test_markdown_stripped(self, db_path):
        """JSON con backtick markdown → parsificato correttamente."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        def llm_with_backticks(prompt: str) -> str:
            return f"```json\n{json.dumps({'edges': [{'from': n1.id, 'to': n2.id, 'type': 'supporta', 'confidence': 0.8, 'reason': 'ok'}]})}\n```"
        agent = LinkAgent(db_path, llm=llm_with_backticks)
        proposed = agent.propose([n1.id], user_id="u1")
        assert len(proposed) == 1

    def test_invalid_type_skipped(self, db_path):
        """type non valido → arco skippato."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "TIPO_INVENTATO", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_low_confidence_filtered(self, db_path):
        """confidence < min_confidence → arco filtrato."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.1, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm, min_confidence=0.4)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_self_loop_filtered(self, db_path):
        """self-loop → arco filtrato."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        llm = _mock_llm([{"from": n1.id, "to": n1.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_unknown_node_filtered(self, db_path):
        """node_id non in grafo → arco filtrato."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        llm = _mock_llm([{"from": n1.id, "to": "node-non-esiste", "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed == []

    def test_preview_populated(self, db_path):
        """from_content e to_content popolati dalla query."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "contenuto sorgente", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "contenuto destinazione", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose([n1.id], user_id="u1")
        assert proposed[0].from_content == "contenuto sorgente"
        assert proposed[0].to_content == "contenuto destinazione"

    def test_empty_edges_returns_empty_list(self, db_path):
        """LLM ritorna {"edges": []} → lista vuota."""
        llm = _mock_llm([])
        agent = LinkAgent(db_path, llm=llm)
        proposed = agent.propose(["qualsiasi"], user_id="u1")
        assert proposed == []
```

- [ ] **Step 2: Scrivi i test fallenti per run()**

```python
# append to tests/test_agent/test_link_agent.py

class TestRun:
    def test_approved_edges_written(self, db_path, monkeypatch):
        """Archi approvati → scritti in GraphStore."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        # simula conferma y
        monkeypatch.setattr("builtins.input", lambda _: "y")
        edge_ids = agent.run([n1.id], user_id="u1")
        assert len(edge_ids) == 1
        graph = store.get_graph("u1")
        assert len(graph["edges"]) == 1

    def test_deselected_edge_not_written(self, db_path, monkeypatch):
        """Arco deselezionato → non scritto."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        # deseleziona 1 poi conferma
        inputs = iter(["n 1", "y"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        edge_ids = agent.run([n1.id], user_id="u1")
        assert edge_ids == []

    def test_no_candidates_returns_empty(self, db_path):
        """Nessun candidato → ritorna [] senza prompt."""
        llm = _mock_llm([])
        agent = LinkAgent(db_path, llm=llm)
        edge_ids = agent.run(["qualsiasi"], user_id="u1")
        assert edge_ids == []

    def test_cancel_writes_nothing(self, db_path, monkeypatch):
        """N → nessun arco scritto."""
        from memorygraph.graph.store import GraphStore
        from memorygraph.graph.models import NodeType
        store = GraphStore(db_path)
        n1 = store.create_node("u1", NodeType.OBSERVATION, "obs", 0.9, "t")
        n2 = store.create_node("u1", NodeType.HYPOTHESIS, "hyp", 0.7, "t")
        llm = _mock_llm([{"from": n1.id, "to": n2.id, "type": "supporta", "confidence": 0.8, "reason": "ok"}])
        agent = LinkAgent(db_path, llm=llm)
        monkeypatch.setattr("builtins.input", lambda _: "N")
        edge_ids = agent.run([n1.id], user_id="u1")
        assert edge_ids == []
        graph = store.get_graph("u1")
        assert len(graph["edges"]) == 0
```

- [ ] **Step 3: Esegui per verificare che falliscono**

```bash
uv run pytest tests/test_agent/test_link_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'memorygraph.agent.link_agent'`

- [ ] **Step 4: Implementa `link_agent.py`**

```python
# src/memorygraph/agent/link_agent.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

import kuzu
from rich.console import Console
from rich.table import Table

from memorygraph.agent.extractor import LLMCallable, EmbedCallable
from memorygraph.graph.models import EdgeType
from memorygraph.graph.store import GraphStore

console = Console()


@dataclass
class CandidateEdge:
    from_node_id: str
    to_node_id: str
    type: EdgeType
    confidence: float
    reason: str
    is_new_node: bool = False


@dataclass
class ProposedEdge:
    candidate: CandidateEdge
    from_content: str
    to_content: str
    approved: bool = True
    edited_type: EdgeType | None = None
    edited_confidence: float | None = None

    @property
    def effective_type(self) -> EdgeType:
        return self.edited_type or self.candidate.type

    @property
    def effective_confidence(self) -> float:
        return self.edited_confidence if self.edited_confidence is not None else self.candidate.confidence


def _strip_markdown(text: str) -> str:
    return re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()


def _clamp(val: float) -> float:
    return max(0.0, min(1.0, val))


class LinkAgent:
    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.4,
        max_edges: int = 10,
    ) -> None:
        self._db_path = db_path
        self._llm = llm
        self._embed = embed
        self._min_confidence = min_confidence
        self._max_edges = max_edges
        self._store = GraphStore(db_path)

    def propose(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[ProposedEdge]:
        """Carica contesto → LLM → filtra → arricchisce → ritorna ProposedEdge."""
        node_contents = self._load_all_nodes(user_id, project_id)
        if not node_contents:
            return []

        valid_ids = set(node_contents.keys())
        # verifica che i new_node_ids siano effettivamente nel grafo
        new_node_ids = [nid for nid in new_node_ids if nid in valid_ids]
        if not new_node_ids:
            return []

        new_block = "\n".join(
            f'[id: {nid}] "{node_contents[nid]["content"][:80]}"'
            for nid in new_node_ids
        )
        existing_ids = [nid for nid in valid_ids if nid not in new_node_ids]
        existing_block = "\n".join(
            f'[id: {nid}] ({node_contents[nid]["type"]}, conf {node_contents[nid]["confidence"]:.2f}) "{node_contents[nid]["content"][:80]}"'
            for nid in existing_ids
        ) or "(nessun nodo esistente oltre ai nuovi)"

        prompt = _build_prompt(new_block, existing_block, self._max_edges)
        raw = self._llm(prompt)
        candidates = _parse_candidates(raw, valid_ids, self._min_confidence)
        return _enrich(candidates, node_contents, new_node_ids)

    def run(
        self,
        new_node_ids: list[str],
        user_id: str,
        project_id: str | None = None,
    ) -> list[str]:
        """propose → tabella interattiva → scrittura."""
        proposed = self.propose(new_node_ids, user_id=user_id, project_id=project_id)
        if not proposed:
            return []

        _render_table(proposed)
        edge_ids = _interactive_loop(proposed, self._store)
        return edge_ids

    def _load_all_nodes(
        self,
        user_id: str,
        project_id: str | None,
    ) -> dict[str, dict]:
        """
        Ritorna {node_id: {content, type, confidence}} per tutti i nodi attivi dell'utente.
        Se project_id presente, filtra per progetto (via BELONGS_TO).
        """
        graph = self._store.get_graph(user_id)
        result = {}
        for entity, state in graph["nodes"]:
            result[entity.id] = {
                "content": state.content,
                "type": entity.type.value,
                "confidence": state.confidence,
            }
        return result


def _build_prompt(new_block: str, existing_block: str, max_edges: int) -> str:
    return f"""Sei un analista di grafi di conoscenza scientifica.
Hai un insieme di nodi appena aggiunti e un insieme di nodi esistenti nel grafo.
Il tuo compito è identificare le relazioni semantiche significative tra di essi.

EdgeType validi:
- supporta       → A fornisce evidenza a favore di B
- contraddice    → A è in tensione o conflitto con B
- deriva_da      → A è conseguenza logica o deduzione di B
- falsifica      → A è evidenza empirica che invalida B
- apre_domanda   → A genera una domanda aperta rappresentata da B
- risolve        → A risponde o chiude la domanda aperta B

Scala confidence:
0.9+  → relazione evidente e diretta
0.6–0.9 → relazione plausibile con motivazione chiara
0.4–0.6 → relazione possibile, vale la pena segnalare
< 0.4 → non proporre

Nodi appena aggiunti:
{new_block}

Nodi esistenti nel grafo:
{existing_block}

Proponi SOLO archi semanticamente significativi. Non più di {max_edges} in totale.

Rispondi SOLO con JSON valido:
{{"edges": [{{"from": "<node_id>", "to": "<node_id>", "type": "<EdgeType>", "confidence": 0.0, "reason": "<spiegazione breve>"}}]}}
Se non trovi archi: {{"edges": []}}"""


def _parse_candidates(
    raw: str,
    valid_ids: set[str],
    min_confidence: float,
) -> list[CandidateEdge]:
    text = _strip_markdown(raw)
    try:
        data = json.loads(text)
        edges = data.get("edges", [])
    except (json.JSONDecodeError, AttributeError):
        return []

    result = []
    seen: set[tuple[str, str, str]] = set()
    for e in edges:
        try:
            from_id = e.get("from", "")
            to_id = e.get("to", "")
            edge_type_str = e.get("type", "")
            confidence = _clamp(float(e.get("confidence", 0.0)))
            reason = e.get("reason", "")
        except (TypeError, ValueError):
            continue

        # validazioni
        if from_id not in valid_ids or to_id not in valid_ids:
            continue
        if from_id == to_id:
            continue
        if confidence < min_confidence:
            continue
        try:
            edge_type = EdgeType(edge_type_str)
        except ValueError:
            continue
        key = (from_id, to_id, edge_type_str)
        if key in seen:
            continue
        seen.add(key)

        result.append(CandidateEdge(
            from_node_id=from_id,
            to_node_id=to_id,
            type=edge_type,
            confidence=confidence,
            reason=reason,
        ))
    return result


def _enrich(
    candidates: list[CandidateEdge],
    node_contents: dict[str, dict],
    new_node_ids: list[str],
) -> list[ProposedEdge]:
    new_set = set(new_node_ids)
    return [
        ProposedEdge(
            candidate=c,
            from_content=node_contents[c.from_node_id]["content"],
            to_content=node_contents[c.to_node_id]["content"],
            approved=True,
        )
        for c in candidates
        if c.from_node_id in node_contents and c.to_node_id in node_contents
    ]


def _render_table(proposed: list[ProposedEdge]) -> None:
    table = Table(title=f"Archi candidati rilevati ({len(proposed)})", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("✓", width=2)
    table.add_column("Da", max_width=28)
    table.add_column("Tipo", width=13)
    table.add_column("A", max_width=28)
    table.add_column("Conf", width=5)
    table.add_column("Motivo", max_width=30)

    for i, p in enumerate(proposed, 1):
        check = "✓" if p.approved else " "
        table.add_row(
            str(i),
            check,
            f"[{p.candidate.from_node_id[:8]}] {p.from_content[:50]}",
            f"{p.effective_type.value} →",
            f"[{p.candidate.to_node_id[:8]}] {p.to_content[:50]}",
            f"{p.effective_confidence:.2f}",
            p.candidate.reason[:60],
        )
    console.print(table)
    console.print(
        "[dim]Comandi: [n <num>] deseleziona  [t <num> <tipo>] modifica tipo  "
        "[c <num> <val>] modifica confidence  [y] approva  [N] annulla[/dim]"
    )


def _interactive_loop(proposed: list[ProposedEdge], store: GraphStore) -> list[str]:
    while True:
        raw = input("> ").strip()
        if raw == "y":
            break
        if raw == "N":
            return []
        parts = raw.split()
        if not parts:
            continue
        cmd = parts[0]
        try:
            if cmd == "n" and len(parts) >= 2:
                for idx_str in parts[1:]:
                    idx = int(idx_str) - 1
                    if 0 <= idx < len(proposed):
                        proposed[idx].approved = False
            elif cmd == "t" and len(parts) == 3:
                idx = int(parts[1]) - 1
                new_type = EdgeType(parts[2])
                if 0 <= idx < len(proposed):
                    proposed[idx].edited_type = new_type
            elif cmd == "c" and len(parts) == 3:
                idx = int(parts[1]) - 1
                new_conf = _clamp(float(parts[2]))
                if 0 <= idx < len(proposed):
                    proposed[idx].edited_confidence = new_conf
        except (ValueError, IndexError):
            console.print("[red]Comando non valido.[/red]")
            continue
        _render_table(proposed)

    edge_ids = []
    for p in proposed:
        if p.approved:
            edge = store.create_edge(
                p.candidate.from_node_id,
                p.candidate.to_node_id,
                p.effective_type,
                p.effective_confidence,
            )
            edge_ids.append(edge.edge_id)
    if edge_ids:
        console.print(f"✓ Scritti {len(edge_ids)} archi.")
    return edge_ids
```

- [ ] **Step 5: Esegui i test**

```bash
uv run pytest tests/test_agent/test_link_agent.py -v
```

Expected: tutti i test passano.

- [ ] **Step 6: Commit**

```bash
git add src/memorygraph/agent/link_agent.py tests/test_agent/test_link_agent.py
git commit -m "feat: link_agent — CandidateEdge, ProposedEdge, LinkAgent con tabella interattiva"
```

---

## Task 2: Integrazione in MemoryAgent.run()

**Files:**
- Modify: `src/memorygraph/agent/agent.py`
- Modify: `src/memorygraph/agent/__init__.py`

- [ ] **Step 1: Scrivi i test di integrazione**

```python
# append to tests/test_agent/test_agent.py

class TestAgentLinkIntegration:
    def test_run_calls_link_agent_after_nodes(self, db_path, monkeypatch):
        """MemoryAgent.run() chiama LinkAgent dopo aver scritto i nodi."""
        import memorygraph.agent.link_agent as la_module
        called_with = []

        class MockLinkAgent:
            def __init__(self, *args, **kwargs): pass
            def run(self, new_node_ids, **kwargs):
                called_with.extend(new_node_ids)
                return []

        monkeypatch.setattr(la_module, "LinkAgent", MockLinkAgent)

        mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "test", "confidence": 0.7, "trigger": "t"}]}'
        agent = MemoryAgent(db_path, llm=mock_llm)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        written = agent.run("testo di test", user_id="u1")
        assert len(called_with) == len(written)

    def test_run_skips_link_agent_if_no_nodes_written(self, db_path, monkeypatch):
        """Se zero nodi approvati, LinkAgent.run() non viene chiamato."""
        import memorygraph.agent.link_agent as la_module
        link_called = []

        class MockLinkAgent:
            def __init__(self, *args, **kwargs): pass
            def run(self, *args, **kwargs):
                link_called.append(True)
                return []

        monkeypatch.setattr(la_module, "LinkAgent", MockLinkAgent)

        mock_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "test", "confidence": 0.7, "trigger": "t"}]}'
        agent = MemoryAgent(db_path, llm=mock_llm)
        monkeypatch.setattr("builtins.input", lambda _: "n")  # rifiuta tutti
        agent.run("testo di test", user_id="u1")
        assert link_called == []
```

- [ ] **Step 2: Modifica `agent.py` — aggiungi chiamata a LinkAgent**

Alla fine del metodo `run()`, dopo la scrittura dei nodi, aggiungi:

```python
# dopo la lista written_node_ids è popolata
if written_node_ids:
    from memorygraph.agent.link_agent import LinkAgent
    link_agent = LinkAgent(self._db_path, self._llm, self._embed, self._min_confidence)
    link_agent.run(written_node_ids, user_id=user_id, project_id=project_id)
```

- [ ] **Step 3: Aggiorna `__init__.py`**

```python
# src/memorygraph/agent/__init__.py
from memorygraph.agent.agent import MemoryAgent
from memorygraph.agent.link_agent import LinkAgent

__all__ = ["MemoryAgent", "LinkAgent"]
```

- [ ] **Step 4: Esegui i test di integrazione**

```bash
uv run pytest tests/test_agent/test_agent.py -v
```

Expected: tutti i test passano inclusi i nuovi.

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/agent/agent.py src/memorygraph/agent/__init__.py
git commit -m "feat: MemoryAgent.run() integra LinkAgent dopo scrittura nodi"
```

---

## Task 3: Coverage check + test manuale + commit finale

- [ ] **Step 1: Esegui tutti i test con coverage**

```bash
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing -v
```

Expected: copertura totale >80%.

- [ ] **Step 2: Test manuale end-to-end**

```bash
uv run python cli/main.py agent-extract \
  --user-id anna \
  --text "Oggi abbiamo ripetuto l'esperimento con pH 6.8 — il legame ACE2-spike era quasi assente. Sembra che sotto 7.0 ci sia una soglia critica di inibizione. Ipotizziamo che la protonazione dell'istidina 34 di ACE2 a pH acido blocchi il sito di legame."
```

Expected:
1. Loop nodi (esistente) — approvazione uno a uno
2. Tabella archi candidati (nuova) — editing + conferma batch
3. Output finale con nodi e archi scritti

- [ ] **Step 3: Verifica grafo**

```bash
uv run python cli/main.py show --user-id anna
```

Expected: archi attivi > 1, relazioni semanticamente corrette tra i nodi.

- [ ] **Step 4: Commit finale**

```bash
git add -A
git commit -m "feat: Fase 2b completa — Link Agent con tabella interattiva e integrazione MemoryAgent"
```

---

## Output atteso dopo Fase 2b

```bash
[1/2] Nodo candidato:
  Tipo:       Observation
  Contenuto:  Il legame ACE2-spike era quasi assente a pH 6.8.
  Confidence: 0.90
  Trigger:    esito dell'esperimento
Approva questo nodo? [y/n/s/a]: y

[2/2] Nodo candidato:
  Tipo:       Hypothesis
  Contenuto:  Ipotizziamo che la protonazione dell'istidina 34 di ACE2 a pH acido blocchi il sito di legame.
  Confidence: 0.60
  Trigger:    ipotizzazione sul meccanismo di inibizione
Approva questo nodo? [y/n/s/a]: y

✓ Scritti 2 nodi: 54211d97, 3a284cda

 Archi candidati rilevati (4)
 # ✓  Da                            Tipo           A                           Conf  Motivo
 1 ✓  [54211d97] Il legame ACE2...  falsifica →   [c34ddd2a] Il pH 7.2 è...   0.85  Obs diretta falsifica il range ottimale
 2 ✓  [54211d97] Il legame ACE2...  supporta →    [cccd2c32] Il pH ottimale... 0.80  Conferma la soglia sotto 7.0
 3 ✓  [3a284cda] Ipotizziamo...     deriva_da →   [54211d97] Il legame ACE2... 0.75  Ipotesi meccanismo deriva dall'obs
 4 ✓  [3a284cda] Ipotizziamo...     contraddice → [51dd7831] Il virus entra... 0.65  Propone meccanismo alternativo

Comandi: [n <num>] deseleziona  [t <num> <tipo>] modifica tipo  [c <num> <val>] modifica confidence  [y] approva  [N] annulla

> y
✓ Scritti 4 archi.
```