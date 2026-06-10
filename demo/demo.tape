# MemoryGraph — VHS demo
# L agente cattura il pensiero da testo libero, rileva contraddizioni,
# propone archi; l ipotesi falsificata collassa ma nulla viene cancellato.
#
#   bash demo/make_demo.sh   →   demo.gif
#
# Deterministico: usa il provider LLM 'demo' (replay, nessuna rete).

Output demo.gif
Require uv

Set Shell bash
Set FontSize 16
Set Width 1450
Set Height 900
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 25ms

# --- setup nascosto: DB pulito, provider demo, progetto creato, PID catturato ---
Hide
Type "shopt -s interactive_comments"
Enter
Type "export MEMORYGRAPH_DB_PATH=data/demo.kuzu MEMORYGRAPH_LLM_PROVIDER=demo"
Enter
Type "rm -rf data/demo.kuzu"
Enter
Type "uv run python cli/main.py project-create --user-id marco --title 'SARS-CoV-2 entry mechanism' --objective 'Identify viable antiviral targets' --summary 'Spike-ACE2 interaction and viral entry pathway' --full-context 'RBD-ACE2 binding, pH effects, TMPRSS2 role.'"
Enter
Type "PID=$(uv run python demo/ids.py project)"
Enter
Type "clear"
Enter
Show

Sleep 1s
Type "# MemoryGraph captures the thinking process from free text"
Enter
Sleep 1s

# 2) Osservazione empirica
Type "# An empirical observation becomes an Observation node"
Enter
Sleep 700ms
Type 'uv run python cli/main.py agent-extract --user-id marco --project-id $PID --text "Lan et al. 2020: the spike RBD binds ACE2 with 10-20x higher affinity than SARS-CoV-1."'
Enter
Sleep 4s
Type "a"
Enter
Sleep 2s

# 3) Ipotesi che contraddice l'osservazione
Type "# A conflicting hypothesis is flagged as a contradiction"
Enter
Sleep 700ms
Type 'uv run python cli/main.py agent-extract --user-id marco --project-id $PID --text "Hypothesis: protonation of ACE2 histidine 34 (pH 5.5-6.0) may reduce spike binding. Open question: does it apply to all variants?"'
Enter
Sleep 4s
Type "a"
Enter
Sleep 1500ms
Type "y"
Enter
Sleep 2s
Type "y"
Enter
Sleep 2500ms

# 4) Dead end — dato di prima classe
Type "# A dead end is first-class data, not a failure to hide"
Enter
Sleep 700ms
Type 'uv run python cli/main.py agent-extract --user-id marco --project-id $PID --text "Tested ACE2 catalytic site inhibitors: worsens lung damage via angiotensin II. Dead end."'
Enter
Sleep 4s
Type "a"
Enter
Sleep 2s

# 5) La scoperta che falsifica l'ipotesi
Type "# New evidence: the agent proposes a falsifica edge"
Enter
Sleep 700ms
Type 'uv run python cli/main.py agent-extract --user-id marco --project-id $PID --text "Hoffmann et al. 2020: TMPRSS2 primes spike at the cell surface and bypasses the endosome - pH is not the limiting factor."'
Enter
Sleep 4s
Type "a"
Enter
Sleep 1500ms
Type "y"
Enter
Sleep 2500ms

# 6) Snapshot del grafo
Type "# Graph snapshot: typed nodes and epistemic edges"
Enter
Sleep 600ms
Type "uv run python cli/main.py show --user-id marco"
Enter
Sleep 4500ms

# 7) L ipotesi falsificata collassa — ma la storia resta
Type "# Falsified: the hypothesis confidence collapses"
Enter
Sleep 700ms
Type 'uv run python cli/main.py update --node-id "$(uv run python demo/ids.py hyp)" --confidence 0.15 --trigger "Falsified by the TMPRSS2 surface-pathway evidence"'
Enter
Sleep 3s
Type "# Time travel: the full belief history, nothing is lost"
Enter
Sleep 700ms
Type 'uv run python cli/main.py history --node-id "$(uv run python demo/ids.py hyp)"'
Enter
Sleep 5s
