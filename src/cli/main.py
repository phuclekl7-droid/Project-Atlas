"""
Project Atlas CLI — Terminal interface for the Personal AI Assistant.

Usage:
    # Interactive chat (REPL)
    python -m src.cli chat --interactive

    # Single message
    python -m src.cli chat "Hello, how are you?"

    # Session management
    python -m src.cli sessions list
    python -m src.cli sessions show <id>
    python -m src.cli sessions rename <id> <name>
    python -m src.cli sessions delete <id>

    # Knowledge base
    python -m src.cli knowledge list
    python -m src.cli knowledge upload <file>

    # Plugins
    python -m src.cli plugins list
    python -m src.cli plugins run <name> <input>

    # Config
    python -m src.cli config show
"""

import sys
import time
from pathlib import Path
from typing import Optional

import typer

from src.core import AssistantError, ConfigurationError, ModelConnectionError
from src.knowledge import SUPPORTED_EXTENSIONS, create_knowledge_base
from src.memory import Memory
from src.model_router import ModelRouter
from src.plugin import PluginLoader
from src.settings import load_settings
from src.workflow import Workflow

# ── Typer app ──
app = typer.Typer(
    name="project-atlas",
    help="🤖 Personal AI Assistant — chat, manage sessions, knowledge base & plugins",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

sessions_app = typer.Typer(help="Manage chat sessions")
app.add_typer(sessions_app, name="sessions")

knowledge_app = typer.Typer(help="Manage knowledge base documents")
app.add_typer(knowledge_app, name="knowledge")

plugins_app = typer.Typer(help="List and run plugins")
app.add_typer(plugins_app, name="plugins")

# ── Shared helpers ──


def _get_version() -> str:
    """Return the current version string."""
    try:
        from importlib.metadata import version
        return version("project-atlas")
    except (ImportError, Exception):
        return "0.6.0-dev"


def _init_backend() -> tuple:
    """
    Initialize and return (settings, memory, model_router, plugin_loader, knowledge_base, workflow).
    Exits on error with a helpful message.
    """
    try:
        settings = load_settings()
    except ConfigurationError as e:
        typer.secho(f"❌ Configuration error: {e.message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"❌ Failed to load settings: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        memory = Memory(db_path=settings.memory_path)
        model_router = ModelRouter(settings)
        plugin_loader = PluginLoader(plugin_package="src.plugins")
        plugin_loader.discover()
        knowledge_base = create_knowledge_base(path="data/knowledge")
        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=settings.max_context_messages,
        )
        return settings, memory, model_router, plugin_loader, knowledge_base, workflow
    except Exception as e:
        typer.secho(f"❌ Initialization failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


def _print_banner(settings) -> None:
    """Print a colorful startup banner."""
    provider_emoji = {
        "mock": "🔌", "ollama": "🦙", "openai": "🔵", "gemini": "🟢",
    }.get(settings.model_provider, "🤖")
    version = _get_version()
    typer.secho(
        f"\n"
        f"  ╔══════════════════════════════════════════╗\n"
        f"  ║    🤖  Project Atlas  v{version:<12}║\n"
        f"  ║    {provider_emoji}  {settings.model_provider.upper():<30}║\n"
        f"  ║    📝  Type /help for commands           ║\n"
        f"  ╚══════════════════════════════════════════╝\n",
        fg=typer.colors.BRIGHT_BLUE,
    )


def _print_result(result, elapsed_ms: float) -> None:
    """Print a workflow result with styling."""
    source_icon = "🧩" if result.source == "plugin" else "🤖"
    source_label = "Plugin" if result.source == "plugin" else "AI"
    latency_str = f"{elapsed_ms:.0f}ms" if elapsed_ms > 0 else "<1ms"

    typer.secho(f"\n{source_icon} [{source_label}] ({latency_str}):", bold=True)
    typer.echo(result.output_text)

    if result.context_used > 0:
        typer.secho(
            f"  └─ Context: {result.context_used} messages",
            fg=typer.colors.BRIGHT_BLACK,
        )


def _print_help() -> None:
    """Print interactive mode help."""
    typer.secho(
        "\n"
        "  📖  Interactive Commands:\n"
        "  ─────────────────────────────────────────────\n"
        "  /help               Show this help\n"
        "  /exit, /quit        Exit the chat\n"
        "  /sessions           List all sessions\n"
        "  /session <id>       Switch to a session\n"
        "  /new               Create a new session\n"
        "  /plugins            List available plugins\n"
        "  /config             Show current configuration\n"
        "  /stats              Show workflow statistics\n"
        "  /clear              Clear the screen\n"
        "\n"
        "  💡  Anything else is sent to the AI assistant.\n"
        "      Type a question, command, or just say hello!\n",
        fg=typer.colors.CYAN,
    )


# ============================================================
# Main Chat Commands
# ============================================================


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Show help when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def chat(
    message: Optional[str] = typer.Argument(
        None,
        help="Message to send. Omit for interactive mode.",
    ),
    session: Optional[str] = typer.Option(
        None, "--session", "-s",
        help="Session ID to use. Creates new if omitted.",
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i",
        help="Start interactive chat mode (REPL).",
    ),
):
    """
    Talk to the AI assistant.

    Provide a message to get a single response, or use --interactive for a REPL.
    """
    settings, memory, model_router, plugin_loader, kb, workflow = _init_backend()

    # Determine session
    session_id = session
    if session_id is None:
        sessions = memory.list_sessions(limit=1)
        if sessions:
            session_id = sessions[0].id
        else:
            session_id = memory.create_session(name="CLI Chat")

    # Single message mode
    if message and not interactive:
        typer.secho(f"\n👤 You: {message}", bold=True)
        session_id = _ensure_session(memory, session_id, "CLI Chat")
        try:
            start = time.time()
            result = workflow.process(message, session_id=session_id)
            elapsed = (time.time() - start) * 1000
            _print_result(result, elapsed)
        except (AssistantError, ModelConnectionError, ConfigurationError) as e:
            typer.secho(f"❌  {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        except Exception as e:
            typer.secho(f"❌  Unexpected error: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        return

    # Interactive mode
    session_id = _ensure_session(memory, session_id, "CLI Chat")
    _print_banner(settings)
    _print_help()

    while True:
        try:
            user_input = typer.prompt("\n👤 You", prompt_suffix=" ")
        except (EOFError, KeyboardInterrupt):
            typer.secho("\n\n👋  Goodbye!", fg=typer.colors.GREEN)
            break

        text = user_input.strip()

        # Handle slash commands
        if text.startswith("/"):
            _handle_slash_command(text, memory, workflow, session_id, settings, plugin_loader, kb)
            continue

        if not text:
            continue

        # Process via workflow
        try:
            start = time.time()
            result = workflow.process(text, session_id=session_id)
            elapsed = (time.time() - start) * 1000
            _print_result(result, elapsed)
        except (AssistantError, ModelConnectionError, ConfigurationError) as e:
            typer.secho(f"❌  {e}", fg=typer.colors.RED, err=True)
        except Exception as e:
            typer.secho(f"❌  Unexpected error: {e}", fg=typer.colors.RED, err=True)


def _ensure_session(memory, session_id: Optional[str], name: str) -> str:
    """Get or create a session."""
    if session_id is None:
        return memory.create_session(name=name)
    existing = memory.get_session(session_id)
    if existing is None:
        return memory.create_session(name=name)
    return session_id


def _handle_slash_command(
    cmd: str,
    memory,
    workflow,
    session_id: str,
    settings,
    plugin_loader,
    kb,
):
    """Handle interactive slash commands."""
    cmd_lower = cmd.lower().strip()

    if cmd_lower in ("/exit", "/quit"):
        typer.secho("👋  Goodbye!", fg=typer.colors.GREEN)
        raise typer.Exit(0)

    elif cmd_lower == "/help":
        _print_help()

    elif cmd_lower == "/sessions":
        _cmd_sessions_list(memory)

    elif cmd_lower.startswith("/session "):
        target_id = cmd[9:].strip()
        session = memory.get_session(target_id)
        if session:
            # Update the session_id in the outer scope via the passed parameter
            # (We can't modify the outer session_id directly, so we print guidance)
            typer.secho(f"ℹ️  Use: --session {target_id} to switch", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"❌  Session '{target_id}' not found", fg=typer.colors.RED)

    elif cmd_lower == "/new":
        new_id = memory.create_session(name="CLI Chat")
        typer.secho(f"✅  Created new session: {new_id}", fg=typer.colors.GREEN)
        typer.secho(f"    Use: --session {new_id} to switch", fg=typer.colors.YELLOW)

    elif cmd_lower == "/plugins":
        _cmd_plugins_list(plugin_loader)

    elif cmd_lower == "/config":
        _cmd_config_show(settings)

    elif cmd_lower == "/stats":
        stats = workflow.get_stats()
        typer.secho("\n📊  Workflow Stats:", bold=True)
        for key, value in stats.items():
            if key == "kb_cache":
                continue
            typer.echo(f"  {key}: {value}")

    elif cmd_lower == "/clear":
        typer.secho("\033[2J\033[H", nl=False)  # ANSI clear screen

    else:
        typer.secho(f"❓  Unknown command: {cmd}", fg=typer.colors.RED)
        typer.secho("    Type /help for available commands", fg=typer.colors.BRIGHT_BLACK)


# ============================================================
# Sessions Commands
# ============================================================


@sessions_app.command("list")
def cmd_sessions_list(
    limit: int = typer.Option(20, "--limit", "-l", help="Max sessions to show"),
):
    """List all chat sessions."""
    _, memory, *_ = _init_backend()
    _cmd_sessions_list(memory, limit)


def _cmd_sessions_list(memory: Memory, limit: int = 20):
    """Shared session list logic."""
    sessions = memory.list_sessions(limit=limit)

    if not sessions:
        typer.secho("📭  No sessions found. Start chatting!", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\n💬  Sessions ({len(sessions)}):", bold=True)
    typer.secho(
        f"  {'ID':<10} {'Name':<30} {'Messages':<10} {'Last Updated':<20}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.secho(
        f"  {'─'*10} {'─'*30} {'─'*10} {'─'*20}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    for s in sessions:
        typer.echo(
            f"  {s.id:<10} {s.name[:28]:<30} {s.message_count:<10} {s.updated_at[:19]:<20}"
        )
    typer.echo("")


@sessions_app.command("show")
def cmd_sessions_show(
    session_id: str = typer.Argument(..., help="Session ID"),
    messages_limit: int = typer.Option(10, "--messages", "-m", help="Number of recent messages"),
):
    """Show session details and recent messages."""
    _, memory, *_ = _init_backend()
    session = memory.get_session(session_id)
    if session is None:
        typer.secho(f"❌  Session '{session_id}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.secho(f"\n💬  Session: {session.name}", bold=True)
    typer.echo(f"  ID:      {session.id}")
    typer.echo(f"  Created: {session.created_at}")
    typer.echo(f"  Updated: {session.updated_at}")
    typer.echo(f"  Messages: {session.message_count}")

    messages = memory.get_messages(session_id, limit=messages_limit)
    if messages:
        typer.secho(f"\n  Recent messages ({len(messages)}):", fg=typer.colors.BRIGHT_BLACK)
        for msg in messages:
            role_icon = "👤" if msg.role == "user" else "🤖"
            preview = msg.content[:120].replace("\n", " ")
            typer.echo(f"  {role_icon} [{msg.role}] {preview}")


@sessions_app.command("delete")
def cmd_sessions_delete(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a session and all its messages."""
    _, memory, *_ = _init_backend()
    session = memory.get_session(session_id)
    if session is None:
        typer.secho(f"❌  Session '{session_id}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not force:
        typer.secho(
            f"⚠️  This will delete '{session.name}' ({session.message_count} messages).",
            fg=typer.colors.YELLOW,
        )
        confirmed = typer.confirm("  Are you sure?")
        if not confirmed:
            typer.secho("  Cancelled.", fg=typer.colors.GREEN)
            return

    memory.delete_session(session_id)
    typer.secho(f"✅  Deleted session: {session.name}", fg=typer.colors.GREEN)


@sessions_app.command("rename")
def cmd_sessions_rename(
    session_id: str = typer.Argument(..., help="Session ID"),
    name: str = typer.Argument(..., help="New session name"),
):
    """Rename a session."""
    _, memory, *_ = _init_backend()
    session = memory.get_session(session_id)
    if session is None:
        typer.secho(f"❌  Session '{session_id}' not found", fg=typer.colors.RED)
        raise typer.Exit(1)

    old_name = session.name
    memory.update_session_name(session_id, name)
    typer.secho(f"✅  Renamed '{old_name}' → '{name}'", fg=typer.colors.GREEN)


# ============================================================
# Knowledge Base Commands
# ============================================================


@knowledge_app.command("list")
def cmd_knowledge_list():
    """List documents in the knowledge base."""
    _, _, _, _, kb, _ = _init_backend()
    docs = kb.list_documents()

    if not docs:
        typer.secho("📚  No documents in knowledge base.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\n📚  Knowledge Base ({len(docs)} documents):", bold=True)
    typer.secho(
        f"  {'ID':<20} {'Filename':<30} {'Chunks':<8} {'Chars':<10}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.secho(
        f"  {'─'*20} {'─'*30} {'─'*8} {'─'*10}",
        fg=typer.colors.BRIGHT_BLACK,
    )
    for doc in docs:
        typer.echo(
            f"  {doc.id:<20} {doc.filename[:28]:<30} {doc.chunk_count:<8} {doc.char_count:<10}"
        )
    typer.echo("")

    # Stats
    stats = kb.get_stats()
    typer.secho(f"  Total chunks: {stats['chunks']}", fg=typer.colors.BRIGHT_BLACK)


@knowledge_app.command("upload")
def cmd_knowledge_upload(
    file_path: str = typer.Argument(
        ..., help="Path to file (.txt, .pdf, .docx)", exists=True,
    ),
):
    """Upload a file to the knowledge base."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        typer.secho(
            f"❌  Unsupported file type: {ext}\n"
            f"    Supported: {', '.join(SUPPORTED_EXTENSIONS.values())}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(f"📤  Uploading '{path.name}'...", fg=typer.colors.CYAN)

    _, _, _, _, kb, _ = _init_backend()

    try:
        file_bytes = path.read_bytes()
        if not file_bytes:
            typer.secho("❌  File is empty!", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        doc_id = kb.add_file(path.name, file_bytes)

        if doc_id:
            stats = kb.get_stats()
            typer.secho(
                f"✅  Uploaded '{path.name}'\n"
                f"    ID: {doc_id}\n"
                f"    Total documents: {stats['documents']}\n"
                f"    Total chunks: {stats['chunks']}",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                f"❌  Could not process '{path.name}'. File may be empty or corrupted.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"❌  Upload failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


# ============================================================
# Plugins Commands
# ============================================================


@plugins_app.command("list")
def cmd_plugins_list():
    """List all available plugins."""
    _, _, _, plugin_loader, _, _ = _init_backend()
    _cmd_plugins_list(plugin_loader)


def _cmd_plugins_list(plugin_loader: PluginLoader):
    """Shared plugin list logic."""
    plugins = plugin_loader.list_plugins()

    if not plugins:
        typer.secho("🧩  No plugins available.", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\n🧩  Plugins ({len(plugins)}):", bold=True)
    for p in plugins:
        typer.echo(f"  • {p['name']}: {p['description']}")
    typer.echo("")


@plugins_app.command("run")
def cmd_plugins_run(
    name: str = typer.Argument(..., help="Plugin name"),
    input_text: str = typer.Argument(..., help="Plugin input"),
):
    """Execute a plugin with the given input."""
    _, _, _, plugin_loader, _, _ = _init_backend()

    plugin = plugin_loader.get(name)
    if plugin is None:
        available = [p["name"] for p in plugin_loader.list_plugins()]
        typer.secho(
            f"❌  Plugin '{name}' not found.\n"
            f"    Available: {', '.join(available) if available else 'none'}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(f"🧩  Running plugin '{name}'...", fg=typer.colors.CYAN)

    try:
        start = time.time()
        result = plugin_loader.execute(name, input_text)
        elapsed = (time.time() - start) * 1000

        if result.success:
            typer.secho(f"\n✅  Result ({elapsed:.0f}ms):", bold=True, fg=typer.colors.GREEN)
            typer.echo(result.output)
        else:
            typer.secho(f"\n❌  Error: {result.error}", fg=typer.colors.RED)

    except Exception as e:
        typer.secho(f"❌  Plugin execution failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


# ============================================================
# Config Commands
# ============================================================


@app.command()
def config(
    show_secrets: bool = typer.Option(
        False, "--show-secrets", "-s",
        help="Show API keys (use with caution!)",
    ),
):
    """Show current application configuration."""
    settings, _, model_router, plugin_loader, kb, workflow = _init_backend()
    _cmd_config_show(settings, show_secrets)


def _cmd_config_show(settings, show_secrets: bool = False):
    """Shared config display logic."""
    typer.secho("\n⚙️  Configuration:", bold=True)

    config_dict = settings.to_dict()
    config_dict["model_provider"] = settings.model_provider

    for key, value in config_dict.items():
        # Mask secrets
        if not show_secrets and any(
            secret in key for secret in ["api_key", "password", "secret", "token"]
        ):
            value = "***" if value else "(not set)"
        typer.echo(f"  {key}: {value}")

    # Additional info
    typer.secho("\n  System:", bold=True)
    typer.echo(f"  provider: {settings.model_provider}")
    typer.echo(f"  model: {model_router.model.model_name}")
    typer.echo(f"  version: {_get_version()}")


# ============================================================
# Version Command
# ============================================================


@app.command()
def version():
    """Show the installed version."""
    typer.echo(f"project-atlas v{_get_version()}")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    app()
