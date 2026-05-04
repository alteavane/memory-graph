import pytest

from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore


@pytest.fixture
def store(tmp_path):
    return GraphStore(str(tmp_path / "test.kuzu"))


class TestCreateNode:
    def test_returns_node_entity(self, store):
        entity = store.create_node(
            user_id="user1",
            type=NodeType.HYPOTHESIS,
            content="Il pH influenza il legame proteico",
            confidence=0.7,
            trigger="Osservazione esperimento #3",
        )
        assert entity.id is not None
        assert entity.user_id == "user1"
        assert entity.type == NodeType.HYPOTHESIS
        assert entity.is_deleted is False

    def test_creates_first_state_version_1(self, store):
        entity = store.create_node("u1", NodeType.OBSERVATION, "contenuto", 0.5, "trigger")
        history = store.get_node_history(entity.id)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].content == "contenuto"
        assert history[0].confidence == 0.5
        assert history[0].trigger == "trigger"

    def test_each_node_has_unique_id(self, store):
        e1 = store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        e2 = store.create_node("u1", NodeType.HYPOTHESIS, "B", 0.6, "t")
        assert e1.id != e2.id


class TestUpdateNode:
    def test_increments_version(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        state = store.update_node(entity.id, "v2", 0.7, "nuova evidenza")
        assert state.version == 2
        assert state.content == "v2"
        assert state.confidence == 0.7

    def test_preserves_previous_states(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        store.update_node(entity.id, "v2", 0.7, "t2")
        history = store.get_node_history(entity.id)
        assert len(history) == 2
        assert history[0].version == 1
        assert history[0].content == "v1"
        assert history[1].version == 2
        assert history[1].content == "v2"

    def test_multiple_updates_increment_correctly(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.3, "t1")
        store.update_node(entity.id, "v2", 0.5, "t2")
        state3 = store.update_node(entity.id, "v3", 0.8, "t3")
        assert state3.version == 3
        history = store.get_node_history(entity.id)
        assert [s.version for s in history] == [1, 2, 3]


class TestGetGraph:
    def test_returns_nodes_with_latest_state(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "v1", 0.5, "t1")
        store.update_node(entity.id, "v2", 0.8, "t2")
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 1
        _, state = graph["nodes"][0]
        assert state.version == 2
        assert state.content == "v2"

    def test_isolates_by_user_id(self, store):
        store.create_node("alice", NodeType.HYPOTHESIS, "alice content", 0.5, "t")
        store.create_node("bob", NodeType.OBSERVATION, "bob content", 0.6, "t")
        graph = store.get_graph("alice")
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0][0].user_id == "alice"

    def test_excludes_deleted_nodes(self, store):
        entity = store.create_node("u1", NodeType.HYPOTHESIS, "content", 0.5, "t")
        store._conn.execute(
            "MATCH (n:NodeEntity) WHERE n.id = $id SET n.is_deleted = true",
            {"id": entity.id},
        )
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 0

    def test_returns_empty_edges_when_none(self, store):
        store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        graph = store.get_graph("u1")
        assert graph["edges"] == []

    def test_multiple_nodes_returned(self, store):
        store.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        store.create_node("u1", NodeType.OBSERVATION, "B", 0.7, "t")
        graph = store.get_graph("u1")
        assert len(graph["nodes"]) == 2
