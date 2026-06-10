# Copyright (C) 2026 AlteaVane
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
import sys
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from memorygraph.config import DB_PATH
from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore
from memorygraph.context import ContextStore
from memorygraph.agent.agent import MemoryAgent
from memorygraph.llm import make_llm
from memorygraph.auth.identity import IdentityStore
from memorygraph.auth.schema import init_auth_schema

app = typer.Typer(help="MemoryGraph CLI - personal belief-based graph store.")
console = Console()


def _get_store() -> GraphStore:
    return GraphStore(DB_PATH)


def _get_context() -> ContextStore:
    return ContextStore(DB_PATH)


def _get_identity_store() -> IdentityStore:
    store = GraphStore(DB_PATH)
    init_auth_schema(store._conn)
    return IdentityStore(store._conn)


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_conf(c: float) -> str:
    return f"{c:.2f}"


@app.command()
def create(
    user_id: str = typer.Option(..., help="User ID"),
    type: NodeType = typer.Option(..., help="Node type"),
    content: str = typer.Option(..., help="Belief content"),
    confidence: float = typer.Option(..., help="Confidence 0.0-1.0"),
    trigger: str = typer.Option(..., help="Why was this belief created?"),
) -> None:
    """Create a new node with its first state."""
    store = _get_store()
    entity = store.create_node(user_id, type, content, confidence, trigger)
    console.print(f"[green]✓[/green] Node created: [bold]{entity.id}[/bold] ({entity.type.value})")


@app.command()
def update(
    node_id: str = typer.Option(..., help="ID of the node to update"),
    content: str | None = typer.Option(None, help="New content (if omitted, reuse the previous one)"),
    confidence: float = typer.Option(..., help="New confidence 0.0-1.0"),
    trigger: str = typer.Option(..., help="Why did this belief change?"),
) -> None:
    """Update a node by creating a new state (previous states are not modified)."""
    store = _get_store()
    if content is None:
        history = store.get_node_history(node_id)
        if not history:
            console.print("[red]Error:[/red] No state found for this node.")
            raise typer.Exit(1)
        content = history[-1].content
    state = store.update_node(node_id, content, confidence, trigger)
    console.print(f"[green]✓[/green] Node updated: version [bold]{state.version}[/bold]")


@app.command()
def history(
    node_id: str = typer.Option(..., help="Node ID"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show the full history of a node (all states in chronological order)."""
    store = _get_store()
    states = store.get_node_history(node_id)

    if json_output:
        data = [
            {
                "id": s.id, "version": s.version, "content": s.content,
                "confidence": s.confidence, "trigger": s.trigger,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in states
        ]
        typer.echo(json.dumps(data, indent=2))
        return

    if not states:
        console.print("[yellow]No state found for this node.[/yellow]")
        return

    table = Table(title=f"History: {node_id[:8]}…", show_lines=True, expand=True)
    table.add_column("Ver", style="cyan", width=4, no_wrap=True)
    table.add_column("Conf", width=6, no_wrap=True)
    table.add_column("Content", ratio=2)
    table.add_column("Trigger", ratio=1)
    table.add_column("Created", width=19, no_wrap=True)
    for s in states:
        table.add_row(str(s.version), _fmt_conf(s.confidence), s.content, s.trigger, _fmt_ts(s.created_at))
    console.print(table)


@app.command()
def show(
    user_id: str = typer.Option(..., help="User ID"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show the current snapshot of a user's graph."""
    store = _get_store()
    graph = store.get_graph(user_id)
    nodes = graph["nodes"]
    edges = graph["edges"]

    if json_output:
        data = {
            "nodes": [
                {
                    "id": e.id, "type": e.type.value, "user_id": e.user_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "latest_state": {
                        "version": s.version, "content": s.content,
                        "confidence": s.confidence, "trigger": s.trigger,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                    },
                }
                for e, s in nodes
            ],
            "edges": [
                {
                    "edge_id": ed.edge_id, "from": ed.from_node, "to": ed.to_node,
                    "type": ed.type.value, "confidence": ed.confidence,
                }
                for ed in edges
            ],
        }
        typer.echo(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]User graph:[/bold] {user_id}  ({len(nodes)} nodes, {len(edges)} edges)\n")

    if nodes:
        node_table = Table(title="Nodes (most recent state)", show_lines=True, expand=True)
        node_table.add_column("ID", width=8, no_wrap=True)
        node_table.add_column("Type", width=12, no_wrap=True)
        node_table.add_column("Conf", width=6, no_wrap=True)
        node_table.add_column("Content", ratio=2)
        node_table.add_column("Trigger", ratio=1)
        for entity, state in nodes:
            node_table.add_row(
                entity.id[:8], entity.type.value,
                _fmt_conf(state.confidence), state.content, state.trigger,
            )
        console.print(node_table)

    if edges:
        edge_table = Table(title="Active edges", show_lines=True)
        edge_table.add_column("From", width=8)
        edge_table.add_column("Type", width=14)
        edge_table.add_column("To", width=8)
        edge_table.add_column("Conf", width=6)
        for ed in edges:
            edge_table.add_row(ed.from_node[:8], ed.type.value, ed.to_node[:8], _fmt_conf(ed.confidence))
        console.print(edge_table)


@app.command(name="link")
def link(
    from_node: str = typer.Option(..., "--from", help="Source node ID"),
    to_node: str = typer.Option(..., "--to", help="Target node ID"),
    type: EdgeType = typer.Option(..., help="Edge type"),
    confidence: float = typer.Option(..., help="Confidence 0.0-1.0"),
) -> None:
    """Create an edge between two nodes (ergonomic alias of edge-create)."""
    store = _get_store()
    edge = store.create_edge(from_node, to_node, type, confidence)
    console.print(f"[green]✓[/green] Edge created: [bold]{edge.edge_id}[/bold] ({edge.type.value})")


@app.command(name="edge-create")
def edge_create(
    from_node: str = typer.Option(..., "--from", help="Source node ID"),
    to_node: str = typer.Option(..., "--to", help="Target node ID"),
    type: EdgeType = typer.Option(..., help="Edge type"),
    confidence: float = typer.Option(..., help="Confidence 0.0-1.0"),
) -> None:
    """Create an edge between two nodes."""
    store = _get_store()
    edge = store.create_edge(from_node, to_node, type, confidence)
    console.print(f"[green]✓[/green] Edge created: [bold]{edge.edge_id}[/bold] ({edge.type.value})")


@app.command(name="edge-invalidate")
def edge_invalidate(
    edge_id: str = typer.Option(..., help="ID of the edge to invalidate"),
) -> None:
    """Invalidate an edge (it is not deleted, only timestamped)."""
    store = _get_store()
    edge = store.invalidate_edge(edge_id)
    console.print(f"[yellow]⊘[/yellow] Edge invalidated: [bold]{edge.edge_id}[/bold] at {_fmt_ts(edge.invalidated_at)}")


@app.command(name="project-create")
def project_create(
    user_id: str = typer.Option(..., help="User ID"),
    title: str = typer.Option(..., help="Project title"),
    objective: str = typer.Option(..., help="Research objective"),
    summary: str = typer.Option(..., help="Public summary (travels with the SubgraphToken)"),
    full_context: str = typer.Option(..., help="Full context - PRIVATE, agent only"),
) -> None:
    """Create a new Project with differentiated summary/full_context visibility."""
    ctx = _get_context()
    project = ctx.projects.create_project(user_id, title, objective, summary, full_context)
    console.print(f"[green]✓[/green] Project created: [bold]{project.id}[/bold]")
    console.print(f"  Title: {project.title}")
    console.print(f"  Summary: {project.summary}")


@app.command(name="project-assign")
def project_assign(
    node_id: str = typer.Option(..., help="Epistemic node ID"),
    project_id: str = typer.Option(..., help="Project ID"),
) -> None:
    """Assign a node to a Project (creates a belongs_to edge)."""
    ctx = _get_context()
    ctx.attach_node(node_id, project_id)
    console.print(
        f"[green]✓[/green] Node [bold]{node_id[:8]}[/bold] "
        f"assigned to project [bold]{project_id[:8]}[/bold]"
    )


@app.command(name="wiki-add")
def wiki_add(
    user_id: str = typer.Option(..., help="User ID"),
    project_id: str = typer.Option(..., help="ID of the owning Project"),
    title: str = typer.Option(..., help="Page title (stable across versions)"),
    content: str = typer.Option(..., help="Page content"),
    summary: str = typer.Option(..., help="What does this version describe?"),
    node_ids: str | None = typer.Option(
        None, help="Nodes to link, comma-separated - creates documents edges"
    ),
) -> None:
    """Create a new WikiPage (v1). With --node-ids it also creates documents edges."""
    ctx = _get_context()
    entity = ctx.wiki.create_wiki_page(user_id, project_id, title, content, summary)
    if node_ids:
        ids = [n.strip() for n in node_ids.split(",") if n.strip()]
        ctx.wiki.link_to_nodes(entity.id, ids)
        console.print(
            f"[green]✓[/green] WikiPage created: [bold]{entity.id}[/bold] "
            f"- {len(ids)} node{'' if len(ids) == 1 else 's'} linked"
        )
    else:
        console.print(f"[green]✓[/green] WikiPage created: [bold]{entity.id}[/bold] (v1)")
    console.print(f"  Title: {entity.title}")


@app.command(name="doc-add")
def doc_add(
    user_id: str = typer.Option(..., help="User ID"),
    title: str = typer.Option(..., help="Document title"),
    doi: str | None = typer.Option(None, help="DOI (e.g. 10.1000/xyz123)"),
    url: str | None = typer.Option(None, help="Document URL"),
    authors: str | None = typer.Option(None, help="Authors, comma-separated (e.g. 'Rossi M, Bianchi A')"),
    pub_date: str | None = typer.Option(None, help="Publication date YYYY-MM-DD"),
) -> None:
    """Add a document to the DocumentIndex."""
    ctx = _get_context()
    doc = ctx.documents.add_document(
        user_id, title, doi=doi, url=url, authors=authors, pub_date=pub_date
    )
    console.print(f"[green]✓[/green] Document added: [bold]{doc.id}[/bold]")
    console.print(f"  Title: {doc.title}")
    if doc.doi:
        console.print(f"  DOI: {doc.doi}")
    if doc.authors:
        console.print(f"  Authors: {doc.authors}")


@app.command(name="agent-extract")
def agent_extract(
    user_id: str = typer.Option(..., "--user-id", help="User ID"),
    text: str | None = typer.Option(None, "--text", help="Text to analyze (ignored if --from-stdin)"),
    project_id: str | None = typer.Option(None, "--project-id", help="Project ID (optional)"),
    from_stdin: bool = typer.Option(False, "--from-stdin", help="Read the text from stdin"),
) -> None:
    """Analyze free text and propose nodes interactively."""
    if from_stdin:
        input_text = sys.stdin.read().strip()
        if not input_text:
            console.print("[red]Error:[/red] The text from stdin is empty.")
            raise typer.Exit(1)
    elif text:
        input_text = text
    else:
        console.print("[red]Error:[/red] Provide --text or --from-stdin.")
        raise typer.Exit(1)

    agent = MemoryAgent(db_path=DB_PATH, llm=make_llm())
    ids = agent.run(input_text, project_id=project_id, user_id=user_id)
    if ids:
        console.print(f"\n[green]✓[/green] Wrote {len(ids)} node(s): {', '.join(i[:8] for i in ids)}")
    else:
        console.print("\n[yellow]No node approved.[/yellow]")


@app.command(name="identity-create")
def identity_create(
    user_id: str = typer.Option(..., help="User ID"),
) -> None:
    """Create a new Ed25519 identity for a user."""
    store = _get_identity_store()
    identity = store.create_identity(user_id)
    console.print(f"[green]✓[/green] Identity created for [bold]{identity.user_id}[/bold]")
    console.print(f"  Public key: {identity.public_key}")


@app.command(name="identity-show")
def identity_show(
    user_id: str = typer.Option(..., help="User ID"),
) -> None:
    """Show a user's public key (the private key is never displayed)."""
    store = _get_identity_store()
    public_key = store.get_public_key(user_id)
    if public_key is None:
        console.print(f"[red]No identity found for {user_id}[/red]")
        raise typer.Exit(code=1)
    console.print(f"Public key for [bold]{user_id}[/bold]: {public_key}")


if __name__ == "__main__":
    app()
