# MemoryGraph — Script Comandi per il Video Demo

Scenario: ricercatore "marco" studia il meccanismo di entrata di SARS-CoV-2.

---

## 1. Crea il progetto

```bash
uv run python cli/main.py project-create \
  --user-id marco \
  --title "SARS-CoV-2 entry mechanism" \
  --objective "Understand the molecular pathway of SARS-CoV-2 cell entry and identify viable antiviral targets" \
  --summary "Study of spike-ACE2 interaction and viral entry pathway" \
  --full-context "Research on SARS-CoV-2 cell entry focusing on RBD-ACE2 binding, pH effects, TMPRSS2 role, and potential antiviral targets."
```

**Risposta attesa:**
```
✓ Project creato: 054d6269-dea9-4413-b149-b1ae43d1e25b
  Titolo: SARS-CoV-2 entry mechanism
  Summary: Study of spike-ACE2 interaction and viral entry pathway
```

---

## 2. Inserisce la prima osservazione (Lan et al.)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Lan et al. 2020 (Nature): crystal structure shows that the spike RBD domain binds ACE2 with 10-20x higher affinity than SARS-CoV-1, with 17 contact residues at the interface. Solid empirical finding."
```

**Risposta attesa — il sistema propone il nodo:**
```
[1/1] Nodo candidato:
  Tipo:       Observation
  Contenuto:  The spike RBD domain binds ACE2 with 10-20x higher affinity than
              SARS-CoV-1, with 17 contact residues at the interface.
  Confidence: 0.90
  Trigger:    Lan et al. 2020 (Nature): crystal structure shows that
Approva questo nodo? [y/n/s/a]:
```

**Digita:** `a`

```
✓ Scritti 1 nodi: 81f9a15d
```

---

## 3. Inserisce un'ipotesi (pH / istidina 34)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Hypothesis: protonation of ACE2 histidine 34 in acidic endosomal environment (pH 5.5-6.0) may reduce spike binding affinity, impairing viral entry post-internalization. Open question: does this mechanism apply to all SARS-CoV-2 variants?"
```

**Risposta attesa — il sistema rileva una possibile contraddizione:**
```
[1/2] Nodo candidato:
  Tipo:       Hypothesis
  Contenuto:  protonation of ACE2 histidine 34 in acidic endosomal environment
              (pH 5.5-6.0) may reduce spike binding affinity, impairing viral
              entry post-internalization.
  Confidence: 0.60
  Trigger:    Hypothesis
  ⚠ Possibile contraddizione con nodo 81f9a15d:
    "Il candidato suggerisce che la protonazione riduca l'affinità, mentre il
    nodo esistente indica affinità 10-20x superiore a SARS-CoV-1."
Approva questo nodo? [y/n/s/a]:
```

**Digita:** `a`

```
Creare arco CONTRADDICE? [y/n]:
```

**Digita:** `y`

```
✓ Archi candidati rilevati (2)
  [1] apre_domanda → does this mechanism apply to all SARS-CoV-2 variants?
  [2] supporta     → The spike RBD domain binds ACE2 with 10-20x...
> y
✓ Scritti 2 archi.
✓ Scritti 2 nodi: b08f1faa, 66bacffe
```

---

## 4. Inserisce un dead end (inibitori ACE2)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Tested ACE2 catalytic site inhibitors as antivirals. Result: blocking ACE2 worsens lung damage due to angiotensin II accumulation. Three weeks of work. Dead end — this path is closed."
```

**Risposta attesa:**
```
[1/1] Nodo candidato:
  Tipo:       DeadEnd
  Contenuto:  Blocking ACE2 worsens lung damage due to angiotensin II
              accumulation.
  Confidence: 0.90
  Trigger:    Tested ACE2 catalytic site inhibitors as antivirals.
Approva questo nodo? [y/n/s/a]:
```

**Digita:** `a`

```
✓ Archi candidati rilevati (3)
  [1] supporta    → The spike RBD domain binds ACE2...
  [2] apre_domanda → does this mechanism apply...
  [3] risolve      → protonation of ACE2 histidine 34...
> y
✓ Scritti 3 archi.
✓ Scritti 1 nodi: 07e2f642
```

---

## 5. Inserisce la scoperta TMPRSS2 (Hoffmann et al.)

```bash
uv run python cli/main.py agent-extract \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --text "Hoffmann et al. 2020 (Cell): TMPRSS2 serine protease is required for spike priming on the cell surface. ACE2 alone is not sufficient for viral entry. The TMPRSS2-mediated pathway bypasses the endosomal route — pH is not the main limiting factor. The histidine 34 protonation hypothesis is contradicted."
```

**Risposta attesa — 4 nodi proposti in sequenza:**
```
[1/4] Nodo candidato:
  Tipo:       Observation
  Contenuto:  TMPRSS2 serine protease is required for spike priming on the
              cell surface.
  Confidence: 0.90
  Trigger:    Hoffmann et al. 2020 (Cell)
Approva questo nodo? [y/n/s/a]:
```

**Digita:** `a`

```
✓ Archi candidati rilevati (5)
  [1] supporta     → ACE2 alone is not sufficient for viral entry
  [2] contraddice  → protonation of ACE2 histidine 34...
  [3] apre_domanda → does this mechanism apply to all variants?
  [4] falsifica    → protonation of ACE2 histidine 34...
  [5] supporta     → The spike RBD domain binds ACE2...
> y
✓ Scritti 5 archi.
✓ Scritti 4 nodi: 2b637865, 87bb325b, 513ed646, ade23470
```

---

## 6. Aggiunge una pagina Wiki di sintesi

```bash
uv run python cli/main.py wiki-add \
  --user-id marco \
  --project-id 054d6269-dea9-4413-b149-b1ae43d1e25b \
  --title "Research synthesis — week 3" \
  --summary "Current state of the research after TMPRSS2 discovery" \
  --content "RBD-ACE2 high affinity confirmed (Lan et al.). pH/histidine 34 hypothesis superseded by TMPRSS2 pathway (Hoffmann et al.). ACE2 inhibition as antiviral: certified dead end — angiotensin II accumulation."
```

**Risposta attesa:**
```
✓ WikiPage creata: 13b200d4-b370-416a-9ac0-d292a9d89ffc (v1)
  Titolo: Research synthesis — week 3
```

---

## 7. Mostra il grafo completo

```bash
uv run python cli/main.py show --user-id marco
```

**Risposta attesa:**
```
Grafo utente: marco  (8 nodi, 11 archi)

┌──────────┬──────────────┬────────┬──────────────────────────────────────────────┬─────────────────────────────────┐
│ ID       │ Tipo         │ Conf   │ Contenuto                                    │ Trigger                         │
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
│ Da       │ Tipo           │ A        │ Conf   │
├──────────┼────────────────┼──────────┼────────┤
│ 81f9a15d │ supporta       │ b08f1faa │ 0.90   │
│ b08f1faa │ contraddice    │ 81f9a15d │ 1.00   │
│ b08f1faa │ apre_domanda   │ 66bacffe │ 0.60   │
│ 07e2f642 │ supporta       │ 81f9a15d │ 0.90   │
│ 07e2f642 │ apre_domanda   │ 66bacffe │ 0.60   │
│ 07e2f642 │ risolve        │ b08f1faa │ 0.60   │
│ 2b637865 │ supporta       │ 87bb325b │ 0.90   │
│ 2b637865 │ apre_domanda   │ 66bacffe │ 0.60   │
│ 2b637865 │ supporta       │ 81f9a15d │ 0.90   │
│ 513ed646 │ contraddice    │ b08f1faa │ 0.60   │
│ ade23470 │ falsifica      │ b08f1faa │ 0.90   │
└──────────┴────────────────┴──────────┴────────┘
```

---

## 8. Consulta la storia di un nodo specifico

```bash
uv run python cli/main.py history \
  --node-id 07e2f642-7bb8-43df-8cdd-e19d6ae3926b
```

**Risposta attesa:**
```
Storia: 07e2f642…

┌──────┬────────┬────────────────────────────────────────────────────┬──────────────────────────────────┬─────────────────────┐
│ Ver  │ Conf   │ Contenuto                                          │ Trigger                          │ Creato              │
├──────┼────────┼────────────────────────────────────────────────────┼──────────────────────────────────┼─────────────────────┤
│ 1    │ 0.90   │ Blocking ACE2 worsens lung damage due to           │ Tested ACE2 catalytic site       │ 2026-05-11 11:09:37 │
│      │        │ angiotensin II accumulation.                       │ inhibitors as antivirals.        │                     │
└──────┴────────┴────────────────────────────────────────────────────┴──────────────────────────────────┴─────────────────────┘
```

---

## 9. Legge la pagina Wiki

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

**Risposta attesa:**
```
--- Research synthesis — week 3 (v1) ---
RBD-ACE2 high affinity confirmed (Lan et al.). pH/histidine 34 hypothesis
superseded by TMPRSS2 pathway (Hoffmann et al.). ACE2 inhibition as antiviral:
certified dead end — angiotensin II accumulation.
```

---

## Riepilogo comandi

| Comando             | Scopo                                          |
|---------------------|------------------------------------------------|
| `project-create`    | Crea un nuovo progetto di ricerca              |
| `agent-extract`     | Estrae nodi da testo libero (interattivo)      |
| `wiki-add`          | Aggiunge una pagina di sintesi al progetto     |
| `show`              | Snapshot del grafo: nodi + archi attivi        |
| `history`           | Storia completa di un nodo (tutte le versioni) |
| `update`            | Aggiorna un nodo (crea nuova versione)         |
| `edge-create`       | Crea un arco manualmente tra due nodi          |
| `edge-invalidate`   | Invalida un arco (non lo cancella)             |
| `project-assign`    | Assegna un nodo a un progetto                  |
| `doc-add`           | Aggiunge un documento al DocumentIndex         |
