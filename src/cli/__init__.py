"""
CLI package for Project Atlas (Personal AI Assistant).

Provides terminal-based access to all assistant features:
  - Interactive and single-message chat
  - Session management (list, show, delete, rename)
  - Knowledge base management (list, upload)
  - Plugin execution
  - Configuration inspection

Usage:
    python -m src.cli chat "Hello!"
    python -m src.cli chat --interactive
    python -m src.cli sessions list
    python -m src.cli knowledge upload report.pdf
    python -m src.cli plugins list
"""
