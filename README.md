# MemoryGraph

> *The process of thinking, made permanent.*

<p align="center">
  <img src="demo.gif" alt="MemoryGraph CLI demo: the Memory Agent extracts nodes from free text, flags a contradiction, proposes edges, and the falsified hypothesis collapses while its full history is preserved" width="820">
</p>

Most of what researchers actually learn never gets recorded.
The failed hypothesis at 11pm. The pivot after a wrong observation.
The dead end that took three weeks — and would have saved the next person three months.

This knowledge disappears. Not because people don't want to preserve it.
Because every existing system asks for an extra act of will to do so.

**MemoryGraph captures it automatically — as a side effect of thinking, not as additional work.**

---

## The core idea

Every unit of thought lives as a node in a personal knowledge graph.
Observations, hypotheses, conclusions, dead ends, open questions.
Each node carries a full temporal history — every change in belief, every pivot, every moment confidence shifted and why.

The graph is never a snapshot. **It is a recording.**

When two researchers need to share knowledge, they don't write a document or schedule a meeting.
One issues a signed **subgraph token** — a precise selection of nodes — to the other.
The recipient receives an isolated fork. They develop it freely.
If they discover something valuable, they propose a merge.
The sender's agent analyzes the semantic delta before any human approves.

This is **Git for knowledge**. Not metaphorically. Architecturally.

| Git | MemoryGraph |
|---|---|
| Repository | Personal knowledge graph |
| Commit | NodeState — a belief captured at a moment in time |
| Fork | SubgraphToken — a signed copy of selected nodes |
| Diff | Semantic delta between two node trajectories |
| Pull request | MergeProposal — with conflict detection |
| Merge conflict | Nodes with contradicting confidence trajectories |

---

## Why this matters

> **$100 billion** is wasted annually in research duplication due to unreported negative results.
> **85%** of research funds are lost in part to selective non-publication.
> **~0** existing tools capture the research *process* without asking for extra effort.

Every attempt to fix this has failed for the same reason:
they require a deliberate, post-hoc act of publication.
More work. No reward. No adoption.

MemoryGraph removes the act entirely.
The knowledge is captured **during** the process, not after it.
Dead ends become first-class data. The dark matter of research finally has a place to live.

---

## Design principles

**No dark periods.**
Every change in belief, every failed experiment, every moment of doubt is a data point.
The trajectory of thought is as valuable as the destination.

**Consent is granular and revocable.**
No access without an explicit, signed token.
Sharing a subgraph never exposes the full graph.
Every token has an issuer, a recipient, a scope, and an expiry.

**The agent suggests. The human decides.**
The Memory Agent observes and updates the graph continuously.
It can propose a match, surface a conflict, suggest a merge.
It never acts without approval.

**Nothing is ever deleted.**
Nodes and edges are invalidated with a timestamp, never removed.
The history of the graph is immutable. You can always go back.

---

## Architecture

Four layers. Each with a single responsibility.

```
┌─────────────────────────────────────────────────────┐
│  L4 — Fork / Merge Engine                           │
│  SubgraphToken · MergeProposal · semantic diff      │
├─────────────────────────────────────────────────────┤
│  L3 — Auth & Consent Layer                          │
│  signed tokens · expiry · revocation · UserConsent  │
├─────────────────────────────────────────────────────┤
│  L2 — Memory Agent                                  │
│  entity extraction · quality gate · pattern detect  │
├─────────────────────────────────────────────────────┤
│  L1 — Graph Store                                   │
│  Kuzu (embedded) · multi-tenant · append-only       │
└─────────────────────────────────────────────────────┘
```

**Graph Store** — The primary data primitive. Each user owns an isolated subgraph.
Nodes are typed epistemic units. Edges are typed relationships. Nothing is ever deleted.
Recommended: [Kuzu](https://kuzudb.com/) for prototype; Neo4j or FalkorDB for scale.

**Memory Agent** — Observes the user's input stream and continuously updates the graph.
Extracts entities, creates nodes, detects contradictions.
Applies a quality gate before every write — not everything belongs in the graph.
LLM-agnostic: works with any model via structured prompting.

**Auth & Consent Layer** — Every sharing operation produces a `SubgraphToken`.
A signed object listing exactly which nodes are shared, with what permissions, with what expiry.
No access without a valid token. Consent is explicit, granular, revocable.

**Fork / Merge Engine** — Sharing produces an isolated copy, never a live view.
The recipient develops the fork freely.
`MergeProposal` presents a semantic diff before any human approves integration.

---

## Schema

```python
# The core belief unit
NodeEntity:
  id              UUID
  user_id         UUID        # multi-tenant isolation
  type            ENUM        # Observation | Hypothesis | Conclusion
                              # DeadEnd | OpenQuestion | Paper
                              # Experiment | MethodDecision
  created_at      TIMESTAMP
  is_deleted      BOOL        # soft delete only — history is immutable

# One row per change in belief
NodeState:
  id              UUID
  node_id         UUID        # → NodeEntity
  version         INT         # incremental from 1
  content         TEXT
  confidence      FLOAT       # 0.0 → 1.0 — the core signal
  trigger         TEXT        # "why did this change?"
  created_at      TIMESTAMP   # this IS the evolution timestamp

# Typed relationships between nodes
Edge:
  from_node       UUID
  to_node         UUID
  type            ENUM        # supports | contradicts | derives_from
                              # falsifies | opens_question | resolves
  confidence      FLOAT       # edges also carry certainty
  invalidated_at  TIMESTAMP   # null if still valid — never delete

# The unit of consensual sharing
SubgraphToken:
  issuer_id       UUID
  recipient_id    UUID
  node_ids        JSONB       # [{id, include_history: bool}]
  forkable        BOOL
  expires_at      TIMESTAMP
  signature       TEXT        # integrity hash

# Cross-graph pattern matching primitive
TrajectoryPattern:
  node_id         UUID
  pattern_type    ENUM        # consolidating | collapsing | recovered
                              # oscillating | terminal_deadend
  context_hash    TEXT        # semantic embedding for cross-user matching
  computed_at     TIMESTAMP

# User-level consent for network participation
UserNetworkConsent:
  discoverable    BOOL        # is my graph searchable?
  share_deadends  BOOL        # include failed trajectories in matches?
  share_triggers  BOOL        # share the "why" text?
  auto_propose    BOOL        # can agent propose matches autonomously?
```

---

## Use cases

### UC-01 — Two researchers, one dead end

Anna studies viral protein binding. Bruno studies immune response.
Anna's hypothesis has been building for three weeks — confidence rising to 0.7.
Then a new experiment. Confidence drops to 0.2. Pattern: `collapsing`.

Her Memory Agent searches the network for nodes with similar semantic content
and pattern type `recovered` — someone who had the same problem and got out of it.
Bruno's graph has exactly this. Trigger: *"corrected pH calculation error"*.

The agent surfaces a suggestion. Anna approves.
A SubgraphToken is issued covering only Bruno's relevant nodes.
Bruno's full graph is never exposed.
Anna receives a fork. She develops it. If she finds something new, she proposes a merge.

**The dark matter of Bruno's research saves Anna three weeks.**

---

### UC-02 — The solo researcher

No collaborators. No network yet. Still valuable.

As the researcher works — reading, noting, experimenting —
the graph builds itself. Every hypothesis gets a NodeState.
Every pivot gets a trigger.

*"Show me how my confidence in hypothesis X has evolved over the last 8 weeks."*

The system reconstructs the full trajectory — including dead ends
that were never written down anywhere else.
The researcher can time-travel through their own thinking.

---

### UC-03 — The lab team

Five researchers. Same project. Parallel tracks.
The graphs do not merge — autonomy is preserved.

The system detects when two researchers are approaching the same hypothesis
from different angles and surfaces a signal: *"Researcher C may be working on something related."*
No content exposed. Just a signal.

When one researcher reaches a conclusion that contradicts another's current hypothesis,
both are alerted. Neither graph is modified. Humans decide how to proceed.

---

### UC-04 — The paper moment

Months of research. Time to write.

The graph already contains the full narrative arc —
every pivot, every dead end, every moment confidence changed and why.
The agent reconstructs the research story chronologically.
`MethodDecision` nodes become the methods section.
`DeadEnd` nodes become structured supplementary material.

**The dark matter becomes published data.**
The next researcher who hits the same wall finds the path out.

---

## Roadmap

**Phase 1 — Foundation**
Graph store with Kuzu · NodeEntity + NodeState with full versioning ·
Edge invalidation (no hard deletes) · Multi-tenant isolation · Basic CLI

**Phase 2 — Memory Agent**
LLM-powered entity extraction · Quality gate before graph write ·
Confidence estimation from language · Trigger population ·
Contradiction detection

**Phase 3 — Sharing protocol**
SubgraphToken generation · Signature and expiry ·
Fork import into isolated graph · UserNetworkConsent ·
Basic REST API between two instances

**Phase 4 — Pattern matching**
TrajectoryPattern computation · Semantic embeddings ·
Cross-user pattern search with consent check ·
MergeProposal with semantic diff ·
Agent-initiated match suggestions

---

## Stack

- **Language**: Python
- **Graph database**: [Kuzu](https://kuzudb.com/) (embedded, prototype) → Neo4j / FalkorDB (scale)
- **LLM**: agnostic — any model via structured prompting
- **Embeddings**: any provider or local model
- **Deployment**: single VPS or distributed (one instance per user)

---

## Contributing

This is an open RFC. The architecture here is a starting point, not a final answer.

We are looking for people who want to:

- **Build** — implement any phase of the roadmap
- **Critique** — open issues challenging the design, find the failure modes
- **Extend** — domain adapters (lab notebooks, clinical research, software engineering, legal)
- **Research** — better trajectory classification, privacy-preserving cross-graph search, consent protocols

Areas where the design is explicitly open:

| Area | Open questions |
|---|---|
| Graph architecture | Alternatives to Kuzu? Schema improvements? |
| Memory Agent | Better quality gate design? Confidence estimation strategies? |
| Consent protocol | Cryptographic hardening? GDPR modeling? Revocation? |
| Pattern matching | Trajectory classification without exposing raw content? |
| Cold start | How to make a single-user graph valuable before the network exists? |

Open an issue. Fork the repo. Break the design.
**The goal is not consensus — it's the best possible system.**

All contributors must sign the Contributor License Agreement before any pull request can be merged.

---

## The belief behind this project

Science accumulates knowledge through published results.
But published results are the final 10% of what was actually learned.
The other 90% — the failed paths, the pivots, the intuitions that didn't pan out —
disappears into lab notebooks that no one reads, or nowhere at all.

This is not a documentation problem. It is an infrastructure problem.
No infrastructure exists for the process of thinking itself.

MemoryGraph is an attempt to build that infrastructure.
Not by asking researchers to do more work.
By making the work they already do leave a permanent, shareable trace.

---

*RFC v0.1 — May 2026 — AGPL-3.0*
