# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from memorygraph.llm.providers import make_llm


class TestMakeLlm:
    def test_demo_when_no_keys(self):
        env = {k: None for k in ("MEMORYGRAPH_LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
        with patch.dict(os.environ, {}, clear=False):
            for k in env:
                os.environ.pop(k, None)
            llm = make_llm()
        result = llm("NodeType validi: test")
        assert "nodes" in result

    def test_explicit_anthropic_raises_without_package(self):
        with patch.dict(os.environ, {"MEMORYGRAPH_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test"}):
            with patch.dict("sys.modules", {"anthropic": None}):
                with pytest.raises(RuntimeError, match="anthropic non installato"):
                    make_llm()

    def test_explicit_openai_raises_without_package(self):
        with patch.dict(os.environ, {"MEMORYGRAPH_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
            with patch.dict("sys.modules", {"openai": None}):
                with pytest.raises(RuntimeError, match="openai non installato"):
                    make_llm()

    def test_autodetect_anthropic_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=False):
            os.environ.pop("MEMORYGRAPH_LLM_PROVIDER", None)
            os.environ.pop("OPENAI_API_KEY", None)
            with patch("memorygraph.llm.providers._make_anthropic_llm") as mock:
                mock.return_value = lambda p: "{}"
                make_llm()
                mock.assert_called_once()

    def test_autodetect_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=False):
            os.environ.pop("MEMORYGRAPH_LLM_PROVIDER", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with patch("memorygraph.llm.providers._make_openai_llm") as mock:
                mock.return_value = lambda p: "{}"
                make_llm()
                mock.assert_called_once()

    def test_explicit_provider_takes_priority_over_autodetect(self):
        with patch.dict(os.environ, {
            "MEMORYGRAPH_LLM_PROVIDER": "openai",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_API_KEY": "sk-openai-test",
        }):
            with patch("memorygraph.llm.providers._make_openai_llm") as mock_oai:
                with patch("memorygraph.llm.providers._make_anthropic_llm") as mock_ant:
                    mock_oai.return_value = lambda p: "{}"
                    make_llm()
                    mock_oai.assert_called_once()
                    mock_ant.assert_not_called()
