# LLM Providers — Design Spec

**Data:** 2026-05-07
**Branch:** feat/llm-providers
**Stato:** Implementato

---

## Obiettivo

Aggiungere supporto a LLM reali (Anthropic e OpenAI) al sistema MemoryGraph, mantenendo l'architettura LLM-agnostica esistente. Il modulo deve essere riusabile sia dalla CLI che dalla futura REST API (Fase 3).

---

## Architettura

Il tipo `LLMCallable = Callable[[str], str]` (definito in `agent/extractor.py`) è il contratto unico. I provider sono factory che restituiscono una `LLMCallable` — nessuna dipendenza da provider specifici nel codice dell'agente.

```
memorygraph/
└── llm/
    ├── __init__.py       ← esporta make_llm()
    └── providers.py      ← factory per Anthropic, OpenAI, demo
```

---

## Selezione provider — Priorità C

```
MEMORYGRAPH_LLM_PROVIDER=anthropic|openai  (esplicito)
        ↓ se assente
ANTHROPIC_API_KEY presente → anthropic
        ↓ se assente
OPENAI_API_KEY presente → openai
        ↓ se assente
demo fallback (stub hardcoded)
```

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `MEMORYGRAPH_LLM_PROVIDER` | — | Forza un provider (`anthropic` o `openai`) |
| `ANTHROPIC_API_KEY` | — | API key Anthropic |
| `MEMORYGRAPH_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Modello Anthropic |
| `OPENAI_API_KEY` | — | API key OpenAI |
| `MEMORYGRAPH_OPENAI_MODEL` | `gpt-4o-mini` | Modello OpenAI |

Tutte le variabili vengono caricate automaticamente da `.env` tramite `python-dotenv` (caricato in `config.py`).

---

## Dipendenze

`anthropic` e `openai` sono dipendenze core del progetto (installate con `uv add`). Gli import sono lazy (dentro le funzioni factory) per evitare errori a runtime se per qualche motivo un pacchetto non fosse disponibile — in quel caso viene sollevato un `RuntimeError` con messaggio chiaro.

---

## Invarianti

- `agent/extractor.py`, `agent/quality.py`, `agent/detector.py`, `agent/agent.py` non importano mai provider LLM — ricevono sempre una `LLMCallable` iniettata
- Il modulo `llm/` non conosce il grafo, i nodi, o la CLI — fa una sola cosa
- Il demo fallback garantisce che il sistema funzioni senza API key configurate

---

## File modificati

| File | Modifica |
|---|---|
| `src/memorygraph/llm/__init__.py` | Nuovo — esporta `make_llm` |
| `src/memorygraph/llm/providers.py` | Nuovo — factory Anthropic, OpenAI, demo |
| `src/memorygraph/config.py` | Aggiunto `load_dotenv()` |
| `cli/main.py` | Sostituito `_make_demo_llm()` con `make_llm()` |
| `pyproject.toml` | Aggiunto `python-dotenv`, `anthropic`, `openai` |
| `.env.example` | Aggiornato con tutte le variabili LLM |
| `tests/test_llm/test_providers.py` | 6 test sulla logica di selezione |
