# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared pytest fixtures.

The API tests create many short-lived FastAPI apps, each opening its own Kuzu
database. Kuzu reserves a large virtual-address mmap per database, so dozens of
un-collected databases in one process exhaust the address space. Forcing a GC
sweep after every test releases databases held only by out-of-scope locals
(inline create_app() calls that are never explicitly closed).
"""
import gc

import pytest


@pytest.fixture(autouse=True)
def _release_kuzu_mmaps():
    yield
    gc.collect()
