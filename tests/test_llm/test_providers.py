# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
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
        result = llm("Valid NodeTypes: test")
        assert "nodes" in result

    def test_explicit_anthropic_raises_without_package(self):
        with patch.dict(os.environ, {"MEMORYGRAPH_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test"}):
            with patch.dict("sys.modules", {"anthropic": None}):
                with pytest.raises(RuntimeError, match="anthropic is not installed"):
                    make_llm()

    def test_explicit_openai_raises_without_package(self):
        with patch.dict(os.environ, {"MEMORYGRAPH_LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"}):
            with patch.dict("sys.modules", {"openai": None}):
                with pytest.raises(RuntimeError, match="openai is not installed"):
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

    def test_explicit_demo_provider(self):
        """MEMORYGRAPH_LLM_PROVIDER=demo selects the replay provider even when keys are present."""
        with patch.dict(os.environ, {
            "MEMORYGRAPH_LLM_PROVIDER": "demo",
            "OPENAI_API_KEY": "sk-openai-test",
        }):
            llm = make_llm()
        out = json.loads(llm(_EXTRACT_PROMPT.replace("{text}", "Lan et al. 2020: high affinity")))
        assert out["nodes"][0]["type"] == "Observation"


# Minimal prompts that reproduce the markers used by the demo provider's router.
_EXTRACT_PROMPT = "You are a belief extractor. Valid NodeTypes: ...\nText:\n{text}"
_DETECT_PROMPT = (
    "You are a contradiction detector in a knowledge graph.\n"
    "Candidate:\n  Content: Protonation of ACE2 histidine 34 reduces binding\n\n"
    "Existing nodes in the project:\n"
    "- id: 11111111-1111-1111-1111-111111111111 | RBD binds ACE2 with 10-20x higher affinity (confidence: 0.90)\n"
)
_LINK_PROMPT = (
    "You are an analyst of scientific knowledge graphs.\n"
    "Newly added nodes:\n"
    '[id: 22222222-2222-2222-2222-222222222222] "Protonation of ACE2 histidine 34 ..."\n\n'
    "Existing nodes in the graph:\n"
    '[id: 33333333-3333-3333-3333-333333333333] (OpenQuestion, conf 0.55) "Does this mechanism apply to all variants?"\n'
)


class TestDemoLlm:
    def _demo(self):
        from memorygraph.llm.providers import _make_demo_llm
        return _make_demo_llm()

    def test_extract_known_text(self):
        out = json.loads(self._demo()(_EXTRACT_PROMPT.replace("{text}", "Lan et al. 2020")))
        assert out["nodes"][0]["content"].startswith("The spike RBD")

    def test_extract_unknown_text_empty(self):
        out = json.loads(self._demo()(_EXTRACT_PROMPT.replace("{text}", "something unknown")))
        assert out["nodes"] == []

    def test_detect_resolves_existing_id_from_prompt(self):
        out = json.loads(self._demo()(_DETECT_PROMPT))
        assert out["contradiction"] is True
        assert out["node_id"] == "11111111-1111-1111-1111-111111111111"

    def test_link_opens_question_from_new_hypothesis(self):
        out = json.loads(self._demo()(_LINK_PROMPT))
        assert out["edges"][0]["type"] == "opens_question"
        assert out["edges"][0]["from"] == "22222222-2222-2222-2222-222222222222"
        assert out["edges"][0]["to"] == "33333333-3333-3333-3333-333333333333"
