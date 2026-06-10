#!/usr/bin/env bash
# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Genera demo.gif (nella root del repo) in modo deterministico e riproducibile.
# Il tape è self-contained: resetta il DB, usa il provider LLM 'demo' (replay,
# nessuna rete) e cattura gli UUID a runtime via demo/ids.py.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v vhs >/dev/null 2>&1; then
  echo "✗ VHS non è installato. Installalo con:" >&2
  echo "    brew install vhs            # tira dentro anche ttyd e ffmpeg" >&2
  exit 1
fi

echo "▸ Rendering VHS (demo/demo.tape) → demo.gif…"
vhs demo/demo.tape

# Ottimizzazione: VHS produce un GIF ~25fps full-color (≈6MB).
# Riduciamo fps/colori per un GIF leggibile ma leggero (~3MB) adatto al README.
if command -v ffmpeg >/dev/null 2>&1; then
  echo "▸ Ottimizzazione GIF (fps 10, 1200px, 32 colori)…"
  ffmpeg -y -v error -i demo.gif \
    -vf "fps=10,scale=1200:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=32:stats_mode=diff[p];[s1][p]paletteuse=dither=none" \
    demo.opt.gif && mv demo.opt.gif demo.gif
else
  echo "  (ffmpeg assente: salto l'ottimizzazione, GIF non compresso)"
fi

echo "✓ Fatto: demo.gif nella root del repo ($(ls -lh demo.gif | awk '{print $5}'))"
