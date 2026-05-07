# LLM Providers — Piano di Implementazione

**Data:** 2026-05-07
**Branch:** feat/llm-providers
**Spec:** `docs/superpowers/specs/2026-05-07-llm-providers-design.md`
**Stato:** Completato ✅

---

## Task 1: Modulo llm/providers.py

**Files:**
- Create: `src/memorygraph/llm/__init__.py`
- Create: `src/memorygraph/llm/providers.py`
- Create: `tests/test_llm/__init__.py`
- Create: `tests/test_llm/test_providers.py`

- [x] `make_llm()` con logica di selezione priorità C
- [x] `_make_anthropic_llm()` — import lazy, client `anthropic.Anthropic`
- [x] `_make_openai_llm()` — import lazy, client `openai.OpenAI`
- [x] `_make_demo_llm()` — stub per assenza di API key
- [x] Modelli configurabili via env (`MEMORYGRAPH_ANTHROPIC_MODEL`, `MEMORYGRAPH_OPENAI_MODEL`)
- [x] `RuntimeError` con messaggio chiaro se pacchetto non installato
- [x] 6 test: demo fallback, explicit provider, auto-detect, priority

**Commit:** `feat: llm/providers — make_llm() con supporto Anthropic, OpenAI e demo fallback`

---

## Task 2: python-dotenv + .env.example

**Files:**
- Modify: `src/memorygraph/config.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [x] `python-dotenv>=1.0.0` aggiunto alle dipendenze core
- [x] `load_dotenv()` chiamato in `config.py` (punto di ingresso unico)
- [x] `.env.example` aggiornato con sezioni Database, LLM Provider, Anthropic, OpenAI

**Commit:** `feat: python-dotenv — carica .env automaticamente all'avvio`

---

## Task 3: Integrazione CLI

**Files:**
- Modify: `cli/main.py`

- [x] Import `from memorygraph.llm import make_llm`
- [x] Rimosso `_make_demo_llm()` locale dalla CLI
- [x] `agent-extract` usa `make_llm()` invece dello stub

**Commit:** incluso nel commit Task 1

---

## Post-implementation

- [x] 127 test totali, nessuna regressione
- [x] Test manuale end-to-end con `ANTHROPIC_API_KEY` reale
- [x] PR aperta: https://github.com/alteavane/memory-graph/pull/1
