# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_project_root = Path(__file__).parent.parent.parent
DB_PATH = os.getenv(
    "MEMORYGRAPH_DB_PATH",
    str(_project_root / "data" / "memorygraph.kuzu"),
)
