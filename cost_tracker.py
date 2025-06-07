import time
from typing import Dict, Any
from rich.console import Console

console = Console()

# Track overall session metrics
start_time = time.perf_counter()
total_cost = 0.0
total_api_duration = 0.0

# Warning thresholds
COST_WARNING = 5.0  # dollars
DURATION_WARNING = 60.0  # seconds

# Simple pricing table (USD per token)
PRICING: Dict[str, Dict[str, float]] = {
    "mistralai/devstral-small:free": {"prompt": 0.0, "completion": 0.0},
    "openai/gpt-3.5-turbo": {"prompt": 0.0015 / 1000, "completion": 0.002 / 1000},
    "openai/gpt-4": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
}


def calculate_cost(model: str, usage: Dict[str, Any]) -> float:
    """Return cost in USD for a response usage dictionary."""
    if not usage:
        return 0.0
    pricing = PRICING.get(model)
    if not pricing:
        return 0.0
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return (
        prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]
    )


def add_cost(cost: float, duration: float) -> None:
    """Accumulate cost and API duration, printing warnings if needed."""
    global total_cost, total_api_duration
    total_cost += cost
    total_api_duration += duration
    if total_cost >= COST_WARNING:
        console.print(
            f"[bold yellow]⚠ API cost warning: ${total_cost:.2f} spent[/bold yellow]"
        )
    if total_api_duration >= DURATION_WARNING:
        console.print(
            f"[bold yellow]⚠ API calls taking {total_api_duration:.1f}s so far[/bold yellow]"
        )


def format_cost_summary() -> str:
    """Return a formatted cost summary for the session."""
    elapsed = time.perf_counter() - start_time
    return (
        f"Total API cost: ${total_cost:.4f}\n"
        f"Total API call duration: {total_api_duration:.2f}s\n"
        f"Elapsed session time: {elapsed:.2f}s"
    )
