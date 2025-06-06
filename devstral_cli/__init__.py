import typer
from config import Config, CONFIG_FILE
from ddg_search import clear_ddg_cache
from .chat import chat

app = typer.Typer(
    help="Devstral Engineer CLI - conversation history is saved between sessions"
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Debug output with profiling"),
) -> None:
    """Start interactive chat when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        chat(verbose=verbose, debug=debug)


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
