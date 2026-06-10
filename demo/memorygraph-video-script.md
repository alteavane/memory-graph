# MemoryGraph — Command Script for the Demo Video

Scenario: researcher "marco" studies the SARS-CoV-2 entry mechanism.

---

## 1. Create the project

```bash
uv run python cli/main.py project-create \
  --user-id marco \
  --title "SARS-CoV-2 entry mechanism" \
  --objective "Understand the molecular pathway of SARS-CoV-2 cell entry and identify viable antiviral targets" \
  --summary "Study of spike-ACE2 interaction and viral entry pathway" \
  --full-context "Research on SARS-CoV-2 cell entry focusing on RBD-ACE2 binding, pH effects, TMPRSS2 role, and potential antiviral targets."
```

**Expected response:**
```
✓ Project created: 054d6269-dea9-4413-b149-b1ae43d1e25b
  Title: SARS-CoV-2 entry mechanism
  Summary: Study of spike-ACE2 interaction and viral entry pathway
```

---

## 2. Enters the first observation (Lan et al.)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Lan et al. 2020 (Nature): crystal structure shows that the spike RBD domain binds ACE2 with 10-20x higher affinity than SARS-CoV-1, with 17 contact residues at the interface. Solid empirical finding."
```

**Expected response — the system proposes the node:**
```
[1/1] Candidate node:
  Type:       Observation
  Content:    The spike RBD domain binds ACE2 with 10-20x higher affinity than
              SARS-CoV-1, with 17 contact residues at the interface.
  Confidence: 0.90
  Trigger:    Lan et al. 2020 (Nature): crystal structure shows that
Approve this node? [y/n/s/a]:
```

**Type:** `a`

```
✓ Wrote 1 nodes: 81f9a15d
```

---

## 3. Enters a hypothesis (pH / histidine 34)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Hypothesis: protonation of ACE2 histidine 34 in acidic endosomal environment (pH 5.5-6.0) may reduce spike binding affinity, impairing viral entry post-internalization. Open question: does this mechanism apply to all SARS-CoV-2 variants?"
```

**Expected response — the system detects a possible contradiction:**
```
[1/2] Candidate node:
  Type:       Hypothesis
  Content:    protonation of ACE2 histidine 34 in acidic endosomal environment
              (pH 5.5-6.0) may reduce spike binding affinity, impairing viral
              entry post-internalization.
  Confidence: 0.60
  Trigger:    Hypothesis
  ⚠ Possible contradiction with node 81f9a15d:
    "The candidate suggests that protonation reduces affinity, while the
    existing node indicates 10-20x higher affinity than SARS-CoV-1."
Approve this node? [y/n/s/a]:
```

**Type:** `a`

```
Create CONTRADICTS edge? [y/n]:
```

**Type:** `y`

```
✓ Candidate edges detected (2)
  [1] opens_question → does this mechanism apply to all SARS-CoV-2 variants?
  [2] supports       → The spike RBD domain binds ACE2 with 10-20x...
> y
✓ Wrote 2 edges.
✓ Wrote 2 nodes: b08f1faa, 66bacffe
```

---

## 4. Enters a dead end (ACE2 inhibitors)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Tested ACE2 catalytic site inhibitors as antivirals. Result: blocking ACE2 worsens lung damage due to angiotensin II accumulation. Three weeks of work. Dead end — this path is closed."
```

**Expected response:**
```
[1/1] Candidate node:
  Type:       DeadEnd
  Content:    Blocking ACE2 worsens lung damage due to angiotensin II
              accumulation.
  Confidence: 0.90
  Trigger:    Tested ACE2 catalytic site inhibitors as antivirals.
Approve this node? [y/n/s/a]:
```

**Type:** `a`

```
✓ Candidate edges detected (3)
  [1] supports       → The spike RBD domain binds ACE2...
  [2] opens_question → does this mechanism apply...
  [3] resolves       → protonation of ACE2 histidine 34...
> y
✓ Wrote 3 edges.
✓ Wrote 1 nodes: 07e2f642
```

---

## 5. Enters the TMPRSS2 discovery (Hoffmann et al.)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Hoffmann et al. 2020 (Cell): TMPRSS2 serine protease is required for spike priming on the cell surface. ACE2 alone is not sufficient for viral entry. The TMPRSS2-mediated pathway bypasses the endosomal route — pH is not the main limiting factor. The histidine 34 protonation hypothesis is contradicted."
```

**Expected response — 4 nodes proposed in sequence:**
```
[1/4] Candidate node:
  Type:       Observation
  Content:    TMPRSS2 serine protease is required for spike priming on the
              cell surface.
  Confidence: 0.90
  Trigger:    Hoffmann et al. 2020 (Cell)
Approve this node? [y/n/s/a]:
```

**Type:** `a`

```
✓ Candidate edges detected (5)
  [1] supports       → ACE2 alone is not sufficient for viral entry
  [2] contradicts    → protonation of ACE2 histidine 34...
  [3] opens_question → does this mechanism apply to all variants?
  [4] falsifies      → protonation of ACE2 histidine 34...
  [5] supports       → The spike RBD domain binds ACE2...
> y
✓ Wrote 5 edges.
✓ Wrote 4 nodes: 2b637865, 87bb325b, 513ed646, ade23470
```

---

## 6. Adds a synthesis Wiki page

```bash
uv run python cli/main.py wiki-add \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --title "Research synthesis — week 3" \
  --summary "Current state of the research after TMPRSS2 discovery" \
  --content "RBD-ACE2 high affinity confirmed (Lan et al.). pH/histidine 34 hypothesis superseded by TMPRSS2 pathway (Hoffmann et al.). ACE2 inhibition as antiviral: certified dead end — angiotensin II accumulation."
```

**Expected response:**
```
✓ WikiPage created: 13b200d4-b370-416a-9ac0-d292a9d89ffc (v1)
  Title: Research synthesis — week 3
```

---

## 7. Show the full graph

```bash
uv run python cli/main.py show --user-id marco
```

**Expected response:**
```
User graph: marco  (8 nodes, 11 edges)

┌──────────┬──────────────┬────────┬──────────────────────────────────────────────┬─────────────────────────────────┐
│ ID       │ Type         │ Conf   │ Content                                      │ Trigger                         │
├──────────┼──────────────┼────────┼──────────────────────────────────────────────┼─────────────────────────────────┤
│ 07e2f642 │ DeadEnd      │ 0.90   │ Blocking ACE2 worsens lung damage...         │ Tested ACE2 catalytic site...   │
│ 2b637865 │ Observation  │ 0.90   │ TMPRSS2 serine protease is required...       │ Hoffmann et al. 2020 (Cell)     │
│ 513ed646 │ Observation  │ 0.90   │ The TMPRSS2-mediated pathway bypasses...     │ Hoffmann et al. 2020 (Cell)     │
│ 66bacffe │ OpenQuestion │ 0.60   │ does this mechanism apply to all variants?   │ Open question                   │
│ 81f9a15d │ Observation  │ 0.90   │ The spike RBD domain binds ACE2 10-20x...   │ Lan et al. 2020 (Nature)        │
│ 87bb325b │ Observation  │ 0.90   │ ACE2 alone is not sufficient for entry.      │ Hoffmann et al. 2020 (Cell)     │
│ ade23470 │ DeadEnd      │ 0.90   │ The histidine 34 protonation hypothesis...   │ Hoffmann et al. 2020 (Cell)     │
│ b08f1faa │ Hypothesis   │ 0.60   │ protonation of ACE2 histidine 34...          │ Hypothesis                      │
└──────────┴──────────────┴────────┴──────────────────────────────────────────────┴─────────────────────────────────┘

┌──────────┬────────────────┬──────────┬────────┐
│ From     │ Type           │ To       │ Conf   │
├──────────┼────────────────┼──────────┼────────┤
│ 81f9a15d │ supports       │ b08f1faa │ 0.90   │
│ b08f1faa │ contradicts    │ 81f9a15d │ 1.00   │
│ b08f1faa │ opens_question │ 66bacffe │ 0.60   │
│ 07e2f642 │ supports       │ 81f9a15d │ 0.90   │
│ 07e2f642 │ opens_question │ 66bacffe │ 0.60   │
│ 07e2f642 │ resolves       │ b08f1faa │ 0.60   │
│ 2b637865 │ supports       │ 87bb325b │ 0.90   │
│ 2b637865 │ opens_question │ 66bacffe │ 0.60   │
│ 2b637865 │ supports       │ 81f9a15d │ 0.90   │
│ 513ed646 │ contradicts    │ b08f1faa │ 0.60   │
│ ade23470 │ falsifies      │ b08f1faa │ 0.90   │
└──────────┴────────────────┴──────────┴────────┘
```

---

## 8. Consult the history of a specific node

```bash
uv run python cli/main.py history \
  --node-id 07e2f642-7bb8-43df-8cdd-e19d6ae3926b
```

**Expected response:**
```
History: 07e2f642…

┌──────┬────────┬────────────────────────────────────────────────────┬──────────────────────────────────┬─────────────────────┐
│ Ver  │ Conf   │ Content                                            │ Trigger                          │ Created             │
├──────┼────────┼────────────────────────────────────────────────────┼──────────────────────────────────┼─────────────────────┤
│ 1    │ 0.90   │ Blocking ACE2 worsens lung damage due to           │ Tested ACE2 catalytic site       │ 2026-05-11 11:09:37 │
│      │        │ angiotensin II accumulation.                       │ inhibitors as antivirals.        │                     │
└──────┴────────┴────────────────────────────────────────────────────┴──────────────────────────────────┴─────────────────────┘
```

---

## 9. Read the Wiki page

```bash
uv run python -c "
from memorygraph.config import DB_PATH
from memorygraph.context.wiki import WikiStore
import kuzu
db = kuzu.Database(str(DB_PATH))
conn = kuzu.Connection(db)
wiki = WikiStore(conn)
pages = wiki.list_wiki_pages('054d6269-dea9-4413-b149-b1ae43d1e25b')
for entity, state in pages:
    print(f'--- {entity.title} (v{state.version}) ---')
    print(state.content)
"
```

**Expected response:**
```
--- Research synthesis — week 3 (v1) ---
RBD-ACE2 high affinity confirmed (Lan et al.). pH/histidine 34 hypothesis
superseded by TMPRSS2 pathway (Hoffmann et al.). ACE2 inhibition as antiviral:
certified dead end — angiotensin II accumulation.
```

---

## Command summary

| Command             | Purpose                                        |
|---------------------|------------------------------------------------|
| `project-create`    | Create a new research project                  |
| `agent-extract`     | Extract nodes from free-form text (interactive)|
| `wiki-add`          | Add a synthesis page to the project            |
| `show`              | Graph snapshot: active nodes + edges           |
| `history`           | Full history of a node (all versions)          |
| `update`            | Update a node (creates a new version)          |
| `edge-create`       | Manually create an edge between two nodes      |
| `edge-invalidate`   | Invalidate an edge (does not delete it)        |
| `project-assign`    | Assign a node to a project                     |
| `doc-add`           | Add a document to the DocumentIndex            |
