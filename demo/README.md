# Demo VHS

Genera `demo.gif` (nella root del repo) in modo **deterministico e riproducibile**.
Mostra il Memory Agent che cattura il pensiero da testo libero — senza dipendere
da un LLM live durante la registrazione.

## Uso

```bash
brew install vhs        # una volta — tira dentro anche ttyd e ffmpeg
bash demo/make_demo.sh  # render VHS → ottimizzazione → demo.gif (~3 MB)
```

## Cosa mostra (scenario UC-01, ricercatore "marco")

1. **Observation** — l'agente estrae un nodo da un'osservazione empirica (Lan et al.).
2. **Hypothesis + contraddizione** — l'ipotesi pH contraddice l'osservazione:
   l'agente la segnala e crea l'arco `contraddice`; propone anche `apre_domanda`.
3. **DeadEnd** — un vicolo cieco, dato di prima classe.
4. **falsifica** — la scoperta TMPRSS2; l'agente propone l'arco `falsifica`.
5. **show** — snapshot del grafo (5 nodi, 3 archi).
6. **update + history** — l'ipotesi falsificata collassa (0.60 → 0.15) e la
   `history` mostra la traiettoria completa: nulla viene mai cancellato.

## Come resta deterministico

`agent-extract` è interattivo e guidato dall'LLM. Per un video ripetibile usiamo
il provider **`demo`** (`MEMORYGRAPH_LLM_PROVIDER=demo`, in `llm/providers.py`):
un LLM di *replay* fixtures-based che restituisce istantaneamente i nodi,
le contraddizioni e gli archi dello scenario. Risolve gli UUID reali leggendoli
dal prompt stesso, quindi il flusso è identico ad ogni run anche se gli ID cambiano.
I prompt interattivi restano veri: è VHS a digitare le risposte `a`/`y`.

## File

| File | Versionato | Ruolo |
|---|---|---|
| `demo.tape` | ✅ | script VHS self-contained (setup nascosto + flusso visibile) |
| `ids.py` | ✅ | helper: stampa l'UUID di progetto/ipotesi (risolto a runtime nel tape) |
| `make_demo.sh` | ✅ | orchestratore: render VHS + ottimizzazione GIF |
| `memorygraph-video-script.md` | ✅ | script narrativo di riferimento (i comandi mostrati) |
| `../demo.gif` | ✅ | output da incorporare nel README |
| `../data/demo.kuzu` | ❌ | DB della demo (rigenerato dal tape ad ogni run) |

## Personalizzare

- **Aspetto** (tema, font, dimensioni, velocità): le righe `Set …` in `demo.tape`.
- **Tempi e narrazione**: i blocchi `Type`/`Sleep` in `demo.tape`. I commenti
  evitano l'apostrofo `'` (romperebbe il parsing della shell nel terminale VHS).
- **Scenario** (nodi, contraddizioni, archi): le fixtures `_DEMO_*` in
  `src/memorygraph/llm/providers.py`. Se cambi un testo `--text` nel tape,
  assicurati che contenga ancora il *needle* riconosciuto dalle fixtures.
- **Peso del GIF**: i parametri `fps`/`scale`/`max_colors` in `make_demo.sh`.
