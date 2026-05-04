from __future__ import annotations

import json
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from memorygraph.config import DB_PATH
from memorygraph.graph.models import EdgeType, NodeType
from memorygraph.graph.store import GraphStore

app = typer.Typer(help="MemoryGraph CLI — graph store personale basato su credenze.")
console = Console()


def _get_store() -> GraphStore:
    return GraphStore(DB_PATH)


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_conf(c: float) -> str:
    return f"{c:.2f}"


@app.command()
def create(
    user_id: str = typer.Option(..., help="ID utente"),
    type: NodeType = typer.Option(..., help="Tipo nodo"),
    content: str = typer.Option(..., help="Contenuto della credenza"),
    confidence: float = typer.Option(..., help="Confidence 0.0–1.0"),
    trigger: str = typer.Option(..., help="Perché è stata creata questa credenza?"),
) -> None:
    """Crea un nuovo nodo con il primo stato."""
    store = _get_store()
    entity = store.create_node(user_id, type, content, confidence, trigger)
    console.print(f"[green]✓[/green] Nodo creato: [bold]{entity.id}[/bold] ({entity.type.value})")


@app.command()
def update(
    node_id: str = typer.Option(..., help="ID del nodo da aggiornare"),
    content: str = typer.Option(..., help="Nuovo contenuto"),
    confidence: float = typer.Option(..., help="Nuova confidence 0.0–1.0"),
    trigger: str = typer.Option(..., help="Perché è cambiata questa credenza?"),
) -> None:
    """Aggiorna un nodo creando un nuovo stato (non modifica i precedenti)."""
    store = _get_store()
    state = store.update_node(node_id, content, confidence, trigger)
    console.print(f"[green]✓[/green] Nodo aggiornato: versione [bold]{state.version}[/bold]")


@app.command()
def history(
    node_id: str = typer.Option(..., help="ID del nodo"),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON"),
) -> None:
    """Mostra la storia completa di un nodo (tutti gli stati in ordine cronologico)."""
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
        console.print("[yellow]Nessuno stato trovato per questo nodo.[/yellow]")
        return

    table = Table(title=f"Storia nodo: {node_id}", show_lines=True)
    table.add_column("Ver", style="cyan", width=4)
    table.add_column("Conf", width=6)
    table.add_column("Contenuto", min_width=30)
    table.add_column("Trigger", min_width=20)
    table.add_column("Creato", width=19)
    for s in states:
        table.add_row(str(s.version), _fmt_conf(s.confidence), s.content, s.trigger, _fmt_ts(s.created_at))
    console.print(table)


@app.command()
def show(
    user_id: str = typer.Option(..., help="ID utente"),
    json_output: bool = typer.Option(False, "--json", help="Output in formato JSON"),
) -> None:
    """Mostra lo snapshot attuale del grafo di un utente."""
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

    console.print(f"\n[bold]Grafo utente:[/bold] {user_id}  ({len(nodes)} nodi, {len(edges)} archi)\n")

    if nodes:
        node_table = Table(title="Nodi (stato più recente)", show_lines=True)
        node_table.add_column("ID", width=8)
        node_table.add_column("Tipo", width=14)
        node_table.add_column("Conf", width=6)
        node_table.add_column("Contenuto", min_width=30)
        node_table.add_column("Trigger", min_width=20)
        for entity, state in nodes:
            node_table.add_row(
                entity.id[:8], entity.type.value,
                _fmt_conf(state.confidence), state.content, state.trigger,
            )
        console.print(node_table)

    if edges:
        edge_table = Table(title="Archi attivi", show_lines=True)
        edge_table.add_column("Da", width=8)
        edge_table.add_column("Tipo", width=14)
        edge_table.add_column("A", width=8)
        edge_table.add_column("Conf", width=6)
        for ed in edges:
            edge_table.add_row(ed.from_node[:8], ed.type.value, ed.to_node[:8], _fmt_conf(ed.confidence))
        console.print(edge_table)


@app.command(name="edge-create")
def edge_create(
    from_node: str = typer.Option(..., "--from", help="ID nodo sorgente"),
    to_node: str = typer.Option(..., "--to", help="ID nodo destinazione"),
    type: EdgeType = typer.Option(..., help="Tipo arco"),
    confidence: float = typer.Option(..., help="Confidence 0.0–1.0"),
) -> None:
    """Crea un arco tra due nodi."""
    store = _get_store()
    edge = store.create_edge(from_node, to_node, type, confidence)
    console.print(f"[green]✓[/green] Arco creato: [bold]{edge.edge_id}[/bold] ({edge.type.value})")


@app.command(name="edge-invalidate")
def edge_invalidate(
    edge_id: str = typer.Option(..., help="ID arco da invalidare"),
) -> None:
    """Invalida un arco (non viene cancellato — viene marcato con timestamp)."""
    store = _get_store()
    edge = store.invalidate_edge(edge_id)
    console.print(f"[yellow]⊘[/yellow] Arco invalidato: [bold]{edge.edge_id}[/bold] alle {_fmt_ts(edge.invalidated_at)}")


if __name__ == "__main__":
    app()
