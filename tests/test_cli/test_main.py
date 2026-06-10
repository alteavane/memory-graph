# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
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
        entity = patched.create_node("u1", NodeType.HYPOTHESIS, "original content", 0.7, "start")
        result = runner.invoke(app, [
            "update",
            "--node-id", entity.id,
            "--confidence", "0.9",
            "--trigger", "new evidence",
        ])
        assert result.exit_code == 0, result.output
        history = patched.get_node_history(entity.id)
        assert len(history) == 2
        assert history[1].content == "original content"
        assert history[1].confidence == 0.9

    def test_update_with_content_uses_new_content(self, patched):
        entity = patched.create_node("u1", NodeType.HYPOTHESIS, "original", 0.7, "start")
        result = runner.invoke(app, [
            "update",
            "--node-id", entity.id,
            "--content", "new content",
            "--confidence", "0.5",
            "--trigger", "change",
        ])
        assert result.exit_code == 0, result.output
        history = patched.get_node_history(entity.id)
        assert history[1].content == "new content"


class TestLinkCommand:
    def test_link_creates_edge(self, patched):
        n1 = patched.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = patched.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        result = runner.invoke(app, [
            "link",
            "--from", n1.id,
            "--to", n2.id,
            "--type", "supports",
            "--confidence", "0.8",
        ])
        assert result.exit_code == 0, result.output
        graph = patched.get_graph("u1")
        assert len(graph["edges"]) == 1
        assert graph["edges"][0].type == EdgeType.SUPPORTS

    def test_link_output_shows_edge_id(self, patched):
        n1 = patched.create_node("u1", NodeType.HYPOTHESIS, "A", 0.5, "t")
        n2 = patched.create_node("u1", NodeType.OBSERVATION, "B", 0.8, "t")
        result = runner.invoke(app, [
            "link",
            "--from", n1.id,
            "--to", n2.id,
            "--type", "contradicts",
            "--confidence", "0.6",
        ])
        assert result.exit_code == 0, result.output
        assert "Edge created" in result.output
