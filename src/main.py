"""
Personal AI Assistant - CLI Entry Point

Uses Workflow orchestrator to integrate Memory → Plugin → Model Router → Memory.
Alternative to the Streamlit UI (app.py).

Run with: python src/main.py
"""

import sys

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    setup_logger,
)
from src.knowledge import create_knowledge_base
from src.memory import Memory
from src.model_router import ModelRouter, ModelResponse
from src.plugin import PluginLoader
from src.settings import load_settings
from src.workflow import Workflow, WorkflowResult

# ── Globally configure root logger ──
logger = setup_logger("main")


def print_banner() -> None:
    """Display a startup banner."""
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║       🤖 Personal AI Assistant v0.5.0       ║")
    print("║     Tinh gọn · Cá nhân · Mở rộng được       ║")
    print("╚══════════════════════════════════════════════╝")
    print()


def print_help() -> None:
    """Display available commands."""
    print()
    print("  📋 Commands:")
    print("    /help      - Show this help message")
    print("    /mock      - Switch to Mock model (testing)")
    print("    /ollama    - Switch to Ollama (local)")
    print("    /openai    - Switch to OpenAI")
    print("    /settings  - Show current configuration")
    print("    /stats     - Show workflow statistics")
    print("    /new       - Start a new conversation session")
    print("    /sessions  - List all saved sessions")
    print("    /memory    - Show memory usage statistics")
    print("    /forget    - Delete ALL sessions (clear memory)")
    print("    /clear     - Clear screen")
    print("    /exit      - Exit the assistant")
    print()


def print_result(result: WorkflowResult) -> None:
    """Pretty-print a WorkflowResult."""
    if result.source == "plugin":
        print()
        print(f"  [🧩 Plugin | {result.latency_ms:.0f}ms]")
        print()
        for line in result.output_text.split("\n"):
            print(f"  {line}")
        print()
    else:
        resp = result.response
        provider_tag = {
            "mock": "🔌 Mock",
            "ollama": "🦙 Ollama",
            "openai": "🔵 OpenAI",
        }.get(resp.provider, resp.provider)

        print()
        print(f"  [{provider_tag} | {resp.model_name}]")
        if resp.latency_ms:
            print(f"  ⏱  {resp.latency_ms:.0f}ms")
        print()
        for line in resp.text.split("\n"):
            print(f"  {line}")
        print()


def print_workflow_stats(workflow: Workflow) -> None:
    """Display workflow statistics."""
    stats = workflow.get_stats()
    print(f"\n  📊 Workflow Stats:")
    print(f"     Total processed:  {stats['total_processed']}")
    print(f"     LLM calls:       {stats['total_llm_calls']}")
    print(f"     Plugin calls:    {stats['total_plugin_calls']}")
    print(f"     Context limit:   {stats['context_limit']} messages")
    print()


def interactive_loop(workflow: Workflow, memory: Memory, session_id: str, settings, model_router: ModelRouter) -> None:
    """
    Main interactive loop using Workflow orchestrator.
    """
    print_help()
    print("  Nhập tin nhắn của bạn (hoặc /exit để thoát):")
    print()

    while True:
        try:
            user_input = input("  ❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            logger.info("Received exit signal")
            break

        if not user_input:
            continue

        # ── Handle commands ──
        if user_input.startswith("/"):
            session_id = handle_command(user_input, model_router, memory, session_id, settings, workflow)
            continue

        # ── Execute Workflow ──
        try:
            logger.info(f"User: {user_input[:100]}")
            result = workflow.process(
                user_input=user_input,
                session_id=session_id,
                max_context=settings.max_context_messages,
            )
            print_result(result)
            logger.info(f"Workflow: source={result.source}, latency={result.latency_ms:.0f}ms")

        except ConfigurationError as e:
            print(f"\n  ⚠️  Configuration Error: {e.message}\n")
            logger.error(str(e))
        except ModelConnectionError as e:
            print(f"\n  🔌 Connection Error: {e.message}\n")
            if e.details:
                print(f"  Details: {e.details}\n")
            logger.error(str(e))
        except AssistantError as e:
            print(f"\n  ❌ Error: {e.message}\n")
            logger.error(str(e))
        except Exception as e:
            print(f"\n  ❌ Unexpected error: {e}\n")
            logger.exception("Unhandled exception in main loop")


def handle_command(cmd: str, model_router: ModelRouter, memory: Memory, current_session_id: str, settings, workflow: Workflow) -> str:
    """Handle a slash command. Returns the (possibly new) session_id."""
    cmd = cmd.lower()

    if cmd == "/exit":
        memory.close()
        print("\n  👋 Tạm biệt! Hẹn gặp lại!\n")
        sys.exit(0)

    elif cmd == "/help":
        print_help()

    elif cmd == "/clear":
        print("\n" * 3)

    elif cmd == "/settings":
        print(f"\n  📋 Current Settings:")
        print(f"     Provider:          {settings.model_provider}")
        print(f"     Model:             {model_router.model.model_name}")
        print(f"     Log level:         {settings.log_level}")
        print(f"     Memory DB:         {settings.memory_path}")
        print(f"     Max context msgs:  {settings.max_context_messages}")
        print()

    elif cmd == "/stats":
        print_workflow_stats(workflow)

    elif cmd in ("/mock", "/ollama", "/openai"):
        provider_map = {"/mock": "mock", "/ollama": "ollama", "/openai": "openai"}
        new_provider = provider_map[cmd]
        old_provider = settings.model_provider
        settings.model_provider = new_provider

        try:
            model_router.__init__(settings)
            # Re-create workflow with new model router
            plugin_loader = getattr(workflow, "plugin_loader", None)
            workflow.__init__(
                memory=memory,
                model_router=model_router,
                plugin_loader=plugin_loader,
                max_context_messages=settings.max_context_messages,
            )
            print(f"\n  ✅ Switched from '{old_provider}' to '{new_provider}'\n")
        except (ConfigurationError, AssistantError) as e:
            settings.model_provider = old_provider
            print(f"\n  ❌ Failed to switch: {e.message}\n")

    elif cmd == "/new":
        name_input = input("  📝 Tên cho session này (Enter để bỏ qua): ").strip()
        name = name_input if name_input else None
        new_id = memory.create_session(name=name)
        session = memory.get_session(new_id)
        print(f"\n  ✅ Đã tạo session mới: {session.name} ({new_id})\n")
        return new_id

    elif cmd == "/sessions":
        sessions = memory.list_sessions()
        if not sessions:
            print("\n  📭 Không có session nào.\n")
        else:
            print(f"\n  📋 Các session ({len(sessions)}):")
            print(f"  {'ID':<10} {'Name':<25} {'Messages':<10} {'Last updated'}")
            print(f"  {'-'*10} {'-'*25} {'-'*10} {'-'*20}")
            for s in sessions:
                marker = " ◀" if s.id == current_session_id else ""
                print(f"  {s.id:<10} {s.name:<25} {s.message_count:<10} {s.updated_at[5:16]}{marker}")
            print()
            print(f"  💡 Dùng /new để tạo session mới.")
            print()

    elif cmd == "/memory":
        stats = memory.get_total_stats()
        print(f"\n  🧠 Memory Statistics:")
        print(f"     Database:     {stats['db_path']}")
        print(f"     Sessions:     {stats['sessions']}")
        print(f"     Messages:     {stats['messages']}")
        print(f"     Current session: {current_session_id}")
        print()

    elif cmd == "/forget":
        confirm = input("  ⚠️  Bạn có chắc muốn xóa TẤT CẢ dữ liệu? (yes/N): ").strip().lower()
        if confirm == "yes":
            count = memory.delete_all_sessions()
            new_id = memory.create_session(name="Main Chat")
            print(f"\n  🗑️  Đã xóa {count} session. Bắt đầu session mới: {new_id}\n")
            return new_id
        else:
            print("\n  ✅ Đã hủy.\n")

    else:
        print(f"\n  Unknown command: {cmd}. Type /help for available commands.\n")

    return current_session_id


def main() -> None:
    """Main entry point."""
    print_banner()

    # ── Initialize Settings ──
    try:
        settings = load_settings()
        logger.info(f"Settings loaded: provider={settings.model_provider}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n  ❌ Configuration Error: {e.message}")
        if e.details:
            print(f"     Details: {e.details}")
        print()
        print("  💡 Tạo file .env từ .env.example và cấu hình đúng các thông số.")
        print()
        sys.exit(1)

    # ── Initialize Memory ──
    try:
        memory = Memory(db_path=settings.memory_path)
    except Exception as e:
        logger.error(f"Failed to initialize memory: {e}")
        print(f"\n  ❌ Failed to initialize memory database: {e}")
        print()
        sys.exit(1)

    # ── Get or create active session ──
    sessions = memory.list_sessions(limit=1)
    if sessions:
        session_id = sessions[0].id
        logger.info(f"Resuming session: {session_id}")
        print(f"  📝 Tiếp tục session: {sessions[0].name} ({sessions[0].message_count} messages)")
    else:
        session_id = memory.create_session(name="Main Chat")
        logger.info(f"Created new session: {session_id}")

    # ── Initialize Model Router ──
    try:
        model_router = ModelRouter(settings)
        logger.info(f"ModelRouter initialized: {model_router}")
    except (ConfigurationError, AssistantError) as e:
        logger.error(f"Failed to initialize model router: {e}")
        print(f"\n  ❌ Failed to initialize AI model: {e.message}")
        print()
        sys.exit(1)

    # ── Initialize Plugin Loader ──
    plugin_loader = PluginLoader(plugin_package="src.plugins")
    plugins = plugin_loader.discover()
    logger.info(f"PluginLoader: found {len(plugins)} plugins")

    # ── Initialize Knowledge Base ──
    knowledge_base = create_knowledge_base(path="data/knowledge")
    logger.info(f"KnowledgeBase: {knowledge_base.__class__.__name__}, available={knowledge_base.available}")

    # ── Initialize Workflow ──
    workflow = Workflow(
        memory=memory,
        model_router=model_router,
        plugin_loader=plugin_loader,
        knowledge_base=knowledge_base,
        max_context_messages=settings.max_context_messages,
    )

    # ── Quick test the connection ──
    if settings.model_provider != "mock":
        print("  🔄 Đang kiểm tra kết nối...")
        try:
            result = workflow.process("Hello! Say 'ok' if you can hear me.", session_id=session_id)
            print(f"  ✅ Kết nối thành công! ({result.latency_ms:.0f}ms)\n")
        except ModelConnectionError as e:
            print(f"  ⚠️  Không thể kết nối: {e.message}")
            print("  Tôi sẽ chuyển sang chế độ Mock để bạn có thể test các tính năng khác.\n")
            settings.model_provider = "mock"
            model_router = ModelRouter(settings)
            workflow = Workflow(memory=memory, model_router=model_router, plugin_loader=plugin_loader)

    # ── Start interactive loop ──
    print("  Nhập tin nhắn của bạn để bắt đầu trò chuyện!")
    print()
    interactive_loop(workflow, memory, session_id, settings, model_router)


if __name__ == "__main__":
    main()
