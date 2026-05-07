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

app = typer.Typer(help="MemoryGraph CLI — graph store personale basato su credenze.")
console = Console()


def _get_store() -> GraphStore:
    return GraphStore(DB_PATH)


def _get_context() -> ContextStore:
    return ContextStore(DB_PATH)


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
    content: str | None = typer.Option(None, help="Nuovo contenuto (se omesso, riusa il precedente)"),
    confidence: float = typer.Option(..., help="Nuova confidence 0.0–1.0"),
    trigger: str = typer.Option(..., help="Perché è cambiata questa credenza?"),
) -> None:
    """Aggiorna un nodo creando un nuovo stato (non modifica i precedenti)."""
    store = _get_store()
    if content is None:
        history = store.get_node_history(node_id)
        if not history:
            console.print("[red]Errore:[/red] Nessuno stato trovato per questo nodo.")
            raise typer.Exit(1)
        content = history[-1].content
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

    table = Table(title=f"Storia: {node_id[:8]}…", show_lines=True, expand=True)
    table.add_column("Ver", style="cyan", width=4, no_wrap=True)
    table.add_column("Conf", width=6, no_wrap=True)
    table.add_column("Contenuto", ratio=2)
    table.add_column("Trigger", ratio=1)
    table.add_column("Creato", width=19, no_wrap=True)
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
        node_table = Table(title="Nodi (stato più recente)", show_lines=True, expand=True)
        node_table.add_column("ID", width=8, no_wrap=True)
        node_table.add_column("Tipo", width=12, no_wrap=True)
        node_table.add_column("Conf", width=6, no_wrap=True)
        node_table.add_column("Contenuto", ratio=2)
        node_table.add_column("Trigger", ratio=1)
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


@app.command(name="link")
def link(
    from_node: str = typer.Option(..., "--from", help="ID nodo sorgente"),
    to_node: str = typer.Option(..., "--to", help="ID nodo destinazione"),
    type: EdgeType = typer.Option(..., help="Tipo arco"),
    confidence: float = typer.Option(..., help="Confidence 0.0–1.0"),
) -> None:
    """Crea un arco tra due nodi (alias ergonomico di edge-create)."""
    store = _get_store()
    edge = store.create_edge(from_node, to_node, type, confidence)
    console.print(f"[green]✓[/green] Arco creato: [bold]{edge.edge_id}[/bold] ({edge.type.value})")


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


@app.command(name="project-create")
def project_create(
    user_id: str = typer.Option(..., help="ID utente"),
    title: str = typer.Option(..., help="Titolo del progetto"),
    objective: str = typer.Option(..., help="Obiettivo della ricerca"),
    summary: str = typer.Option(..., help="Summary pubblico (viaggia con SubgraphToken)"),
    full_context: str = typer.Option(..., help="Contesto completo — PRIVATO, solo agente"),
) -> None:
    """Crea un nuovo Project con visibilità differenziata summary/full_context."""
    ctx = _get_context()
    project = ctx.projects.create_project(user_id, title, objective, summary, full_context)
    console.print(f"[green]✓[/green] Project creato: [bold]{project.id}[/bold]")
    console.print(f"  Titolo: {project.title}")
    console.print(f"  Summary: {project.summary}")


@app.command(name="project-assign")
def project_assign(
    node_id: str = typer.Option(..., help="ID del nodo epistemico"),
    project_id: str = typer.Option(..., help="ID del Project"),
) -> None:
    """Assegna un nodo a un Project (crea arco appartiene_a)."""
    ctx = _get_context()
    ctx.attach_node(node_id, project_id)
    console.print(
        f"[green]✓[/green] Nodo [bold]{node_id[:8]}[/bold] "
        f"assegnato al project [bold]{project_id[:8]}[/bold]"
    )


@app.command(name="wiki-add")
def wiki_add(
    user_id: str = typer.Option(..., help="ID utente"),
    project_id: str = typer.Option(..., help="ID del Project a cui appartiene"),
    title: str = typer.Option(..., help="Titolo della pagina (stabile tra versioni)"),
    content: str = typer.Option(..., help="Contenuto della pagina"),
    summary: str = typer.Option(..., help="Cosa descrive questa versione?"),
    node_ids: str | None = typer.Option(
        None, help="Nodi da collegare, comma-separated — crea archi documenta"
    ),
) -> None:
    """Crea una nuova WikiPage (v1). Con --node-ids crea anche gli archi documenta."""
    ctx = _get_context()
    entity = ctx.wiki.create_wiki_page(user_id, project_id, title, content, summary)
    if node_ids:
        ids = [n.strip() for n in node_ids.split(",") if n.strip()]
        ctx.wiki.link_to_nodes(entity.id, ids)
        console.print(
            f"[green]✓[/green] WikiPage creata: [bold]{entity.id}[/bold] "
            f"— {len(ids)} nod{'o' if len(ids) == 1 else 'i'} collegat{'o' if len(ids) == 1 else 'i'}"
        )
    else:
        console.print(f"[green]✓[/green] WikiPage creata: [bold]{entity.id}[/bold] (v1)")
    console.print(f"  Titolo: {entity.title}")


@app.command(name="doc-add")
def doc_add(
    user_id: str = typer.Option(..., help="ID utente"),
    title: str = typer.Option(..., help="Titolo del documento"),
    doi: str | None = typer.Option(None, help="DOI (es. 10.1000/xyz123)"),
    url: str | None = typer.Option(None, help="URL del documento"),
    authors: str | None = typer.Option(None, help="Autori comma-separated (es. 'Rossi M, Bianchi A')"),
    pub_date: str | None = typer.Option(None, help="Data pubblicazione YYYY-MM-DD"),
) -> None:
    """Aggiunge un documento al DocumentIndex."""
    ctx = _get_context()
    doc = ctx.documents.add_document(
        user_id, title, doi=doi, url=url, authors=authors, pub_date=pub_date
    )
    console.print(f"[green]✓[/green] Documento aggiunto: [bold]{doc.id}[/bold]")
    console.print(f"  Titolo: {doc.title}")
    if doc.doi:
        console.print(f"  DOI: {doc.doi}")
    if doc.authors:
        console.print(f"  Autori: {doc.authors}")


@app.command(name="agent-extract")
def agent_extract(
    user_id: str = typer.Option(..., "--user-id", help="ID utente"),
    text: str | None = typer.Option(None, "--text", help="Testo da analizzare (ignorato se --from-stdin)"),
    project_id: str | None = typer.Option(None, "--project-id", help="ID progetto (opzionale)"),
    from_stdin: bool = typer.Option(False, "--from-stdin", help="Legge il testo da stdin"),
) -> None:
    """Analizza testo libero e propone nodi interattivamente."""
    if from_stdin:
        input_text = sys.stdin.read().strip()
        if not input_text:
            console.print("[red]Errore:[/red] Il testo da stdin è vuoto.")
            raise typer.Exit(1)
    elif text:
        input_text = text
    else:
        console.print("[red]Errore:[/red] Fornire --text oppure --from-stdin.")
        raise typer.Exit(1)

    agent = MemoryAgent(db_path=DB_PATH, llm=make_llm())
    ids = agent.run(input_text, project_id=project_id, user_id=user_id)
    if ids:
        console.print(f"\n[green]✓[/green] Scritti {len(ids)} nodi: {', '.join(i[:8] for i in ids)}")
    else:
        console.print("\n[yellow]Nessun nodo approvato.[/yellow]")


if __name__ == "__main__":
    app()
