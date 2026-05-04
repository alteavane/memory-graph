from datetime import datetime, timezone

import pytest

from memorygraph.graph.models import Edge, EdgeType, NodeEntity, NodeState, NodeType


def test_node_type_values():
    assert NodeType.HYPOTHESIS.value == "Hypothesis"
    assert NodeType.DEAD_END.value == "DeadEnd"
    assert NodeType.METHOD_DECISION.value == "MethodDecision"


def test_edge_type_values():
    assert EdgeType.SUPPORTA.value == "supporta"
    assert EdgeType.APRE_DOMANDA.value == "apre_domanda"


def test_node_entity_defaults():
    entity = NodeEntity(
        id="abc",
        user_id="user1",
        type=NodeType.HYPOTHESIS,
        created_at=datetime.now(timezone.utc),
    )
    assert entity.is_deleted is False


def test_node_state_fields():
    state = NodeState(
        id="s1",
        node_id="abc",
        version=1,
        content="test content",
        confidence=0.7,
        trigger="test trigger",
        created_at=datetime.now(timezone.utc),
    )
    assert state.version == 1
    assert state.confidence == 0.7


def test_edge_defaults():
    edge = Edge(
        edge_id="e1",
        from_node="n1",
        to_node="n2",
        type=EdgeType.SUPPORTA,
        confidence=0.9,
    )
    assert edge.invalidated_at is None


def test_node_type_from_str():
    t = NodeType("Hypothesis")
    assert t == NodeType.HYPOTHESIS


def test_edge_type_from_str():
    t = EdgeType("supporta")
    assert t == EdgeType.SUPPORTA
