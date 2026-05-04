from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cli.main import app
from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore

runner = CliRunner()


@pytest.fixture
def store(tmp_path):
    return GraphStore(str(tmp_path / "test.kuzu"))


@pytest.fixture
def patched(store):
    with patch("cli.main._get_store", return_value=store):
        yield store


class TestUpdateOptionalContent:
    def test_update_without_content_reuses_last_state(self, patched):
        entity = patched.create_node("u1", NodeType.HYPOTHESIS, "contenuto originale", 0.7, "inizio")
        result = runner.invoke(app, [
            "update",
            "--node-id", entity.id,
            "--confidence", "0.9",
            "--trigger", "nuova evidenza",
        ])
        assert result.exit_code == 0, result.output
        history = patched.get_node_history(entity.id)
        assert len(history) == 2
        assert history[1].content == "contenuto originale"
        assert history[1].confidence == 0.9

    def test_update_with_content_uses_new_content(self, patched):
        entity = patched.create_node("u1", NodeType.HYPOTHESIS, "originale", 0.7, "inizio")
        result = runner.invoke(app, [
            "update",
            "--node-id", entity.id,
            "--content", "nuovo contenuto",
            "--confidence", "0.5",
            "--trigger", "cambio",
        ])
        assert result.exit_code == 0, result.output
        history = patched.get_node_history(entity.id)
        assert history[1].content == "nuovo contenuto"
