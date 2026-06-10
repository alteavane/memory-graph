# VHS Demo

Generates `demo.gif` (in the repo root) in a **deterministic and reproducible** way.
It shows the Memory Agent capturing thought from free-form text — without depending
on a live LLM during recording.

## Usage

```bash
brew install vhs        # once — also pulls in ttyd and ffmpeg
bash demo/make_demo.sh  # VHS render → optimization → demo.gif (~3 MB)
```

## What it shows (UC-01 scenario, researcher "marco")

1. **Observation** — the agent extracts a node from an empirical observation (Lan et al.).
2. **Hypothesis + contradiction** — the pH hypothesis contradicts the observation:
   the agent flags it and creates the `contradicts` edge; it also proposes `opens_question`.
3. **DeadEnd** — a dead end, a first-class datum.
4. **falsifies** — the TMPRSS2 discovery; the agent proposes the `falsifies` edge.
5. **show** — graph snapshot (5 nodes, 3 edges).
6. **update + history** — the falsified hypothesis collapses (0.60 → 0.15) and the
   `history` shows the full trajectory: nothing is ever deleted.

## How it stays deterministic

`agent-extract` is interactive and LLM-driven. For a repeatable video we use
the **`demo`** provider (`MEMORYGRAPH_LLM_PROVIDER=demo`, in `llm/providers.py`):
a fixtures-based *replay* LLM that instantly returns the nodes,
contradictions, and edges of the scenario. It resolves the real UUIDs by reading them
from the prompt itself, so the flow is identical on every run even when the IDs change.
The interactive prompts stay real: it is VHS that types the `a`/`y` answers.

## Files

| File | Versioned | Role |
|---|---|---|
| `demo.tape` | ✅ | self-contained VHS script (hidden setup + visible flow) |
| `ids.py` | ✅ | helper: prints the project/hypothesis UUID (resolved at runtime in the tape) |
| `make_demo.sh` | ✅ | orchestrator: VHS render + GIF optimization |
| `memorygraph-video-script.md` | ✅ | reference narrative script (the commands shown) |
| `../demo.gif` | ✅ | output to embed in the README |
| `../data/demo.kuzu` | ❌ | demo DB (regenerated from the tape on every run) |

## Customizing

- **Appearance** (theme, font, size, speed): the `Set …` lines in `demo.tape`.
- **Timing and narration**: the `Type`/`Sleep` blocks in `demo.tape`. The comments
  avoid the apostrophe `'` (it would break shell parsing in the VHS terminal).
- **Scenario** (nodes, contradictions, edges): the `_DEMO_*` fixtures in
  `src/memorygraph/llm/providers.py`. If you change a `--text` string in the tape,
  make sure it still contains the *needle* recognized by the fixtures.
- **GIF weight**: the `fps`/`scale`/`max_colors` parameters in `make_demo.sh`.
