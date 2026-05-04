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
