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
        graph = agent._store.get_graph("u1")
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
