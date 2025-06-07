from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from rich.console import Console
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, TextLog

import devstral_eng


class _LogWriter:
    """File-like bridge from Rich Console to a TextLog."""

    def __init__(self, log: TextLog) -> None:
        self.log = log

    def write(self, data: str) -> None:  # pragma: no cover - simple passthrough
        self.log.write(data)

    def flush(self) -> None:  # pragma: no cover - interface requirement
        pass


class DevstralTUI(App):
    """Textual UI displaying conversation history and assistant output."""

    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #history, #output { width: 1fr; height: 1fr; border: round $secondary; }
    #input { height: 3; }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self, *, no_index: bool = False) -> None:
        super().__init__()
        self.no_index = no_index
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._engine_task: asyncio.Task[Any] | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover - textual runtime
        with Horizontal(id="body"):
            yield TextLog(id="history", highlight=True)
            yield TextLog(id="output", highlight=True)
        yield Input(placeholder="Message", id="input")

    async def on_mount(self) -> None:  # pragma: no cover - textual runtime
        self.history = self.query_one("#history", TextLog)
        self.output = self.query_one("#output", TextLog)
        self.input = self.query_one(Input)

        # Redirect engine console output to the right pane
        devstral_eng.console = Console(
            file=_LogWriter(self.output),
            force_terminal=True,
            color_system="truecolor",
        )

        # Hook history updates
        original_add = devstral_eng.add_to_history

        def patched_add(message: dict[str, Any]) -> None:
            original_add(message)
            self.refresh_history()

        devstral_eng.add_to_history = patched_add  # type: ignore[assignment]

        # Replace prompt_session with queue-based input
        async def get_input(_: str = "") -> str:
            return await self._input_queue.get()

        devstral_eng.prompt_session.prompt_async = get_input  # type: ignore[assignment]

        self.refresh_history()
        self._engine_task = asyncio.create_task(
            devstral_eng.main(no_index=self.no_index)
        )

    def refresh_history(self) -> None:
        self.history.clear()
        for item in devstral_eng.conversation_history:
            role = item.get("role")
            content = item.get("content") or ""
            self.history.write(f"{role}: {content}\n")

    async def on_input_submitted(self, event: Input.Submitted) -> None:  # pragma: no cover - textual runtime
        await self._input_queue.put(event.value)
        self.input.value = ""

    async def on_unmount(self) -> None:  # pragma: no cover - textual runtime
        if self._engine_task:
            self._engine_task.cancel()
            with contextlib.suppress(Exception):
                await self._engine_task


def run_tui(*, verbose: bool = False, debug: bool = False, no_index: bool = False) -> None:
    """Launch the Devstral textual interface."""

    devstral_eng.VERBOSE = verbose
    devstral_eng.DEBUG = debug
    DevstralTUI(no_index=no_index).run()
