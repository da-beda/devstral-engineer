import typer
from config import CONFIG_FILE, Config, ThemeConfig

app = typer.Typer(add_completion=False)


THEMES = {
    "light": ThemeConfig(
        success="bold blue",
        error="bold red",
        warning="bold yellow",
        panel="green",
    ),
    "dark": ThemeConfig(
        success="bright_green",
        error="bright_red",
        warning="bright_yellow",
        panel="bright_white",
    ),
    "daltonized": ThemeConfig(
        success="bold cyan",
        error="bold magenta",
        warning="bold white",
        panel="cyan",
    ),
}


@app.command()
def onboard() -> None:
    """Interactive onboarding for first-time setup."""
    cfg = Config.load()

    if not cfg.api_key:
        cfg.api_key = typer.prompt("OpenRouter API key", hide_input=True)

    if not cfg.default_model:
        cfg.default_model = typer.prompt(
            "Default model",
            default="mistralai/devstral-small:free",
        )

    theme_choice = typer.prompt(
        "Color theme",
        type=typer.Choice(list(THEMES.keys())),
        default="light",
    )
    cfg.theme = THEMES[theme_choice]

    cfg.save()
    typer.echo(f"Configuration written to {CONFIG_FILE}")


if __name__ == "__main__":  # pragma: no cover - manual invocation
    app()
