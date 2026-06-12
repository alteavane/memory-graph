# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from memorygraph.api.schemas import (
    ConsentUpdate,
    NodeSelection,
    TokenIssueRequest,
)


def test_node_selection_defaults_include_history_false():
    sel = NodeSelection(id="n1")
    assert sel.id == "n1"
    assert sel.include_history is False


def test_token_issue_request_defaults():
    req = TokenIssueRequest(recipient_id="bruno", project_id="p1", node_ids=[NodeSelection(id="n1")])
    assert req.wiki_page_ids == []
    assert req.forkable is False
    assert req.ttl_seconds == 86400


def test_consent_update_all_optional():
    upd = ConsentUpdate()
    assert upd.discoverable is None
    assert upd.share_deadends is None
