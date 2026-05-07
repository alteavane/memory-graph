# Fase 2 — Memory Agent: Piano di Implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire il Memory Agent — trasforma testo libero in nodi candidati, li filtra, rileva contraddizioni, e li propone all'utente per approvazione esplicita prima di scrivere nel grafo.

**Architecture:** Il testo passa attraverso una pipeline lineare: `extractor.py` chiama il LLM e produce `CandidateNode`, `quality.py` filtra per confidence e contenuto, `detector.py` rileva contraddizioni, e `agent.py` orchestra tutto con un loop CLI interattivo. Il Memory Agent usa un'unica connessione Kuzu condivisa tra `GraphStore` (nodi/archi) e `ProjectStore` (contesto progetto), senza modificare i componenti esistenti.

**Tech Stack:** Python 3.11+, Kuzu (embedded), pytest, Typer, Rich — nessuna dipendenza da provider LLM.

---

## Mappa dei file

### Nuovi file
| File | Responsabilità |
|---|---|
| `src/memorygraph/agent/__init__.py` | Esporta `MemoryAgent` |
| `src/memorygraph/agent/extractor.py` | Tipi condivisi + `extract()` |
| `src/memorygraph/agent/quality.py` | `filter_candidates()` |
| `src/memorygraph/agent/detector.py` | `detect()` + cosine similarity |
| `src/memorygraph/agent/agent.py` | `MemoryAgent` + loop approvazione |
| `tests/test_agent/__init__.py` | Package pytest |
| `tests/test_agent/test_extractor.py` | 5 test su extractor |
| `tests/test_agent/test_quality.py` | 3 test su quality gate |
| `tests/test_agent/test_detector.py` | 4 test su detector |
| `tests/test_agent/test_agent.py` | 7 test su MemoryAgent |

### File modificati
| File | Modifica |
|---|---|
| `cli/main.py` | Aggiunge comando `agent-extract` |

### Invarianti
- `GraphStore` e `ContextStore` non vengono modificati
- `MemoryAgent` non scrive mai senza `y` o `a` esplicito dall'utente
- `Project.full_context` accessibile solo con `agent_context=True`
- Nessun import da `anthropic`, `openai`, o qualsiasi provider LLM

---

## Task 1: Package stub + Extractor

**Files:**
- Create: `src/memorygraph/agent/__init__.py`
- Create: `src/memorygraph/agent/extractor.py`
- Create: `tests/test_agent/__init__.py`
- Create: `tests/test_agent/test_extractor.py`

- [ ] **Step 1: Crea il package stub**

```python
# src/memorygraph/agent/__init__.py
# populated in Task 7
```

```python
# tests/test_agent/__init__.py
```

- [ ] **Step 2: Scrivi i test fallenti per extractor**

```python
# tests/test_agent/test_extractor.py
from __future__ import annotations

from memorygraph.agent.extractor import (
    CandidateNode,
    ContradictionHint,
    ProposedNode,
    extract,
)
from memorygraph.graph.models import NodeType


def _make_llm(response: str):
    return lambda _prompt: response


class TestExtractTypes:
    def test_candidate_node_fields(self):
        node = CandidateNode(
            type=NodeType.HYPOTHESIS,
            content="Il pH ottimale è 7.4",
            confidence=0.7,
            trigger="esperimento #3",
        )
        assert node.type == NodeType.HYPOTHESIS
        assert node.project_id is None

    def test_proposed_node_hint_default_none(self):
        candidate = CandidateNode(NodeType.OBSERVATION, "fatto", 0.9, "diretto")
        proposed = ProposedNode(candidate=candidate)
        assert proposed.hint is None

    def test_contradiction_hint_fields(self):
        hint = ContradictionHint(existing_node_id="abc-123", reason="contraddice")
        assert hint.existing_node_id == "abc-123"


class TestExtract:
    def test_returns_candidate_nodes(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'
        )
        result = extract("testo", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.HYPOTHESIS
        assert result[0].content == "ACE2 è il recettore"
        assert result[0].confidence == 0.7

    def test_strips_markdown_backticks(self):
        llm = _make_llm(
            '```json\n{"nodes": [{"type": "Observation", "content": "pH 7.4", "confidence": 0.9, "trigger": "misura"}]}\n```'
        )
        result = extract("testo", llm)
        assert len(result) == 1
        assert result[0].type == NodeType.OBSERVATION

    def test_unknown_type_skipped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Unknown", "content": "qualcosa", "confidence": 0.5, "trigger": "t"}]}'
        )
        result = extract("testo", llm)
        assert len(result) == 0

    def test_confidence_clamped(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Conclusion", "content": "certo", "confidence": 1.5, "trigger": "t"}]}'
        )
        result = extract("testo", llm)
        assert result[0].confidence == 1.0

    def test_project_context_in_prompt(self):
        received_prompts = []
        def capturing_llm(prompt: str) -> str:
            received_prompts.append(prompt)
            return '{"nodes": []}'

        extract("testo", capturing_llm, project_context="contesto segreto del progetto")
        assert "contesto segreto del progetto" in received_prompts[0]

    def test_project_id_propagated_to_candidates(self):
        llm = _make_llm(
            '{"nodes": [{"type": "Hypothesis", "content": "H", "confidence": 0.6, "trigger": "t"}]}'
        )
        result = extract("testo", llm, project_id="proj-1")
        assert result[0].project_id == "proj-1"
```

- [ ] **Step 3: Verifica che i test falliscano**

```bash
cd /path/to/memorygraph
uv run pytest tests/test_agent/test_extractor.py -v
```
Atteso: `ModuleNotFoundError: No module named 'memorygraph.agent.extractor'`

- [ ] **Step 4: Implementa extractor.py**

```python
# src/memorygraph/agent/extractor.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Callable

from memorygraph.graph.models import NodeType

logger = logging.getLogger(__name__)

LLMCallable = Callable[[str], str]
EmbedCallable = Callable[[str], list[float]]

_NODE_TYPE_VALUES = {nt.value for nt in NodeType}

_ROLE_INSTRUCTIONS = """\
Sei un estrattore di credenze da testo scientifico.

NodeType validi: Observation, Hypothesis, Conclusion, DeadEnd, OpenQuestion, Paper, Experiment, MethodDecision

Scegli il tipo più specifico:
- Observation    → fatto empirico osservato direttamente
- Hypothesis     → ipotesi da verificare, anche se il testo usa "forse", "potrebbe"
- Conclusion     → validata, alta certezza
- DeadEnd        → fallimento, strada chiusa, falsificazione
- OpenQuestion   → domanda senza risposta ancora
- Paper          → citazione di fonte esterna, articolo, dataset
- Experiment     → descrizione di un esperimento con metodo/risultato
- MethodDecision → scelta metodologica con ragionamento

Se il testo esprime incertezza esplicita → Hypothesis o OpenQuestion.
Se descrive un fallimento → DeadEnd.
Se cita una fonte esterna → Paper.

Scala confidence:
0.9+    → fatto empirico osservato direttamente
0.6–0.9 → ipotesi con evidenza parziale
0.3–0.6 → speculazione o evidenza debole
< 0.3   → dubbio esplicito — includi solo se il contenuto è significativo"""

_OUTPUT_FORMAT = """\
Rispondi SOLO con JSON valido in questo formato:
{"nodes": [{"type": "...", "content": "...", "confidence": 0.0, "trigger": "..."}]}
Se non trovi nodi significativi, rispondi: {"nodes": []}"""


@dataclass
class CandidateNode:
    type: NodeType
    content: str
    confidence: float
    trigger: str
    project_id: str | None = None


@dataclass
class ContradictionHint:
    existing_node_id: str
    reason: str


@dataclass
class ProposedNode:
    candidate: CandidateNode
    hint: ContradictionHint | None = None


def _build_prompt(text: str, project_context: str | None) -> str:
    parts = [_ROLE_INSTRUCTIONS]
    if project_context:
        parts.append(f"Contesto del progetto:\n{project_context}")
    parts.append(f"Testo:\n{text}")
    parts.append(_OUTPUT_FORMAT)
    return "\n\n".join(parts)


def _strip_markdown(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


def extract(
    text: str,
    llm: LLMCallable,
    project_context: str | None = None,
    project_id: str | None = None,
) -> list[CandidateNode]:
    """Chiama LLM con prompt strutturato, parsifica JSON, ritorna candidati."""
    prompt = _build_prompt(text, project_context)
    raw = llm(prompt)
    cleaned = _strip_markdown(raw)

    try:
        data = json.loads(cleaned)
        nodes_raw: list[dict] = data.get("nodes", [])
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %s", raw[:200])
        return []

    candidates: list[CandidateNode] = []
    for item in nodes_raw:
        type_str = item.get("type", "")
        if type_str not in _NODE_TYPE_VALUES:
            logger.warning("Unknown node type skipped: %s", type_str)
            continue
        content = item.get("content", "")
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        trigger = item.get("trigger", "")
        candidates.append(CandidateNode(
            type=NodeType(type_str),
            content=content,
            confidence=confidence,
            trigger=trigger,
            project_id=project_id,
        ))

    return candidates
```

- [ ] **Step 5: Verifica che i test passino**

```bash
uv run pytest tests/test_agent/test_extractor.py -v
```
Atteso: tutti i test PASS.

- [ ] **Step 6: Coverage check parziale**

```bash
uv run pytest tests/test_agent/test_extractor.py --cov=src/memorygraph/agent/extractor --cov-report=term-missing
```
Atteso: coverage ≥ 90% su `extractor.py`.

- [ ] **Step 7: Commit**

```bash
git add src/memorygraph/agent/__init__.py \
        src/memorygraph/agent/extractor.py \
        tests/test_agent/__init__.py \
        tests/test_agent/test_extractor.py
git commit -m "feat: agent/extractor — CandidateNode, ContradictionHint, ProposedNode, extract()"
```

---

## Task 2: Quality Gate

**Files:**
- Create: `src/memorygraph/agent/quality.py`
- Create: `tests/test_agent/test_quality.py`

- [ ] **Step 1: Scrivi i test fallenti**

```python
# tests/test_agent/test_quality.py
from __future__ import annotations

import pytest

from memorygraph.agent.extractor import CandidateNode
from memorygraph.agent.quality import filter_candidates
from memorygraph.graph.models import NodeType


def _make(content: str = "contenuto", confidence: float = 0.7) -> CandidateNode:
    return CandidateNode(
        type=NodeType.HYPOTHESIS, content=content, confidence=confidence, trigger="t"
    )


class TestFilterCandidates:
    def test_below_threshold_removed(self):
        result = filter_candidates([_make(confidence=0.2)], min_confidence=0.3)
        assert len(result) == 0

    def test_empty_content_removed(self):
        result = filter_candidates([_make(content="   ")], min_confidence=0.3)
        assert len(result) == 0

    def test_valid_candidate_passes(self):
        result = filter_candidates([_make(confidence=0.5)], min_confidence=0.3)
        assert len(result) == 1

    def test_default_min_confidence_is_0_3(self):
        below = _make(confidence=0.29)
        above = _make(confidence=0.30)
        result = filter_candidates([below, above])
        assert len(result) == 1
        assert result[0].confidence == 0.30

    def test_empty_list_returns_empty(self):
        assert filter_candidates([]) == []
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
uv run pytest tests/test_agent/test_quality.py -v
```
Atteso: `ModuleNotFoundError: No module named 'memorygraph.agent.quality'`

- [ ] **Step 3: Implementa quality.py**

```python
# src/memorygraph/agent/quality.py
from __future__ import annotations

from memorygraph.agent.extractor import CandidateNode


def filter_candidates(
    candidates: list[CandidateNode],
    min_confidence: float = 0.3,
) -> list[CandidateNode]:
    """Filtra i candidati che non soddisfano i criteri minimi di quality."""
    return [
        c for c in candidates
        if c.confidence >= min_confidence and c.content.strip()
    ]
```

- [ ] **Step 4: Verifica che i test passino**

```bash
uv run pytest tests/test_agent/test_quality.py -v
```
Atteso: tutti i test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/agent/quality.py tests/test_agent/test_quality.py
git commit -m "feat: agent/quality — filter_candidates()"
```

---

## Task 3: Contradiction Detector

**Files:**
- Create: `src/memorygraph/agent/detector.py`
- Create: `tests/test_agent/test_detector.py`

- [ ] **Step 1: Scrivi i test fallenti**

```python
# tests/test_agent/test_detector.py
from __future__ import annotations

from datetime import datetime

from memorygraph.agent.detector import detect
from memorygraph.agent.extractor import CandidateNode
from memorygraph.graph.models import NodeState, NodeType


def _make_candidate(project_id: str | None = "proj-1") -> CandidateNode:
    return CandidateNode(
        type=NodeType.HYPOTHESIS,
        content="ACE2 è il recettore principale",
        confidence=0.8,
        trigger="paper",
        project_id=project_id,
    )


def _make_state(node_id: str = "node-existing", content: str = "ACE2 non è il recettore") -> NodeState:
    return NodeState(
        id="state-1",
        node_id=node_id,
        version=1,
        content=content,
        confidence=0.8,
        trigger="t",
        created_at=datetime(2026, 1, 1),
    )


class TestDetect:
    def test_no_project_id_returns_none(self):
        llm = lambda p: '{"contradiction": true, "node_id": "x", "reason": "r"}'
        result = detect(_make_candidate(project_id=None), [_make_state()], llm)
        assert result is None

    def test_empty_project_nodes_returns_none(self):
        llm = lambda p: '{"contradiction": true, "node_id": "x", "reason": "r"}'
        result = detect(_make_candidate(), [], llm)
        assert result is None

    def test_llm_detects_contradiction(self):
        llm = lambda p: '{"contradiction": true, "node_id": "node-existing", "reason": "Contraddice diretta"}'
        result = detect(_make_candidate(), [_make_state()], llm)
        assert result is not None
        assert result.existing_node_id == "node-existing"
        assert result.reason == "Contraddice diretta"

    def test_llm_no_contradiction_returns_none(self):
        llm = lambda p: '{"contradiction": false, "node_id": null, "reason": null}'
        result = detect(_make_candidate(), [_make_state()], llm)
        assert result is None

    def test_embed_top_k_llm_called_only_on_top_k(self):
        prompts_received = []

        def recording_llm(prompt: str) -> str:
            prompts_received.append(prompt)
            return '{"contradiction": false, "node_id": null, "reason": null}'

        # 3 nodes, top_k=2 — LLM prompt should contain at most 2 node ids
        states = [
            _make_state(node_id="n1", content="testo 1"),
            _make_state(node_id="n2", content="testo 2"),
            _make_state(node_id="n3", content="testo 3"),
        ]
        embed = lambda t: [1.0, 0.0]   # same vector for all — ties resolved by list order

        detect(_make_candidate(), states, recording_llm, embed=embed, top_k=2)

        assert len(prompts_received) == 1
        # Only 2 of the 3 node ids should appear in the prompt
        count = sum(1 for s in states if s.node_id in prompts_received[0])
        assert count == 2
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
uv run pytest tests/test_agent/test_detector.py -v
```
Atteso: `ModuleNotFoundError: No module named 'memorygraph.agent.detector'`

- [ ] **Step 3: Implementa detector.py**

```python
# src/memorygraph/agent/detector.py
from __future__ import annotations

import json
import logging
import math

from memorygraph.agent.extractor import (
    CandidateNode,
    ContradictionHint,
    EmbedCallable,
    LLMCallable,
)
from memorygraph.graph.models import NodeState

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _format_nodes(nodes: list[NodeState]) -> str:
    return "\n".join(
        f"- id: {n.node_id} | {n.content} (confidence: {n.confidence:.2f})"
        for n in nodes
    )


def _call_llm(
    candidate: CandidateNode,
    nodes: list[NodeState],
    llm: LLMCallable,
) -> ContradictionHint | None:
    prompt = (
        "Sei un rilevatore di contraddizioni in un grafo di conoscenza.\n\n"
        f"Candidato:\n"
        f"  Tipo: {candidate.type.value}\n"
        f"  Contenuto: {candidate.content}\n"
        f"  Confidence: {candidate.confidence:.2f}\n\n"
        f"Nodi esistenti nel progetto:\n"
        f"{_format_nodes(nodes)}\n\n"
        "Il candidato contraddice uno dei nodi esistenti?\n"
        'Rispondi SOLO con JSON valido:\n'
        '{"contradiction": true/false, "node_id": "<id del nodo o null>", "reason": "<spiegazione o null>"}'
    )
    raw = llm(prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.split("\n") if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Detector LLM invalid JSON: %s", raw[:200])
        return None

    if data.get("contradiction") and data.get("node_id"):
        return ContradictionHint(
            existing_node_id=data["node_id"],
            reason=data.get("reason") or "",
        )
    return None


def detect(
    candidate: CandidateNode,
    project_nodes: list[NodeState],
    llm: LLMCallable,
    embed: EmbedCallable | None = None,
    top_k: int = 5,
) -> ContradictionHint | None:
    """Rileva se il candidato contraddice nodi esistenti nel progetto."""
    if candidate.project_id is None or not project_nodes:
        return None

    if embed is None:
        return _call_llm(candidate, project_nodes, llm)

    candidate_vec = embed(candidate.content)
    scored: list[tuple[float, NodeState]] = []
    for node in project_nodes:
        node_vec = embed(node.content)
        sim = _cosine_similarity(candidate_vec, node_vec)
        scored.append((sim, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_nodes = [node for _, node in scored[:top_k]]
    return _call_llm(candidate, top_nodes, llm)
```

- [ ] **Step 4: Verifica che i test passino**

```bash
uv run pytest tests/test_agent/test_detector.py -v
```
Atteso: tutti i test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/agent/detector.py tests/test_agent/test_detector.py
git commit -m "feat: agent/detector — detect() con LLM + cosine similarity opzionale"
```

---

## Task 4: MemoryAgent — extract() e propose()

**Files:**
- Create: `src/memorygraph/agent/agent.py`
- Create: `tests/test_agent/test_agent.py` (parziale)

Nota implementativa: `MemoryAgent` crea UN solo `GraphStore` (che apre il DB Kuzu), poi chiama `init_context_schema` sulla stessa connessione per inizializzare le tabelle Project/BELONGS_TO. Questo evita di aprire due istanze DB sulla stessa path. `ProjectStore` riceve la connessione esistente.

- [ ] **Step 1: Scrivi i test fallenti per extract() e propose()**

```python
# tests/test_agent/test_agent.py
from __future__ import annotations

import pytest

from memorygraph.agent.agent import MemoryAgent
from memorygraph.agent.extractor import CandidateNode, ProposedNode
from memorygraph.graph.models import EdgeType, NodeType


def _extractor_llm(prompt: str) -> str:
    """Mock LLM che ritorna un nodo Hypothesis valido."""
    return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'


def _no_contradiction_llm(prompt: str) -> str:
    """Mock LLM: estrae un nodo, non rileva contraddizioni."""
    if "NodeType validi" in prompt:
        return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.7, "trigger": "paper Zhang"}]}'
    return '{"contradiction": false, "node_id": null, "reason": null}'


@pytest.fixture
def agent(tmp_path):
    return MemoryAgent(str(tmp_path / "test.kuzu"), llm=_extractor_llm)


class TestMemoryAgentExtract:
    def test_extract_returns_candidates(self, agent):
        result = agent.extract("Il pH ottimale per la reazione è 7.4")
        assert len(result) == 1
        assert isinstance(result[0], CandidateNode)
        assert result[0].type == NodeType.HYPOTHESIS

    def test_extract_without_project_id(self, agent):
        result = agent.extract("testo senza progetto")
        assert result[0].project_id is None

    def test_extract_with_project_id_propagated(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_extractor_llm)
        result = agent.extract("testo", project_id="proj-999")
        assert result[0].project_id == "proj-999"


class TestMemoryAgentPropose:
    def test_propose_returns_proposed_nodes(self, tmp_path):
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=_no_contradiction_llm)
        result = agent.propose("Il pH ottimale è 7.4")
        assert len(result) == 1
        assert isinstance(result[0], ProposedNode)
        assert result[0].hint is None

    def test_propose_filters_below_threshold(self, tmp_path):
        low_conf_llm = lambda p: '{"nodes": [{"type": "Hypothesis", "content": "speculazione", "confidence": 0.1, "trigger": "t"}]}'
        agent = MemoryAgent(str(tmp_path / "test.kuzu"), llm=low_conf_llm, min_confidence=0.3)
        result = agent.propose("testo")
        assert len(result) == 0
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
uv run pytest tests/test_agent/test_agent.py::TestMemoryAgentExtract \
              tests/test_agent/test_agent.py::TestMemoryAgentPropose -v
```
Atteso: `ModuleNotFoundError: No module named 'memorygraph.agent.agent'`

- [ ] **Step 3: Implementa agent.py con constructor + extract() + propose()**

```python
# src/memorygraph/agent/agent.py
from __future__ import annotations

from typing import Callable

from rich.console import Console

from memorygraph.agent import extractor as _extractor
from memorygraph.agent import quality as _quality
from memorygraph.agent import detector as _detector
from memorygraph.agent.extractor import (
    CandidateNode,
    EmbedCallable,
    LLMCallable,
    ProposedNode,
)
from memorygraph.context.project import ProjectStore
from memorygraph.context.schema import init_context_schema
from memorygraph.graph.models import EdgeType, NodeState
from memorygraph.graph.store import GraphStore

console = Console()


class MemoryAgent:
    """Memory Agent: estrae nodi candidati dal testo e li propone per approvazione."""

    def __init__(
        self,
        db_path: str,
        llm: LLMCallable,
        embed: EmbedCallable | None = None,
        min_confidence: float = 0.3,
        _input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._store = GraphStore(db_path)
        init_context_schema(self._store._conn)
        self._project_store = ProjectStore(self._store._conn)
        self._llm = llm
        self._embed = embed
        self._min_confidence = min_confidence
        self._input_fn = _input_fn or input

    def _load_project_nodes(self, project_id: str) -> list[NodeState]:
        result = self._store._conn.execute(
            """
            MATCH (n:NodeEntity)-[:BELONGS_TO]->(p:Project)
            WHERE p.id = $pid AND n.is_deleted = false
            MATCH (n)-[:HAS_STATE]->(s:NodeState)
            RETURN n.id, s.id, s.version, s.content, s.confidence, s.trigger, s.created_at
            ORDER BY n.id ASC, s.version DESC
            """,
            {"pid": project_id},
        )
        seen: set[str] = set()
        states: list[NodeState] = []
        while result.has_next():
            row = result.get_next()
            node_id = row[0]
            if node_id not in seen:
                seen.add(node_id)
                states.append(NodeState(
                    id=row[1], node_id=node_id, version=row[2],
                    content=row[3], confidence=row[4], trigger=row[5], created_at=row[6],
                ))
        return states

    def extract(self, text: str, project_id: str | None = None) -> list[CandidateNode]:
        """Chiama LLM → parsifica JSON → ritorna candidati non filtrati."""
        project_context = None
        if project_id:
            project = self._project_store.get_project(project_id, agent_context=True)
            if project:
                project_context = project.full_context
        return _extractor.extract(text, self._llm, project_context=project_context, project_id=project_id)

    def propose(self, text: str, project_id: str | None = None) -> list[ProposedNode]:
        """extract → quality gate → contradiction detection → lista ProposedNode."""
        candidates = self.extract(text, project_id)
        filtered = _quality.filter_candidates(candidates, self._min_confidence)

        project_nodes: list[NodeState] = []
        if project_id:
            project_nodes = self._load_project_nodes(project_id)

        proposals: list[ProposedNode] = []
        for candidate in filtered:
            hint = _detector.detect(candidate, project_nodes, self._llm, self._embed)
            proposals.append(ProposedNode(candidate=candidate, hint=hint))

        return proposals

    def run(
        self,
        text: str,
        project_id: str | None = None,
        user_id: str = "",
    ) -> list[str]:
        """Esegue propose + loop di approvazione CLI → scrive nodi approvati → ritorna node_id[]."""
        raise NotImplementedError("Implementato nel Task 5")
```

- [ ] **Step 4: Verifica che i test passino**

```bash
uv run pytest tests/test_agent/test_agent.py::TestMemoryAgentExtract \
              tests/test_agent/test_agent.py::TestMemoryAgentPropose -v
```
Atteso: tutti i test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memorygraph/agent/agent.py tests/test_agent/test_agent.py
git commit -m "feat: MemoryAgent.extract() e propose() — pipeline completa fino al loop"
```

---

## Task 5: MemoryAgent.run() — loop di approvazione CLI

**Files:**
- Modify: `src/memorygraph/agent/agent.py` (sostituisce il `raise NotImplementedError`)
- Modify: `tests/test_agent/test_agent.py` (aggiunge classi di test)

- [ ] **Step 1: Aggiungi i test fallenti per run()**

Aggiungi queste classi in fondo a `tests/test_agent/test_agent.py`:

```python
class TestMemoryAgentRunApproval:
    def test_run_y_writes_node(self, tmp_path):
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=_no_contradiction_llm,
            _input_fn=lambda p: "y",
        )
        ids = agent.run("Il pH ottimale è 7.4", user_id="u1")
        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        assert len(graph["nodes"]) == 1

    def test_run_n_does_not_write(self, tmp_path):
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=_no_contradiction_llm,
            _input_fn=lambda p: "n",
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 0
        graph = agent._store.get_graph("u1")
        assert len(graph["nodes"]) == 0

    def test_run_s_skips_remaining(self, tmp_path):
        multi_llm = lambda p: (
            '{"nodes": ['
            '{"type": "Hypothesis", "content": "H1", "confidence": 0.7, "trigger": "t"},'
            '{"type": "Observation", "content": "O1", "confidence": 0.9, "trigger": "t"}'
            ']}'
            if "NodeType validi" in p else
            '{"contradiction": false, "node_id": null, "reason": null}'
        )
        responses = iter(["s"])
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=multi_llm,
            _input_fn=lambda p: next(responses),
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 0

    def test_run_a_approves_all_remaining(self, tmp_path):
        multi_llm = lambda p: (
            '{"nodes": ['
            '{"type": "Hypothesis", "content": "H1", "confidence": 0.7, "trigger": "t"},'
            '{"type": "Observation", "content": "O1", "confidence": 0.9, "trigger": "t"}'
            ']}'
            if "NodeType validi" in p else
            '{"contradiction": false, "node_id": null, "reason": null}'
        )
        responses = iter(["a"])
        agent = MemoryAgent(
            str(tmp_path / "test.kuzu"),
            llm=multi_llm,
            _input_fn=lambda p: next(responses),
        )
        ids = agent.run("testo", user_id="u1")
        assert len(ids) == 2


class TestMemoryAgentContradiction:
    def test_contradiction_hint_y_creates_edge(self, tmp_path):
        db_path = str(tmp_path / "test.kuzu")

        # Crea l'agente prima (inizializza schema completo)
        agent = MemoryAgent(db_path, llm=lambda p: '{"nodes": []}', _input_fn=lambda p: "y")

        # Setup: crea project e nodo esistente via store interno
        project = agent._project_store.create_project(
            user_id="u1", title="Test", objective="obj",
            summary="summary", full_context="context",
        )
        existing = agent._store.create_node(
            "u1", NodeType.HYPOTHESIS, "ACE2 non è il recettore primario", 0.8, "t"
        )
        agent._store._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": existing.id, "pid": project.id},
        )

        # LLM smart: estrae un nodo nella prima chiamata, rileva contraddizione nella seconda
        def smart_llm(prompt: str) -> str:
            if "NodeType validi" in prompt:
                return '{"nodes": [{"type": "Hypothesis", "content": "ACE2 è il recettore", "confidence": 0.8, "trigger": "paper"}]}'
            return f'{{"contradiction": true, "node_id": "{existing.id}", "reason": "Contraddice diretta"}}'

        agent._llm = smart_llm
        responses = iter(["y", "y"])  # primo y = approva nodo, secondo y = crea arco CONTRADDICE
        agent._input_fn = lambda p: next(responses)

        ids = agent.run("testo", project_id=project.id, user_id="u1")

        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        edges = [e for e in graph["edges"] if e.type == EdgeType.CONTRADDICE]
        assert len(edges) == 1
        assert edges[0].from_node == ids[0]
        assert edges[0].to_node == existing.id

    def test_contradiction_hint_n_no_edge(self, tmp_path):
        db_path = str(tmp_path / "test.kuzu")
        agent = MemoryAgent(db_path, llm=lambda p: '{"nodes": []}', _input_fn=lambda p: "y")

        project = agent._project_store.create_project(
            user_id="u1", title="T", objective="o", summary="s", full_context="fc",
        )
        existing = agent._store.create_node("u1", NodeType.HYPOTHESIS, "tesi contraria", 0.8, "t")
        agent._store._conn.execute(
            "MATCH (n:NodeEntity), (p:Project) WHERE n.id = $nid AND p.id = $pid "
            "CREATE (n)-[:BELONGS_TO]->(p)",
            {"nid": existing.id, "pid": project.id},
        )

        def smart_llm(prompt: str) -> str:
            if "NodeType validi" in prompt:
                return '{"nodes": [{"type": "Hypothesis", "content": "nuova tesi", "confidence": 0.8, "trigger": "t"}]}'
            return f'{{"contradiction": true, "node_id": "{existing.id}", "reason": "contraddice"}}'

        agent._llm = smart_llm
        responses = iter(["y", "n"])  # approva nodo, rifiuta arco CONTRADDICE
        agent._input_fn = lambda p: next(responses)

        ids = agent.run("testo", project_id=project.id, user_id="u1")
        assert len(ids) == 1
        graph = agent._store.get_graph("u1")
        edges = [e for e in graph["edges"] if e.type == EdgeType.CONTRADDICE]
        assert len(edges) == 0
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
uv run pytest tests/test_agent/test_agent.py::TestMemoryAgentRunApproval \
              tests/test_agent/test_agent.py::TestMemoryAgentContradiction -v
```
Atteso: `NotImplementedError` su `run()`.

- [ ] **Step 3: Implementa run() — sostituisci il `raise NotImplementedError` in agent.py**

Sostituisci il metodo `run()` con questa implementazione:

```python
    def _write_node(self, user_id: str, candidate: CandidateNode, project_id: str | None) -> str:
        node = self._store.create_node(
            user_id=user_id,
            type=candidate.type,
            content=candidate.content,
            confidence=candidate.confidence,
            trigger=candidate.trigger,
        )
        if project_id:
            self._store._conn.execute(
                "MATCH (n:NodeEntity), (p:Project) "
                "WHERE n.id = $nid AND p.id = $pid "
                "CREATE (n)-[:BELONGS_TO]->(p)",
                {"nid": node.id, "pid": project_id},
            )
        return node.id

    def run(
        self,
        text: str,
        project_id: str | None = None,
        user_id: str = "",
    ) -> list[str]:
        """Esegue propose + loop di approvazione CLI → scrive nodi approvati → ritorna node_id[]."""
        proposals = self.propose(text, project_id)
        approved: list[str] = []
        total = len(proposals)

        for i, proposed in enumerate(proposals):
            c = proposed.candidate
            console.print(f"\n[bold cyan][{i + 1}/{total}] Nodo candidato:[/bold cyan]")
            console.print(f"  Tipo:       {c.type.value}")
            console.print(f"  Contenuto:  {c.content}")
            console.print(f"  Confidence: {c.confidence:.2f}")
            console.print(f"  Trigger:    {c.trigger}")
            if proposed.hint:
                console.print(
                    f"  [yellow]⚠ Possibile contraddizione con nodo "
                    f"{proposed.hint.existing_node_id[:8]}:[/yellow]"
                )
                console.print(f'    "{proposed.hint.reason}" (rilevata dall\'agente)')

            response = self._input_fn("Approva questo nodo? [y/n/s/a]: ").strip().lower()

            if response == "n":
                continue
            elif response == "s":
                break
            elif response in ("y", "a"):
                node_id = self._write_node(user_id, c, project_id)
                approved.append(node_id)

                if proposed.hint:
                    edge_resp = self._input_fn("Creare arco CONTRADDICE? [y/n]: ").strip().lower()
                    if edge_resp == "y":
                        self._store.create_edge(
                            node_id,
                            proposed.hint.existing_node_id,
                            EdgeType.CONTRADDICE,
                            1.0,
                        )

                if response == "a":
                    for remaining in proposals[i + 1:]:
                        rid = self._write_node(user_id, remaining.candidate, project_id)
                        approved.append(rid)
                    break

        return approved
```

Il metodo `_write_node` va aggiunto come privato prima di `run()` nella classe. Rimuovi il metodo `run()` con `raise NotImplementedError` e sostituiscilo con questo blocco.

- [ ] **Step 4: Verifica tutti i test dell'agent**

```bash
uv run pytest tests/test_agent/test_agent.py -v
```
Atteso: tutti i test PASS.

- [ ] **Step 5: Coverage check completo del modulo agent**

```bash
uv run pytest tests/test_agent/ --cov=src/memorygraph/agent --cov-report=term-missing
```
Atteso: coverage ≥ 80%.

- [ ] **Step 6: Test suite completa — nessuna regressione**

```bash
uv run pytest tests/ -v
```
Atteso: tutti i test PASS (inclusi test_graph e test_context esistenti).

- [ ] **Step 7: Commit**

```bash
git add src/memorygraph/agent/agent.py tests/test_agent/test_agent.py
git commit -m "feat: MemoryAgent.run() — loop approvazione y/n/s/a + arco CONTRADDICE"
```

---

## Task 6: CLI command `agent-extract`

**Files:**
- Modify: `cli/main.py`

Nota: il comando CLI richiede un LLM reale in produzione. Per il MVP includiamo una factory `_make_demo_llm()` che usa regole semplici. Gli utenti sostituiranno questa funzione con il proprio provider. Il parametro `--stdin` legge il testo da stdin invece di `--text`.

- [ ] **Step 1: Leggi le ultime righe di cli/main.py per sapere dove inserire il nuovo comando**

```bash
tail -30 cli/main.py
```

- [ ] **Step 2: Aggiungi il comando `agent-extract` in fondo a cli/main.py**

Aggiungi in fondo al file (dopo tutti i comandi esistenti) il seguente blocco. Le due import vanno invece inserite nelle import in cima al file, dopo le import esistenti:

```python
# aggiungere alle import in cima, dopo le import esistenti
from memorygraph.agent.agent import MemoryAgent
from memorygraph.agent.extractor import LLMCallable
```

```python
# aggiungere in fondo al file
def _make_demo_llm() -> LLMCallable:
    """LLM demo — ritorna un nodo fisso. Sostituire con un LLM reale in produzione."""
    def demo_llm(prompt: str) -> str:
        if "NodeType validi" in prompt:
            return (
                '{"nodes": [{"type": "Observation", '
                '"content": "Testo inserito tramite CLI", '
                '"confidence": 0.5, '
                '"trigger": "Inserito via agent-extract"}]}'
            )
        return '{"contradiction": false, "node_id": null, "reason": null}'
    return demo_llm


@app.command()
def agent_extract(
    user_id: str = typer.Option(..., "--user-id", help="ID utente"),
    text: str | None = typer.Option(None, "--text", help="Testo da analizzare"),
    project_id: str | None = typer.Option(None, "--project-id", help="ID progetto (opzionale)"),
    stdin: bool = typer.Option(False, "--stdin", help="Legge il testo da stdin"),
) -> None:
    """Analizza testo libero e propone nodi interattivamente."""
    import sys as _sys
    from memorygraph.config import DB_PATH

    if stdin:
        input_text = _sys.stdin.read().strip()
    elif text:
        input_text = text
    else:
        console.print("[red]Errore:[/red] Fornire --text oppure --stdin.")
        raise typer.Exit(1)

    agent = MemoryAgent(db_path=DB_PATH, llm=_make_demo_llm())
    ids = agent.run(input_text, project_id=project_id, user_id=user_id)
    if ids:
        console.print(f"\n[green]✓[/green] Scritti {len(ids)} nodi: {', '.join(i[:8] for i in ids)}")
    else:
        console.print("\n[yellow]Nessun nodo approvato.[/yellow]")
```

- [ ] **Step 3: Verifica che il comando sia registrato**

```bash
uv run python cli/main.py --help
```
Atteso: `agent-extract` appare nella lista dei comandi.

- [ ] **Step 4: Test smoke del comando**

```bash
uv run python cli/main.py agent-extract --user-id test-user --text "Il pH ottimale è 7.4"
```
Atteso: il comando stampa il nodo candidato e attende input `[y/n/s/a]:`. Premi `n` per non scrivere nulla.

- [ ] **Step 5: Commit**

```bash
git add cli/main.py
git commit -m "feat: CLI agent-extract — loop interattivo di approvazione nodi"
```

---

## Task 7: __init__.py finale

**Files:**
- Modify: `src/memorygraph/agent/__init__.py`

- [ ] **Step 1: Popola __init__.py**

```python
# src/memorygraph/agent/__init__.py
"""Memory Agent — estrazione di nodi candidati da testo con approvazione esplicita."""

from memorygraph.agent.agent import MemoryAgent

__all__ = ["MemoryAgent"]
```

- [ ] **Step 2: Verifica che l'import funzioni**

```bash
uv run python -c "from memorygraph.agent import MemoryAgent; print('OK')"
```
Atteso: `OK`

- [ ] **Step 3: Test suite completa finale**

```bash
uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing -v
```
Atteso: tutti i test PASS, coverage ≥ 80% globale.

- [ ] **Step 4: Commit**

```bash
git add src/memorygraph/agent/__init__.py
git commit -m "feat: agent/__init__.py — esporta MemoryAgent"
```

---

## Post-implementation checklist

- [ ] `uv run pytest tests/ --cov=src/memorygraph --cov-report=term-missing` — coverage ≥ 80%
- [ ] Nessun import da `anthropic`, `openai`, o altri provider LLM
- [ ] `MemoryAgent` non scrive mai senza risposta esplicita `y` o `a`
- [ ] `Project.full_context` accessibile solo con `agent_context=True` (già garantito da `ProjectStore`)
- [ ] Aggiornare `CLAUDE.md` → roadmap: Fase 2 da `⏳` a `✅`

---

## Note per l'implementatore

**Connessione DB unica:** `MemoryAgent.__init__` crea `GraphStore(db_path)`, poi chiama `init_context_schema(self._store._conn)` per aggiungere le tabelle Context senza aprire un secondo database. `ProjectStore` riceve la stessa connessione. Questo evita problemi con Kuzu embedded su path identica.

**Discriminare extractor vs detector nel mock LLM:** Il prompt dell'extractor contiene sempre la stringa `"NodeType validi"`. Il prompt del detector non la contiene mai. Usa questo nei test per far rispondere il mock LLM in modo diverso alle due chiamate.

**`_input_fn` convention:** Il parametro `_input_fn` (underscore prefix) è solo per i test. In produzione `run()` usa il `input()` builtin. Nei test: `lambda p: "y"` per approvare tutto, `iter(["y", "n"])` per risposte sequenziali.

**Batch-approve con ContradictionHint:** quando l'utente risponde `a`, la risposta bulk approva tutti i nodi rimanenti **senza chiedere** per gli archi CONTRADDICE eventuali. Solo il nodo corrente (che ha ricevuto `a`) può generare la domanda sull'arco, se ha un hint.
