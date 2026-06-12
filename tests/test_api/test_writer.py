# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from memorygraph.api.writer import WriterManager
from memorygraph.graph.models import NodeType


def _mgr(tmp_path):
    # one db file per user_id, all under tmp_path
    return WriterManager(lambda uid: str(tmp_path / f"{uid}.kuzu"))


def test_writer_is_lazy_and_cached(tmp_path):
    mgr = _mgr(tmp_path)
    assert "anna" not in mgr._writers          # nothing created yet
    first = mgr.writer("anna")
    second = mgr.writer("anna")
    assert first is second                       # cached, one connection per user
    mgr.close()


def test_submit_runs_op_against_users_store(tmp_path):
    mgr = _mgr(tmp_path)
    node = mgr.submit(
        "anna",
        lambda s: s.create_node("anna", NodeType.HYPOTHESIS, "pH", 0.6, "t"),
    )
    found = mgr.submit("anna", lambda s: s.get_graph("anna")["nodes"])
    assert [e.id for e, _ in found] == [node.id]
    mgr.close()


def test_users_are_isolated(tmp_path):
    mgr = _mgr(tmp_path)
    mgr.submit("anna", lambda s: s.create_node("anna", NodeType.HYPOTHESIS, "a", 0.6, "t"))
    bruno_nodes = mgr.submit("bruno", lambda s: s.get_graph("bruno")["nodes"])
    assert bruno_nodes == []                     # separate db, separate writer
    assert mgr.writer("anna") is not mgr.writer("bruno")
    mgr.close()


def test_submit_serializes_concurrent_ops(tmp_path):
    import threading

    mgr = _mgr(tmp_path)
    order = []
    barrier = threading.Barrier(8)  # force all threads live at once → real contention

    def op(tag):
        def inner(_store):
            order.append(("start", tag))
            order.append(("end", tag))
            return tag
        return inner

    def run(tag):
        barrier.wait()  # all 8 threads reach submit together
        mgr.submit("anna", op(tag))

    threads = [threading.Thread(target=lambda t=t: run(t)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # serialized → every start is immediately followed by its own end
    for i in range(0, len(order), 2):
        assert order[i][0] == "start"
        assert order[i + 1] == ("end", order[i][1])
    mgr.close()
