import typer
from config import Config, CONFIG_FILE
from ddg_search import clear_ddg_cache
from conversation_store import display_history, clear_history
from .chat import chat

app = typer.Typer(
    help=(
        "Devstral Engineer CLI - conversation history is saved between sessions."
        " Use the 'history' command to view or 'clear-history' to delete it."
    )
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output (show engine logs)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Debug output with profiling and engine logs",
    ),
    no_index: bool = typer.Option(
        False,
        "--no-index",
        help="Skip launching the indexing engine for this session",
    ),
) -> None:
    """Start interactive chat when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        chat(verbose=verbose, debug=debug, no_index=no_index)


@app.command()
def setup(
    api_key: str = typer.Option(
        ..., prompt=True, hide_input=True, help="OpenRouter API key"
    ),
    model: str = typer.Option(
        "mistralai/devstral-small:free", prompt="Default model", show_default=True
    ),
) -> None:
    """Create or update configuration."""
    cfg = Config(api_key=api_key, default_model=model)
    cfg.save()
    typer.echo(f"Configuration written to {CONFIG_FILE}")


@app.command("set-default-model")
def set_default_model(model: str) -> None:
    """Set the default model used for chatting."""
    cfg = Config.load()
    cfg.default_model = model
    cfg.save()
    typer.echo(f"Default model set to {model}")


@app.command("clear-cache")
def clear_cache() -> None:
    """Remove cached DuckDuckGo search results."""
    clear_ddg_cache()
    typer.echo("DuckDuckGo cache cleared.")


@app.command("history")
def view_history() -> None:
    """Display the stored conversation history."""
    typer.echo(display_history())


@app.command("clear-history")
def clear_history_cmd() -> None:
    """Delete the stored conversation history."""
    clear_history()
    typer.echo("Conversation history cleared.")


@app.command("code-search")
def code_search(query: str, top_k: int = 5) -> None:
    """Search indexed code via the local indexing engine."""
    from code_index_engine.client import IndexClient
    import asyncio

    client = IndexClient()

    async def _run():
        return await client.search(query, top_k)

    results = asyncio.run(_run())
    for item in results:
        typer.echo(f"{item['path']}\n{item['content']}\n")


@app.command("index-status")
def index_status() -> None:
    """Check if the indexing engine is running."""
    from code_index_engine.client import IndexClient
    import asyncio

    client = IndexClient()

    async def _run():
        return await client.status()

    res = asyncio.run(_run())
    typer.echo(res.get("status", "unknown"))


@app.command("index-clear")
def index_clear() -> None:
    """Release the current code index."""
    from code_index_engine.client import IndexClient
    import asyncio

    client = IndexClient()

    async def _run():
        return await client.clear()

    res = asyncio.run(_run())
    typer.echo(res.get("status", "unknown"))
