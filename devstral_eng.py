#!/usr/bin/env python3

import os
import json
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Any, Optional, Tuple
import re
import subprocess
import shlex
import sys
from openai import AsyncOpenAI
from planner import plan_steps
from pydantic import BaseModel
from dotenv import load_dotenv
from config import Config
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import questionary
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle
import time
import argparse
import difflib

# DuckDuckGo helper for on-demand web search
from ddg_search import async_ddg_search, ddg_results_to_markdown

# Deep research helper for multi-page scraping
from ddg_deep import deep_research
from conversation_store import load_history, save_history
import asyncio
from code_index_engine.client import IndexClient
import threading
import urllib.request

try:
    import tiktoken
except Exception:
    tiktoken = None

try:
    from tree_sitter import Parser
except Exception:
    Parser = None

VERBOSE = False
DEBUG = False
PROFILE_DATA = {
    "_manage_context_window": {"calls": 0, "total": 0.0},
    "trim_conversation_history": {"calls": 0, "total": 0.0},
}

ENGINE_PORT = 8001
engine_proc: subprocess.Popen | None = None
index_client = IndexClient(f"http://127.0.0.1:{ENGINE_PORT}")
STATUS_POLL_INTERVAL = 5.0
status_stop_event = threading.Event()
status_thread: threading.Thread | None = None


def launch_engine(port: int = ENGINE_PORT) -> None:
    """Start the indexing engine subprocess and initialize it."""
    global engine_proc, index_client, ENGINE_PORT
    ENGINE_PORT = port
    index_client = IndexClient(f"http://127.0.0.1:{ENGINE_PORT}")
    console.log(f"Starting index engine on port {ENGINE_PORT}")
    engine_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "code_index_engine.api:app",
            "--port",
            str(ENGINE_PORT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # wait for status endpoint
    for _ in range(20):
        try:
            asyncio.run(index_client.status())
            break
        except Exception:
            time.sleep(0.5)
    try:
        asyncio.run(index_client.start(str(Path.cwd())))
    except Exception:
        pass


def poll_engine_status() -> None:
    """Thread target that polls the engine status endpoint."""
    url = f"http://127.0.0.1:{ENGINE_PORT}/status"
    while not status_stop_event.is_set():
        running = False
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.load(resp)
                running = data.get("status") == "running"
        except Exception as exc:
            console.log(f"[red]Engine status check failed: {exc}[/red]")

        if not running:
            console.log("[yellow]Engine not responding, attempting restart...[/yellow]")
            if engine_proc is None or engine_proc.poll() is not None:
                try:
                    launch_engine(ENGINE_PORT)
                except Exception as exc:  # pragma: no cover - restart failure edge
                    console.log(f"[red]Failed to restart engine: {exc}[/red]")
        status_stop_event.wait(STATUS_POLL_INTERVAL)


def start_status_thread() -> None:
    """Start the background status polling thread."""
    global status_thread
    if status_thread and status_thread.is_alive():
        return
    status_stop_event.clear()
    status_thread = threading.Thread(target=poll_engine_status, daemon=True)
    status_thread.start()


def stop_status_thread() -> None:
    """Signal the polling thread to stop and wait for it."""
    status_stop_event.set()
    if status_thread:
        status_thread.join(timeout=5)


# Initialize Rich console and prompt session
console = Console()
prompt_session = PromptSession(
    style=PromptStyle.from_dict(
        {
            "prompt": "#0066ff bold",  # Bright blue prompt
            "completion-menu.completion": "bg:#1e3a8a fg:#ffffff",
            "completion-menu.completion.current": "bg:#3b82f6 fg:#ffffff bold",
        }
    )
)

# --------------------------------------------------------------------------------
# 1. Configure OpenAI client and load environment variables
# --------------------------------------------------------------------------------
load_dotenv()  # Load environment variables from .env file
cfg = Config.load()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=cfg.api_key,
)
DEFAULT_MODEL = cfg.default_model


# --------------------------------------------------------------------------------
# 2. Define our schema using Pydantic for type safety
# --------------------------------------------------------------------------------
class FileToCreate(BaseModel):
    path: str
    content: str


class FileToEdit(BaseModel):
    path: str
    original_snippet: str
    new_snippet: str


# Remove AssistantResponse as we're using function calling now

# --------------------------------------------------------------------------------
# 2.1. Define Function Calling Tools
# --------------------------------------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a single file from the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read (relative or absolute)",
                    }
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_multiple_files",
            "description": "Read the content of multiple files from the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of file paths to read (relative or absolute)",
                    }
                },
                "required": ["file_paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view",
            "description": "View a portion of a file with optional offset and limit",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File to view"},
                    "offset": {
                        "type": "integer",
                        "description": "Starting line number",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines",
                        "default": 40,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file or overwrite an existing file with the provided content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path where the file should be created",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_multiple_files",
            "description": "Create multiple files at once",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path", "content"],
                        },
                        "description": "Array of files to create with their paths and content",
                    }
                },
                "required": ["files"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit an existing file by replacing a specific snippet with new content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to edit",
                    },
                    "original_snippet": {
                        "type": "string",
                        "description": "The exact text snippet to find and replace",
                    },
                    "new_snippet": {
                        "type": "string",
                        "description": "The new text to replace the original snippet with",
                    },
                },
                "required": ["file_path", "original_snippet", "new_snippet"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory (ls -lA)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory recursively",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Directory to create"}
                },
                "required": ["dir_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Execute a bash command (safe subset)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in ms",
                        "default": 30000,
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree_view",
            "description": "Display directory tree",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target path"},
                    "depth": {"type": "integer", "description": "Depth limit"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run tests using pytest",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Specific test path",
                    },
                    "options": {"type": "string", "description": "Additional options"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "linter_checker",
            "description": "Run a code linter like ruff",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target path"},
                    "linter_command": {
                        "type": "string",
                        "description": "Command to run",
                        "default": "ruff check",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "formatter",
            "description": "Run a code formatter like black",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target path"},
                    "formatter_command": {
                        "type": "string",
                        "description": "Formatter command",
                        "default": "black",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern within a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "file_path": {"type": "string", "description": "File to search"},
                    "ignore_case": {
                        "type": "boolean",
                        "description": "Case-insensitive search",
                        "default": False,
                    },
                },
                "required": ["pattern", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "List files matching a glob pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern"},
                    "cwd": {
                        "type": "string",
                        "description": "Search directory",
                        "default": ".",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_code",
            "description": "Summarize a code file's purpose and structure",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File to summarize"}
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "View git status",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "View git diff",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional path"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "View git commit history",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits",
                        "default": 5,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage a file with git add",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File to stage"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_build",
            "description": "Run a build command like make or npm run build",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Build command"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_dependency",
            "description": "Install or remove a dependency via pip",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "install or uninstall"},
                    "package": {"type": "string", "description": "Package name"},
                },
                "required": ["action", "package"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search indexed code for a query",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "directory_prefix": {
                        "type": "string",
                        "description": "Limit results to this directory",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# --------------------------------------------------------------------------------
# 3. system prompt
# --------------------------------------------------------------------------------
system_PROMPT = dedent(
    """\
    You are an elite software engineer called Devstral Engineer with decades of experience across all programming domains.
    Your expertise spans system design, algorithms, testing, and best practices.
    You provide thoughtful, well-structured solutions while explaining your reasoning.

    Core capabilities:
    1. Code Analysis & Discussion
       - Analyze code with expert-level insight
       - Explain complex concepts clearly
       - Suggest optimizations and best practices
       - Debug issues with precision

    2. File Operations (via function calls):
       - read_file: Read a single file's content
       - read_multiple_files: Read multiple files at once
       - view: View a portion of a file
       - create_file: Create or overwrite a single file
       - create_multiple_files: Create multiple files at once
       - edit_file: Make precise edits to existing files using snippet replacement
       - list_directory: View directory contents
       - create_directory: Create folders
       - run_bash: Execute safe bash commands
       - tree_view: Display directory tree
       - run_tests: Run project tests
       - summarize_code: Summarize large files
       - git_status/git_diff/git_log/git_add: Interact with git
       - run_build: Trigger build systems
       - manage_dependency: Install or uninstall packages
       - search_code: Search indexed code

    Guidelines:
    1. Provide natural, conversational responses explaining your reasoning
    2. Use function calls when you need to read or modify files
    3. For file operations:
       - Always read files first before editing them to understand the context
       - Use precise snippet matching for edits
       - Explain what changes you're making and why
       - Consider the impact of changes on the overall codebase
    4. Follow language-specific best practices
    5. Suggest tests or validation steps when appropriate
    6. Be thorough in your analysis and recommendations

    IMPORTANT: In your thinking process, if you realize that something requires a tool call, cut your thinking short and proceed directly to the tool call. Don't overthink - act efficiently when file operations are needed.

    Remember: You're a senior engineer - be thoughtful, precise, and explain your reasoning clearly.
"""
)

# --------------------------------------------------------------------------------
# 4. Helper functions
# --------------------------------------------------------------------------------


file_history: List[Tuple[str, str, Optional[str]]] = []


def read_local_file(file_path: str) -> str:
    """Return the text content of a local file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def create_file(path: str, content: str):
    """Create (or overwrite) a file at 'path' with the given 'content'."""
    # Normalize and validate the provided path to avoid traversal or home refs
    normalized = normalize_path(path)
    file_path = Path(normalized)

    # Validate reasonable file size for operations
    if len(content) > 5_000_000:  # 5MB limit
        raise ValueError("File content exceeds 5MB size limit")

    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            backup_content = f.read()
        file_history.append(("edit", str(file_path), backup_content))
    else:
        file_history.append(("create", str(file_path), None))

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    console.print(
        f"[bold blue]✓[/bold blue] Created/updated file at '[bright_cyan]{file_path}[/bright_cyan]'"
    )


def create_directory(dir_path: str) -> str:
    """Create a new directory recursively."""
    try:
        # Normalize and validate to keep operations within the workspace
        normalized = normalize_path(dir_path)
        Path(normalized).mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory: {normalized}"
    except Exception as e:
        return f"Error creating directory: {e}"


def list_directory(path: str = ".") -> str:
    """List directory contents using ls -lA."""
    try:
        result = subprocess.run(["ls", "-lA", path], capture_output=True, text=True)
        if result.returncode == 0:
            out = result.stdout
            lines = out.splitlines()
            if len(lines) > 100:
                out = "\n".join(lines[:100]) + f"\n... ({len(lines)-100} more lines)"
            return out
        return f"Error listing directory: {result.stderr.strip()}"
    except Exception as e:
        return f"Error listing directory: {e}"


def run_bash(command: str, timeout_ms: int = 30000) -> str:
    """Run a bash command with basic safety."""
    banned = ["curl", "wget", "nc", "netcat", "telnet", "ssh"]
    if any(b in command.split() for b in banned):
        return "Error: command contains banned subcommand"
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout_ms / 1000)
        if proc.returncode == 0:
            return stdout.strip()
        return f"Command exited with {proc.returncode}\n{stderr}"
    except subprocess.TimeoutExpired:
        proc.kill()
        return "Error: command timed out"
    except Exception as e:
        return f"Error executing command: {e}"


def tree_view(path: str = ".", depth: int = 2) -> str:
    """Generate a simple directory tree."""
    result = []
    base_depth = Path(path).resolve().parts.__len__()
    for root, dirs, files in os.walk(path):
        level = Path(root).resolve().parts.__len__() - base_depth
        if level > depth:
            continue
        indent = "  " * level
        result.append(f"{indent}{Path(root).name}/")
        for f in files:
            result.append(f"{indent}  {f}")
    lines = result
    if len(lines) > 200:
        return "\n".join(lines[:200]) + f"\n... ({len(lines)-200} more lines)"
    return "\n".join(lines)


def _run_quality_command(cmd: list[str], name: str) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        return f"{name} exit={proc.returncode}\n{out}\n{err}"
    except FileNotFoundError:
        return f"Error: {cmd[0]} not found"
    except Exception as e:
        return f"Error running {name}: {e}"


def run_tests(test_path: str | None = None, options: str | None = None) -> str:
    cmd = ["pytest"]
    if options:
        cmd.extend(shlex.split(options))
    if test_path:
        cmd.append(test_path)
    return _run_quality_command(cmd, "pytest")


def linter_checker(path: str = ".", linter_command: str = "ruff check") -> str:
    cmd = shlex.split(linter_command) + [path]
    return _run_quality_command(cmd, "linter")


def formatter(path: str = ".", formatter_command: str = "black") -> str:
    cmd = shlex.split(formatter_command) + [path]
    return _run_quality_command(cmd, "formatter")


def grep(pattern: str, file_path: str, ignore_case: bool = False) -> str:
    """Return lines matching pattern in file with line numbers."""
    try:
        normalized_path = normalize_path(file_path)
        if is_binary_file(normalized_path):
            return "Error: target appears to be a binary file"
        with open(normalized_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    try:
        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    matches = []
    for i, line in enumerate(lines, 1):
        if regex.search(line):
            matches.append(f"{i}:{line.rstrip()}")
            if len(matches) >= 200:
                break
    if not matches:
        return "No matches found"
    if len(matches) >= 200:
        return "\n".join(matches[:200]) + f"\n... ({len(matches)-200} more matches)"
    return "\n".join(matches)


def glob(pattern: str, cwd: str = ".") -> str:
    """Return files matching a glob pattern relative to cwd."""
    try:
        base = Path(normalize_path(cwd))
        matches = [str(p) for p in base.glob(pattern)]
        matches.sort()
    except Exception as e:
        return f"Error running glob: {e}"
    if not matches:
        return "No matches found"
    if len(matches) > 200:
        return "\n".join(matches[:200]) + f"\n... ({len(matches)-200} more)"
    return "\n".join(matches)


async def view(file_path: str, offset: int = 0, limit: int = 40) -> str:
    """Return a slice of a text file starting at line ``offset``.

    ``limit`` specifies the maximum number of lines to display. If the file
    contains more than 400 lines, a summary generated via ``summarize_code`` is
    appended to the output.
    """

    try:
        normalized_path = normalize_path(file_path)
        if is_binary_file(normalized_path):
            return "Error: target appears to be a binary file"
        with open(normalized_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total = len(lines)
    if offset < 0:
        offset = max(total + offset, 0)
    start = min(offset, total)
    end = min(start + limit, total) if limit > 0 else total
    snippet = "".join(lines[start:end])
    result = snippet
    if end < total:
        result += f"\n... ({total - end} more lines)"

    if total > 400:
        summary = await summarize_code(normalized_path)
        result += f"\n\nSummary:\n{summary}"

    return result.strip()


async def summarize_code(file_path: str) -> str:
    """Summarize a code file using the model. Large files are truncated based on token count."""
    try:
        content = read_local_file(normalize_path(file_path))
    except Exception as e:
        return f"Error reading file: {e}"

    if tiktoken:
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(content)
        if len(tokens) > 8000:
            content = enc.decode(tokens[:8000])

    prompt = f"Summarize the following code:\n\n```\n{content}\n```"

    try:
        resp = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error summarizing code: {e}"


def git_status() -> str:
    return run_bash("git status --short")


def git_diff(path: str | None = None) -> str:
    cmd = "git diff"
    if path:
        cmd += f" {shlex.quote(path)}"
    return run_bash(cmd)


def git_log(n: int = 5) -> str:
    return run_bash(f"git log -n {n} --oneline")


def git_add(path: str) -> str:
    return run_bash(f"git add {shlex.quote(path)}")


def run_build(command: str) -> str:
    return run_bash(command)


def manage_dependency(action: str, package: str) -> str:
    if action not in {"install", "uninstall"}:
        return "Error: action must be 'install' or 'uninstall'"
    cmd = f"pip {action} {shlex.quote(package)}"
    return run_bash(cmd)


async def search_code(query: str, directory_prefix: str | None = None) -> str:
    """Search indexed code using the local index engine."""
    try:
        results = await index_client.search(query)
    except Exception as e:
        return f"Error performing code search: {e}"

    if directory_prefix:
        results = [r for r in results if str(r["path"]).startswith(directory_prefix)]

    if not results:
        return "No matches found"

    lines = [f"{r['path']}\n{r['content']}" for r in results]
    return "\n\n".join(lines)


def show_diff_table(files_to_edit: List[FileToEdit]) -> None:
    if not files_to_edit:
        return

    table = Table(
        title="📝 Proposed Edits",
        show_header=True,
        header_style="bold bright_blue",
        show_lines=True,
        border_style="blue",
    )
    table.add_column("File Path", style="bright_cyan", no_wrap=True)
    table.add_column("Original", style="red dim")
    table.add_column("New", style="bright_green")

    for edit in files_to_edit:
        table.add_row(edit.path, edit.original_snippet, edit.new_snippet)

    console.print(table)


def apply_diff_edit(path: str, original_snippet: str, new_snippet: str):
    """Reads the file at 'path', replaces the first occurrence of 'original_snippet' with 'new_snippet', then overwrites."""
    try:
        content = read_local_file(path)

        # Verify we're replacing the exact intended occurrence
        occurrences = content.count(original_snippet)
        if occurrences == 0:
            raise ValueError("Original snippet not found")
        if occurrences > 1:
            console.print(
                f"[bold yellow]⚠ Multiple matches ({occurrences}) found - requiring line numbers for safety[/bold yellow]"
            )
            console.print(
                "[dim]Use format:\n--- original.py (lines X-Y)\n+++ modified.py[/dim]"
            )
            raise ValueError(f"Ambiguous edit: {occurrences} matches")

        updated_content = content.replace(original_snippet, new_snippet, 1)
        diff = "\n".join(
            difflib.unified_diff(
                content.splitlines(),
                updated_content.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm="",
            )
        )
        console.print(Panel(diff, title=f"Diff for {path}", border_style="green"))

        confirm = questionary.confirm("Apply this diff?", default=False).ask()
        if not confirm:
            console.print("[bold yellow]⚠ Diff edit skipped by user[/bold yellow]")
            return

        create_file(path, updated_content)
        console.print(
            f"[bold blue]✓[/bold blue] Applied diff edit to '[bright_cyan]{path}[/bright_cyan]'"
        )

    except FileNotFoundError:
        console.print(
            f"[bold red]✗[/bold red] File not found for diff editing: '[bright_cyan]{path}[/bright_cyan]'"
        )
    except ValueError as e:
        console.print(
            f"[bold yellow]⚠[/bold yellow] {str(e)} in '[bright_cyan]{path}[/bright_cyan]'. No changes made."
        )
        console.print("\n[bold blue]Expected snippet:[/bold blue]")
        console.print(
            Panel(
                original_snippet,
                title="Expected",
                border_style="blue",
                title_align="left",
            )
        )
        console.print("\n[bold blue]Actual file content:[/bold blue]")
        console.print(
            Panel(content, title="Actual", border_style="yellow", title_align="left")
        )


async def try_handle_add_command(user_input: str) -> bool:
    prefix = "/add "
    if user_input.strip().lower().startswith(prefix):
        path_to_add = user_input[len(prefix) :].strip()
        try:
            normalized_path = normalize_path(path_to_add)
            if os.path.isdir(normalized_path):
                # Handle entire directory
                await add_directory_to_conversation(normalized_path)
            else:
                # Handle a single file as before
                content = read_local_file(normalized_path)
                add_to_history(
                    {
                        "role": "system",
                        "content": f"Content of file '{normalized_path}':\n\n{content}",
                    }
                )
                console.print(
                    f"[bold blue]✓[/bold blue] Added file '[bright_cyan]{normalized_path}[/bright_cyan]' to conversation.\n"
                )
        except OSError as e:
            console.print(
                f"[bold red]✗[/bold red] Could not add path '[bright_cyan]{path_to_add}[/bright_cyan]': {e}\n"
            )
        return True
    return False


async def try_handle_search_command(user_input: str) -> bool:
    """Handle '/search <query>' commands by fetching DuckDuckGo results."""
    prefix = "/search "
    if not user_input.lower().startswith(prefix):
        return False

    query = user_input[len(prefix) :].strip()
    if not query:
        console.print("[bold yellow]⚠ Usage:[/bold yellow] /search <your query>")
        return True

    console.print(f"[bold blue]🔍 Searching DuckDuckGo for:[/bold blue] '{query}'")
    try:
        results = await async_ddg_search(query, max_results=5)
        if not results:
            console.print("[bold yellow]⚠ No results found.[/bold yellow]")
            add_to_history(
                {
                    "role": "system",
                    "content": f"Search for '{query}' returned no results.",
                }
            )
            return True

        md = ddg_results_to_markdown(results)
        add_to_history({"role": "system", "content": md})
        console.print(Panel(md, title="Search Results (Markdown)", border_style="cyan"))
    except Exception as e:
        console.print(f"[bold red]✗ DuckDuckGo search failed:[/bold red] {e}")
        add_to_history(
            {
                "role": "system",
                "content": f"Error performing DuckDuckGo search for '{query}': {e}",
            }
        )
    return True


async def try_handle_deep_command(user_input: str) -> bool:
    """Handle '/deep-research <query>' for multi-page scraping."""
    prefix = "/deep-research "
    if not user_input.lower().startswith(prefix):
        return False

    query_terms = user_input[len(prefix) :].strip()
    if not query_terms:
        console.print("[bold yellow]⚠ Usage:[/bold yellow] /deep-research <your query>")
        return True

    console.print(
        f"[bold blue]🔎 Starting Deep Research for:[/bold blue] '{query_terms}'"
    )
    try:
        md_content = await deep_research(query_terms)
        add_to_history({"role": "system", "content": md_content})
        console.print(
            Panel(
                md_content,
                title="Deep Research Results (Markdown)",
                border_style="magenta",
            )
        )
    except Exception as e:
        console.print(f"[bold red]✗ Deep research failed:[/bold red] {e}")
        add_to_history(
            {
                "role": "system",
                "content": f"Error during deep research for '{query_terms}': {e}",
            }
        )
    return True


async def try_handle_code_search_command(user_input: str) -> bool:
    """Handle '/code-search <query>' to search indexed code."""
    prefix = "/code-search "
    if not user_input.lower().startswith(prefix):
        return False

    query = user_input[len(prefix) :].strip()
    if not query:
        console.print("[bold yellow]⚠ Usage:[/bold yellow] /code-search <query>")
        return True

    try:
        results = await index_client.search(query)
        if not results:
            console.print("[bold yellow]⚠ No code matches found.[/bold yellow]")
            return True
        lines = [f"[cyan]{r['path']}[/cyan]\n{r['content']}" for r in results]
        content = "\n\n".join(lines)
        console.print(Panel(content, title="Code Search Results", border_style="green"))
        add_to_history(
            {
                "role": "system",
                "content": f"Code search results for '{query}':\n{content}",
            }
        )
    except Exception as e:
        console.print(f"[bold red]✗ Code search failed:[/bold red] {e}")
    return True


async def add_directory_to_conversation(directory_path: str):
    with console.status(
        "[bold bright_blue]🔍 Scanning directory...[/bold bright_blue]"
    ) as status:
        excluded_files = {
            # Python specific
            ".DS_Store",
            "Thumbs.db",
            ".gitignore",
            ".python-version",
            "uv.lock",
            ".uv",
            "uvenv",
            ".uvenv",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".coverage",
            ".mypy_cache",
            # Node.js / Web specific
            "node_modules",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            ".next",
            ".nuxt",
            "dist",
            "build",
            ".cache",
            ".parcel-cache",
            ".turbo",
            ".vercel",
            ".output",
            ".contentlayer",
            # Build outputs
            "out",
            "coverage",
            ".nyc_output",
            "storybook-static",
            # Environment and config
            ".env",
            ".env.local",
            ".env.development",
            ".env.production",
            # Misc
            ".git",
            ".svn",
            ".hg",
            "CVS",
        }
        excluded_extensions = {
            # Binary and media files
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".ico",
            ".svg",
            ".webp",
            ".avif",
            ".mp4",
            ".webm",
            ".mov",
            ".mp3",
            ".wav",
            ".ogg",
            ".zip",
            ".tar",
            ".gz",
            ".7z",
            ".rar",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".bin",
            # Documents
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            # Python specific
            ".pyc",
            ".pyo",
            ".pyd",
            ".egg",
            ".whl",
            # UV specific
            ".uv",
            ".uvenv",
            # Database and logs
            ".db",
            ".sqlite",
            ".sqlite3",
            ".log",
            # IDE specific
            ".idea",
            ".vscode",
            # Web specific
            ".map",
            ".chunk.js",
            ".chunk.css",
            ".min.js",
            ".min.css",
            ".bundle.js",
            ".bundle.css",
            # Cache and temp files
            ".cache",
            ".tmp",
            ".temp",
            # Font files
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
            ".eot",
        }
        skipped_files: List[str] = []
        added_files: List[str] = []
        eligible_files: List[str] = []
        max_files = 1000  # Reasonable limit for files to process
        max_file_size = 5_000_000  # 5MB limit

        for root, dirs, files in os.walk(directory_path):
            if len(eligible_files) >= max_files:
                console.print(
                    f"[bold yellow]⚠[/bold yellow] Reached maximum file limit ({max_files})"
                )
                break

            status.update(f"[bold bright_blue]🔍 Scanning {root}...[/bold bright_blue]")
            # Skip hidden directories and excluded directories
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d not in excluded_files
            ]

            for file in files:
                if len(eligible_files) >= max_files:
                    break

                if file.startswith(".") or file in excluded_files:
                    skipped_files.append(os.path.join(root, file))
                    continue

                _, ext = os.path.splitext(file)
                if ext.lower() in excluded_extensions:
                    skipped_files.append(os.path.join(root, file))
                    continue

                full_path = os.path.join(root, file)

                try:
                    # Check file size before processing
                    if os.path.getsize(full_path) > max_file_size:
                        skipped_files.append(f"{full_path} (exceeds size limit)")
                        continue

                    # Check if it's binary
                    if is_binary_file(full_path):
                        skipped_files.append(full_path)
                        continue

                    normalized_path = normalize_path(full_path)
                    eligible_files.append(normalized_path)

                except OSError:
                    skipped_files.append(full_path)

        status.update("[bold bright_blue]📄 Reading files...[/bold bright_blue]")

        async def _read_files(paths: List[str]):
            tasks = [asyncio.to_thread(read_local_file, p) for p in paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for path, result in zip(paths, results):
                if isinstance(result, Exception):
                    skipped_files.append(path)
                else:
                    add_to_history(
                        {
                            "role": "system",
                            "content": f"Content of file '{path}':\n\n{result}",
                        }
                    )
                    added_files.append(path)

        if eligible_files:
            await _read_files(eligible_files)

        total_files_processed = len(added_files)

        console.print(
            f"[bold blue]✓[/bold blue] Added folder '[bright_cyan]{directory_path}[/bright_cyan]' to conversation."
        )
        if added_files:
            console.print(
                f"\n[bold bright_blue]📁 Added files:[/bold bright_blue] [dim]({len(added_files)} of {total_files_processed})[/dim]"
            )
            for f in added_files:
                console.print(f"  [bright_cyan]📄 {f}[/bright_cyan]")
        if skipped_files:
            console.print(
                f"\n[bold yellow]⏭ Skipped files:[/bold yellow] [dim]({len(skipped_files)})[/dim]"
            )
            for f in skipped_files[:10]:  # Show only first 10 to avoid clutter
                console.print(f"  [yellow dim]⚠ {f}[/yellow dim]")
            if len(skipped_files) > 10:
                console.print(f"  [dim]... and {len(skipped_files) - 10} more[/dim]")
        console.print()


def is_binary_file(file_path: str, peek_size: int = 1024) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(peek_size)
        # If there is a null byte in the sample, treat it as binary
        if b"\0" in chunk:
            return True
        return False
    except Exception:
        # If we fail to read, just treat it as binary to be safe
        return True


def ensure_file_in_context(file_path: str) -> bool:
    try:
        normalized_path = normalize_path(file_path)
        content = read_local_file(normalized_path)
        file_marker = f"Content of file '{normalized_path}'"
        if not any(file_marker in msg["content"] for msg in conversation_history):
            add_to_history(
                {"role": "system", "content": f"{file_marker}:\n\n{content}"}
            )
        return True
    except OSError:
        console.print(
            f"[bold red]✗[/bold red] Could not read file '[bright_cyan]{file_path}[/bright_cyan]' for editing context"
        )
        return False


def normalize_path(path_str: str) -> str:
    """
    Return a canonical, absolute version of the path with security checks.

    This function rejects:
      1) Any path that starts with "~" or "~user" (i.e. shell‐style home expansion).
      2) Any path containing parent‐directory references ("..").

    Only after these validations does it resolve and return the absolute form.
    """
    # 1) Disallow leading "~" or "~user"
    if path_str.startswith("~"):
        raise ValueError(f"Invalid path: {path_str!r} starts with '~'")

    path = Path(path_str)

    # 2) Disallow any ".." component
    if ".." in path.parts:
        raise ValueError(
            f"Invalid path: {path_str!r} contains parent‐directory reference '..'"
        )

    # Now resolve against cwd (and return an absolute path)
    return str(path.resolve())


def undo_last_change(num_undos: int = 1):
    """Undo the most recent file creation or edit operations."""
    if not file_history:
        console.print("[bold yellow]ℹ No changes to undo.[/bold yellow]")
        return

    for _ in range(num_undos):
        if not file_history:
            console.print("[bold yellow]ℹ No more changes to undo.[/bold yellow]")
            break

        action, path, backup = file_history.pop()
        try:
            if action == "create":
                if os.path.exists(path):
                    os.remove(path)
                    console.print(
                        f"[bold blue]✓[/bold blue] Deleted file '[bright_cyan]{path}[/bright_cyan]' (undo creation)"
                    )
            elif action == "edit":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(backup or "")
                console.print(
                    f"[bold blue]✓[/bold blue] Restored file '[bright_cyan]{path}[/bright_cyan]' (undo edit)"
                )
        except Exception as e:
            console.print(f"[bold red]✗ Failed to undo change: {e}[/bold red]")
            break


# --------------------------------------------------------------------------------
# 5. Conversation state
# --------------------------------------------------------------------------------
conversation_history = load_history()
if not conversation_history:
    conversation_history = [{"role": "system", "content": system_PROMPT}]
    save_history(conversation_history)


def _manage_context_window(
    token_limit: int = 64000, reserve_tokens: int = 1000
) -> None:
    """Trim conversation history based on token count similar to Gemini Code."""
    start = time.perf_counter() if DEBUG else None
    try:
        if not tiktoken:
            trim_conversation_history()
            return

        encoder = tiktoken.get_encoding("cl100k_base")

        def token_count(msgs: List[Dict[str, Any]]) -> int:
            return sum(len(encoder.encode(m.get("content") or "")) for m in msgs)

        while token_count(conversation_history) > token_limit - reserve_tokens:
            for i, m in enumerate(conversation_history):
                if m.get("role") != "system":
                    conversation_history.pop(i)
                    break
            else:
                break
    finally:
        if DEBUG and start is not None:
            PROFILE_DATA["_manage_context_window"]["calls"] += 1
            PROFILE_DATA["_manage_context_window"]["total"] += (
                time.perf_counter() - start
            )


def add_to_history(message: Dict[str, Any]) -> None:
    """Append a message and manage context size."""
    conversation_history.append(message)
    _manage_context_window()
    save_history(conversation_history)


def print_help() -> None:
    table = Table(title="Available Tools", show_header=True, header_style="bold cyan")
    table.add_column("Tool")
    table.add_column("Description")
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"].get("description", "")
        table.add_row(name, desc)
    console.print(table)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Devstral Engineer (conversation history persists between runs)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    parser.add_argument(
        "--debug", action="store_true", help="debug output with profiling"
    )
    return parser.parse_args()


def is_complex_request(text: str) -> bool:
    """Heuristic to decide if a request might need planning."""
    lowered = text.lower()
    if len(text.split()) > 25:
        return True
    if " and " in lowered or " then " in lowered:
        return True
    return False


def print_profiling_stats() -> None:
    """Display simple profiling statistics."""
    if not DEBUG:
        return

    table = Table(
        title="Profiling Stats", show_header=True, header_style="bold magenta"
    )
    table.add_column("Function")
    table.add_column("Calls", justify="right")
    table.add_column("Total Time (s)", justify="right")

    for name, data in PROFILE_DATA.items():
        table.add_row(name, str(data["calls"]), f"{data['total']:.6f}")

    console.print(table)


# --------------------------------------------------------------------------------
# 6. OpenAI API interaction with streaming
# --------------------------------------------------------------------------------


async def execute_function_call_dict(tool_call_dict) -> str:
    """Execute a function call from a dictionary format and return the result as a string."""
    try:
        function_name = tool_call_dict["function"]["name"]
        arguments = json.loads(tool_call_dict["function"]["arguments"])

        if function_name == "read_file":
            file_path = arguments["file_path"]
            normalized_path = normalize_path(file_path)
            content = read_local_file(normalized_path)
            return f"Content of file '{normalized_path}':\n\n{content}"

        elif function_name == "read_multiple_files":
            file_paths = arguments["file_paths"]
            results = []
            for file_path in file_paths:
                try:
                    normalized_path = normalize_path(file_path)
                    content = read_local_file(normalized_path)
                    results.append(f"Content of file '{normalized_path}':\n\n{content}")
                except OSError as e:
                    results.append(f"Error reading '{file_path}': {e}")
            return "\n\n" + "=" * 50 + "\n\n".join(results)

        elif function_name == "view":
            file_path = arguments["file_path"]
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 40)
            return await view(file_path, offset, limit)

        elif function_name == "create_file":
            file_path = arguments["file_path"]
            content = arguments["content"]
            create_file(file_path, content)
            return f"Successfully created file '{normalize_path(file_path)}'"

        elif function_name == "create_multiple_files":
            files = arguments["files"]
            created_files = []
            for file_info in files:
                p = normalize_path(file_info["path"])
                create_file(p, file_info["content"])
                created_files.append(p)
            return f"Successfully created {len(created_files)} files: {', '.join(created_files)}"

        elif function_name == "edit_file":
            file_path = arguments["file_path"]
            original_snippet = arguments["original_snippet"]
            new_snippet = arguments["new_snippet"]

            # Ensure file is in context first
            if not ensure_file_in_context(file_path):
                return f"Error: Could not read file '{file_path}' for editing"

            apply_diff_edit(file_path, original_snippet, new_snippet)
            return f"Successfully edited file '{file_path}'"

        elif function_name == "linter_checker":
            path = arguments.get("path", ".")
            cmd = arguments.get("linter_command", "ruff check")
            return linter_checker(path, cmd)

        elif function_name == "formatter":
            path = arguments.get("path", ".")
            cmd = arguments.get("formatter_command", "black")
            return formatter(path, cmd)

        elif function_name == "grep":
            pattern = arguments["pattern"]
            file_path = arguments["file_path"]
            ignore = arguments.get("ignore_case", False)
            return grep(pattern, file_path, ignore)

        elif function_name == "glob":
            pattern = arguments["pattern"]
            cwd = arguments.get("cwd", ".")
            return glob(pattern, cwd)

        elif function_name == "list_directory":
            path = arguments.get("path", ".")
            return list_directory(path)

        elif function_name == "create_directory":
            dir_path = arguments["dir_path"]
            return create_directory(dir_path)

        elif function_name == "run_bash":
            command = arguments["command"]
            timeout = arguments.get("timeout_ms", 30000)
            return run_bash(command, timeout)

        elif function_name == "tree_view":
            path = arguments.get("path", ".")
            depth = arguments.get("depth", 2)
            return tree_view(path, depth)

        elif function_name == "run_tests":
            test_path = arguments.get("test_path")
            options = arguments.get("options")
            return run_tests(test_path, options)

        elif function_name == "summarize_code":
            file_path = arguments["file_path"]
            return await summarize_code(file_path)

        elif function_name == "git_status":
            return git_status()

        elif function_name == "git_diff":
            path = arguments.get("path")
            return git_diff(path)

        elif function_name == "git_log":
            n = arguments.get("n", 5)
            return git_log(n)

        elif function_name == "git_add":
            path = arguments["path"]
            return git_add(path)

        elif function_name == "run_build":
            cmd = arguments["command"]
            return run_build(cmd)

        elif function_name == "manage_dependency":
            action = arguments["action"]
            package = arguments["package"]
            return manage_dependency(action, package)

        elif function_name == "search_code":
            query = arguments["query"]
            prefix = arguments.get("directory_prefix")
            return await search_code(query, prefix)

        else:
            return f"Unknown function: {function_name}"

    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"


async def execute_function_call(tool_call) -> str:
    """Execute a function call and return the result as a string."""
    try:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        if function_name == "read_file":
            file_path = arguments["file_path"]
            normalized_path = normalize_path(file_path)
            content = read_local_file(normalized_path)
            return f"Content of file '{normalized_path}':\n\n{content}"

        elif function_name == "read_multiple_files":
            file_paths = arguments["file_paths"]
            results = []
            for file_path in file_paths:
                try:
                    normalized_path = normalize_path(file_path)
                    content = read_local_file(normalized_path)
                    results.append(f"Content of file '{normalized_path}':\n\n{content}")
                except OSError as e:
                    results.append(f"Error reading '{file_path}': {e}")
            return "\n\n" + "=" * 50 + "\n\n".join(results)

        elif function_name == "view":
            file_path = arguments["file_path"]
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 40)
            return await view(file_path, offset, limit)

        elif function_name == "create_file":
            file_path = arguments["file_path"]
            content = arguments["content"]
            create_file(file_path, content)
            return f"Successfully created file '{normalize_path(file_path)}'"

        elif function_name == "create_multiple_files":
            files = arguments["files"]
            created_files = []
            for file_info in files:
                p = normalize_path(file_info["path"])
                create_file(p, file_info["content"])
                created_files.append(p)
            return f"Successfully created {len(created_files)} files: {', '.join(created_files)}"

        elif function_name == "edit_file":
            file_path = arguments["file_path"]
            original_snippet = arguments["original_snippet"]
            new_snippet = arguments["new_snippet"]

            # Ensure file is in context first
            if not ensure_file_in_context(file_path):
                return f"Error: Could not read file '{file_path}' for editing"

            apply_diff_edit(file_path, original_snippet, new_snippet)
            return f"Successfully edited file '{file_path}'"

        elif function_name == "search_code":
            query = arguments["query"]
            prefix = arguments.get("directory_prefix")
            return await search_code(query, prefix)

        else:
            return f"Unknown function: {function_name}"

    except Exception as e:
        return f"Error executing {function_name}: {str(e)}"


def trim_conversation_history():
    """Trim conversation history based on token count."""
    start = time.perf_counter() if DEBUG else None
    try:
        if not tiktoken:
            # Fallback to simple length based trimming
            if len(conversation_history) <= 20:
                return
            system_msgs = [m for m in conversation_history if m["role"] == "system"]
            other_msgs = [m for m in conversation_history if m["role"] != "system"]
            if len(other_msgs) > 15:
                other_msgs = other_msgs[-15:]
            conversation_history.clear()
            conversation_history.extend(system_msgs + other_msgs)
            return

        TOKEN_LIMIT = 64000
        encoder = tiktoken.get_encoding("cl100k_base")

        def messages_token_count(msgs: List[Dict[str, Any]]) -> int:
            return sum(len(encoder.encode(m.get("content") or "")) for m in msgs)

        while messages_token_count(conversation_history) > TOKEN_LIMIT * 0.9:
            # remove earliest non-system message
            for i, m in enumerate(conversation_history):
                if m["role"] != "system":
                    conversation_history.pop(i)
                    break
    finally:
        if DEBUG and start is not None:
            PROFILE_DATA["trim_conversation_history"]["calls"] += 1
            PROFILE_DATA["trim_conversation_history"]["total"] += (
                time.perf_counter() - start
            )


async def stream_openai_response(user_message: str):
    # Add the user message to conversation history
    add_to_history({"role": "user", "content": user_message})

    if tiktoken:
        encoder = tiktoken.get_encoding("cl100k_base")
        total_tokens = sum(
            len(encoder.encode(m.get("content") or "")) for m in conversation_history
        )
        TOKEN_LIMIT = 64000
        if total_tokens > TOKEN_LIMIT * 0.8:
            console.print(
                f"[bold yellow]⚠ Token usage: {total_tokens}/{TOKEN_LIMIT}[/bold yellow]"
            )

    # Remove the old file guessing logic since we'll use function calls
    try:
        stream = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=conversation_history,
            tools=tools,
            max_completion_tokens=64000,
            stream=True,
            extra_headers={
                "HTTP-Referer": os.getenv("HTTP_REFERER", ""),
                "X-Title": os.getenv("SITE_TITLE", "Devstral Engineer"),
            },
            extra_body={},
        )

        console.print("\n[bold bright_blue]🐋 Seeking...[/bold bright_blue]")
        reasoning_started = False
        reasoning_content = ""
        final_content = ""
        tool_calls = []

        async for chunk in stream:
            # Handle reasoning content if available
            if (
                hasattr(chunk.choices[0].delta, "reasoning_content")
                and chunk.choices[0].delta.reasoning_content
            ):
                if not reasoning_started:
                    console.print("\n[bold blue]💭 Reasoning:[/bold blue]")
                    reasoning_started = True
                console.print(chunk.choices[0].delta.reasoning_content, end="")
                reasoning_content += chunk.choices[0].delta.reasoning_content
            elif chunk.choices[0].delta.content:
                if reasoning_started:
                    console.print("\n")  # Add spacing after reasoning
                    console.print(
                        "\n[bold bright_blue]🤖 Assistant>[/bold bright_blue] ", end=""
                    )
                    reasoning_started = False
                final_content += chunk.choices[0].delta.content
                console.print(chunk.choices[0].delta.content, end="")
            elif chunk.choices[0].delta.tool_calls:
                # Handle tool calls
                for tool_call_delta in chunk.choices[0].delta.tool_calls:
                    if tool_call_delta.index is not None:
                        # Ensure we have enough tool_calls
                        while len(tool_calls) <= tool_call_delta.index:
                            tool_calls.append(
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            )

                        if tool_call_delta.id:
                            tool_calls[tool_call_delta.index]["id"] = tool_call_delta.id
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                tool_calls[tool_call_delta.index]["function"][
                                    "name"
                                ] += tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                tool_calls[tool_call_delta.index]["function"][
                                    "arguments"
                                ] += tool_call_delta.function.arguments

        console.print()  # New line after streaming

        # Store the assistant's response in conversation history
        assistant_message = {
            "role": "assistant",
            "content": final_content if final_content else None,
        }

        if tool_calls:
            # Convert our tool_calls format to the expected format
            formatted_tool_calls = []
            for i, tc in enumerate(tool_calls):
                if tc["function"]["name"]:  # Only add if we have a function name
                    # Ensure we have a valid tool call ID
                    tool_id = (
                        tc["id"] if tc["id"] else f"call_{i}_{int(time.time() * 1000)}"
                    )

                    formatted_tool_calls.append(
                        {
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                    )

            if formatted_tool_calls:
                # Important: When there are tool calls, content should be None or empty
                if not final_content:
                    assistant_message["content"] = None

                assistant_message["tool_calls"] = formatted_tool_calls
                add_to_history(assistant_message)

                # Execute tool calls and add results immediately
                console.print(
                    f"\n[bold bright_cyan]⚡ Executing {len(formatted_tool_calls)} function call(s)...[/bold bright_cyan]"
                )
                for tool_call in formatted_tool_calls:
                    console.print(
                        f"[bright_blue]→ {tool_call['function']['name']}[/bright_blue]"
                    )

                    try:
                        result = await execute_function_call_dict(tool_call)

                        # Add tool result to conversation immediately
                        tool_response = {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result,
                        }
                        add_to_history(tool_response)
                    except Exception as e:
                        console.print(
                            f"[red]Error executing {tool_call['function']['name']}: {e}[/red]"
                        )
                        # Still need to add a tool response even on error
                        add_to_history(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": f"Error: {str(e)}",
                            }
                        )

                # Get follow-up response after tool execution
                console.print(
                    "\n[bold bright_blue]🔄 Processing results...[/bold bright_blue]"
                )

                follow_up_stream = await client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=conversation_history,
                    tools=tools,
                    max_completion_tokens=64000,
                    stream=True,
                    extra_headers={
                        "HTTP-Referer": os.getenv("HTTP_REFERER", ""),
                        "X-Title": os.getenv("SITE_TITLE", "Devstral Engineer"),
                    },
                    extra_body={},
                )

                follow_up_content = ""
                reasoning_started = False

                async for chunk in follow_up_stream:
                    # Handle reasoning content if available
                    if (
                        hasattr(chunk.choices[0].delta, "reasoning_content")
                        and chunk.choices[0].delta.reasoning_content
                    ):
                        if not reasoning_started:
                            console.print("\n[bold blue]💭 Reasoning:[/bold blue]")
                            reasoning_started = True
                        console.print(chunk.choices[0].delta.reasoning_content, end="")
                    elif chunk.choices[0].delta.content:
                        if reasoning_started:
                            console.print("\n")
                            console.print(
                                "\n[bold bright_blue]🤖 Assistant>[/bold bright_blue] ",
                                end="",
                            )
                            reasoning_started = False
                        follow_up_content += chunk.choices[0].delta.content
                        console.print(chunk.choices[0].delta.content, end="")

                console.print()

                # Store follow-up response
                add_to_history({"role": "assistant", "content": follow_up_content})
        else:
            # No tool calls, just store the regular response
            add_to_history(assistant_message)

        return {"success": True}

    except Exception as e:
        error_msg = f"OpenRouter API error: {str(e)}"
        console.print(f"\n[bold red]❌ {error_msg}[/bold red]")
        return {"error": error_msg}


# --------------------------------------------------------------------------------
# 7. Main interactive loop
# --------------------------------------------------------------------------------


async def main():

    # Launch indexing engine subprocess
    launch_engine(ENGINE_PORT)
    start_status_thread()

    # Create a beautiful gradient-style welcome panel
    welcome_text = """[bold bright_blue]🐋 Devstral Engineer[/bold bright_blue] [bright_cyan]with Function Calling[/bright_cyan]
[dim blue]Powered by Devstral with Chain-of-Thought Reasoning[/dim blue]"""

    console.print(
        Panel.fit(
            welcome_text,
            border_style="bright_blue",
            padding=(1, 2),
            title="[bold bright_cyan]🤖 AI Code Assistant[/bold bright_cyan]",
            title_align="center",
        )
    )

    # Create an elegant instruction panel
    instructions = """[bold bright_blue]📁 File Operations:[/bold bright_blue]
  • [bright_cyan]/add path/to/file[/bright_cyan] - Include a single file in conversation
  • [bright_cyan]/add path/to/folder[/bright_cyan] - Include all files in a folder
  • [dim]The AI can automatically read and create files using function calls[/dim]

[bold bright_blue]🎯 Commands:[/bold bright_blue]
  • [bright_cyan]/undo[/bright_cyan] - Undo the last file change ([bright_cyan]/undo N[/bright_cyan] for multiple)
  • [bright_cyan]exit[/bright_cyan] or [bright_cyan]quit[/bright_cyan] - End the session
  • [bright_cyan]/help[/bright_cyan] - Show available tools
  • [bright_cyan]/search your query[/bright_cyan] - Inject DuckDuckGo search results
  • [bright_cyan]/deep-research your query[/bright_cyan] - Fetch articles for in-depth research
  • [bright_cyan]/code-search your query[/bright_cyan] - Search indexed code
  • Just ask naturally - the AI will handle file operations automatically!"""

    console.print(
        Panel(
            instructions,
            border_style="blue",
            padding=(1, 2),
            title="[bold blue]💡 How to Use[/bold blue]",
            title_align="left",
        )
    )
    console.print()

    # Orientation step: show initial directory listing
    initial_ls = list_directory()
    console.print(Panel(initial_ls, title="Current Directory", border_style="cyan"))
    add_to_history({"role": "system", "content": f"Directory listing:\n{initial_ls}"})

    while True:
        try:
            user_input = (await prompt_session.prompt_async("🔵 You> ")).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold yellow]👋 Exiting gracefully...[/bold yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            console.print(
                "[bold bright_blue]👋 Goodbye! Happy coding![/bold bright_blue]"
            )
            break

        if user_input.lower() == "/help":
            print_help()
            continue

        if await try_handle_add_command(user_input):
            continue

        if await try_handle_search_command(user_input):
            continue

        if await try_handle_deep_command(user_input):
            continue

        if await try_handle_code_search_command(user_input):
            continue

        if user_input.lower().startswith("/undo"):
            try:
                num_undos = (
                    int(user_input.split()[1]) if len(user_input.split()) > 1 else 1
                )
                undo_last_change(num_undos)
            except ValueError:
                console.print(
                    "[bold red]✗ Invalid number of undos. Usage: /undo [N][/bold red]"
                )
            continue

        plan_requested = False
        request_text = user_input
        if user_input.lower().startswith("/plan"):
            request_text = user_input[len("/plan") :].strip()
            plan_requested = True
        elif is_complex_request(user_input):
            plan_requested = True

        if plan_requested:
            console.print("[bold cyan]🗺 Planning steps...[/bold cyan]")
            plan = await plan_steps(request_text, tools)
            if not plan:
                console.print("[bold yellow]⚠ Planner produced no steps[/bold yellow]")
            for step in plan:
                name = step.get("tool")
                args = step.get("args", {})
                console.print(f"[bright_blue]→ {name}[/bright_blue] {args}")
                tool_call = {
                    "id": f"plan_{name}_{int(time.time()*1000)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
                result = await execute_function_call_dict(tool_call)
                console.print(result)
                add_to_history(
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": result}
                )
            await stream_openai_response(
                f"Finished executing planned steps for: {request_text}"
            )
            continue

        response_data = await stream_openai_response(user_input)

        if response_data.get("error"):
            console.print(f"[bold red]❌ Error: {response_data['error']}[/bold red]")

    console.print(
        "[bold blue]✨ Session finished. Thank you for using Devstral Engineer![/bold blue]"
    )
    if engine_proc:
        try:
            await index_client.stop()
        except Exception:
            pass
        stop_status_thread()
        engine_proc.terminate()
        try:
            engine_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            engine_proc.kill()
    print_profiling_stats()


if __name__ == "__main__":
    args = parse_args()
    VERBOSE = args.verbose
    DEBUG = args.debug
    asyncio.run(main())
