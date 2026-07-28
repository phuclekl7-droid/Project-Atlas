# Changelog

## v0.6.0-alpha (Async Workflow + Python 3.11 Compat)

**Release date:** 2026-07-27

### 🆕 Async Workflow Processor
- **`Workflow.process_async()`**: Full async pipeline — `Memory → Plugin → Model Router → Memory`
  - Uses `ModelRouter.generate_async()` for non-blocking API calls (aiohttp cho Ollama/OpenAI)
  - Plugin execution giữ sync (fast local operation), phần còn lại chạy async
  - Giữ `process()` sync cho backward compatibility
- **10 new tests** cho async pipeline (`TestWorkflowProcessAsync`, `TestWorkflowProcessStream`)
  - Test LLM greeting, plugin routing, memory saving, empty input, stats tracking
- **`pytest.ini`**: Thêm `asyncio_mode = auto` để hỗ trợ async tests

### 🐛 Bug Fix
- **Python 3.11 f-string compatibility**: Sửa nested quotes `f"{"... "}"` → `f"{'...'}"` trong `_call_model` và `_call_model_async` (Dockerfile dùng `python:3.11-slim`)

### ✅ Verification
- 28 workflow tests pass (18 sync + 5 async + 5 streaming)
- Backward compatible: `process()` sync giữ nguyên, không thay đổi API

---

## v0.5.2-alpha (Community + Deploy) — Push lên GitHub + Streamlit Cloud

**Release date:** 2026-07-27

### 🐛 Bug Fix
- **SQLite threading error on Streamlit Cloud**: Added `check_same_thread=False` to `sqlite3.connect()` in `src/memory/__init__.py` – fix cho lỗi "SQLite objects created in a thread can only be used in that same thread"

### 🆕 Community Infrastructure
- **Issue templates**: Bug Report (`bug_report.md`) + Feature Request (`feature_request.md`) + config.yml
- **Pull Request template**: Checklist format + CI requirements
- **`CONTRIBUTING.md`**: Hướng dẫn đóng góp 15 trang (branch naming, commit format, code style, testing, PR process)
- **`CODE_OF_CONDUCT.md`**: Contributor Covenant 2.1
- **`SECURITY.md`**: Chính sách bảo mật + báo cáo lỗ hổng

### 📚 Wiki Documentation (`docs/`)
- `01-getting-started.md`: Hướng dẫn cài đặt từ A-Z
- `02-architecture.md`: Kiến trúc module + data flow diagrams
- `03-modules-api.md`: API reference cho Memory, Plugin, Workflow, Knowledge
- `04-contributing.md`: Tóm tắt đóng góp nhanh
- `05-faq.md`: 15+ câu hỏi thường gặp

### 🚀 GitHub + Streamlit Cloud
- **Git push**: Code đã push lên `phuclekl7-droid/Project-Atlas`
- **GitHub Actions**: CI workflow đã chạy thành công (1m 34s)
- **Streamlit Cloud**: Deployed tại https://phuclekl7-droid-project-atlas.streamlit.app
- **GitHub Release**: Template release notes v0.5.0-alpha sẵn sàng
- **README badges**: GitHub Actions + Python version + Streamlit App badges

### 📊 Project Progress
| Hạng mục | Trạng thái |
|---|---|
| Code push lên GitHub | ✅ Done |
| CI/CD (GitHub Actions) | ✅ Running |
| Streamlit Cloud deploy | ✅ Live |
| Issue/PR templates | ✅ Ready |
| Contributing guide | ✅ Ready |
| Wiki docs | ✅ 5 pages |
| SECURITY.md | ✅ Ready |

---

## v0.5.1-alpha (Deployment) — Streamlit Cloud + GitHub

**Release date:** 2026-07-27

### 🆕 New
- **`.streamlit/config.toml`**: Streamlit Cloud config (dark theme, max upload 10MB)
- **`README.md`**: Full deployment guide A-Z (Git → GitHub → Streamlit Cloud)
- **`.env.example`**: Updated secrets template for Cloud dashboard

### 🔧 Changed
- `.gitignore`: Now tracks `.streamlit/config.toml` but ignores `secrets.toml` and `*.local.toml`

### 📊 Deployment Ready
| Công việc | Trạng thái |
|---|---|
| Git init | ✅ Hướng dẫn chi tiết |
| GitHub push | ✅ Step-by-step |
| Streamlit Cloud | ✅ Config file sẵn |
| Secrets management | ✅ .env.example template |

---

## v0.5.0-alpha (Knowledge Module) — RAG với ChromaDB

**Release date:** 2026-07-27

### 🆕 New Features
- **Knowledge Module (`src/knowledge/`)**: RAG (Retrieval-Augmented Generation) system
  - Text chunking with paragraph/sentence/character boundary detection
  - `ChromaDBKnowledgeBase`: Full ChromaDB vector store with cosine similarity search
  - `SimpleKnowledgeBase`: Keyword-based fallback when ChromaDB not installed
  - `create_knowledge_base()`: Factory function auto-selects the right backend
  - Knowledge context auto-injected into LLM prompts during Workflow

- **Streamlit Knowledge UI**: Upload `.txt` files, browse documents, search, and delete from sidebar

- **Knowledge Stats**: Document count, chunk count visible in sidebar

### 🔧 Changed
- **Workflow**: Now accepts `knowledge_base` parameter; enriches LLM prompts with relevant knowledge chunks
- **`app.py`**: Knowledge Base section in sidebar, file upload, document management
- **`main.py`**: Initializes `knowledge_base` and passes to Workflow
- **`requirements.txt`**: Added `chromadb>=0.5.0`

### 🧪 Tests
- `tests/test_knowledge.py`: 55+ tests covering:
  - `chunk_text()`: empty, short, paragraph, sentence, overlap, long text, normalization
  - KnowledgeDoc / SearchResult dataclasses
  - SimpleKnowledgeBase: add, search, list, delete, stats
  - Workflow integration: enrichment, plugin routing, stats tracking
  - Edge cases: empty text, no match, empty KB, duplicate docs

### 📊 Project Progress
| Module | Status |
|---|---|
| Core | ✅ Tested |
| Settings | ✅ Tested |
| Model Router | ✅ Tested |
| Memory | ✅ Tested |
| Plugin | ✅ Implemented + Tested |
| Workflow | ✅ Implemented + Tested |
| **Knowledge** | ✅ **Implemented + Tested** |
| CI/CD | ✅ Set up |

---

## v0.4.0-alpha (Plugin System)

**Release date:** 2026-07-27

### 🆕 New Features
- **Plugin System (`src/plugin/`)**: Extensible plugin architecture
  - `BasePlugin` abstract base class with execute pattern
  - `PluginLoader` with `importlib`-based auto-discovery
  - `PluginResult` dataclass for standardized plugin output
  - `PluginExecutionError` for error handling

- **CalculatorPlugin (`src/plugins/calculator.py`)**: 8 operations
  - Addition, subtraction, multiplication, division
  - Power (`^`, `**`), square root (`sqrt`), factorial (`!`), modulo (`%`)
  - Error handling: division by zero, negative sqrt, large factorials

- **Streamlit Plugin UI**: Plugin list, executor input, results via toast notifications

### 🔧 Changed
- **Workflow**: Auto-routes matching inputs to plugins before LLM call
- **`app.py`**: Plugin section in sidebar with executor
- **`main.py`**: Uses Workflow orchestrator (was direct module calls)

### 🧪 Tests
- `tests/test_plugin.py`: 40+ tests (BasePlugin, PluginResult, PluginLoader, CalculatorPlugin)
- `tests/test_workflow.py`: 20+ tests (Workflow init, process, plugin routing, stats)

---

## v0.3.1-alpha (CI/CD Setup)

**Release date:** 2026-07-27

### 🆕 New
- **GitHub Actions CI**: `.github/workflows/test.yml` runs pytest + flake8 on push/PR
  - Matrix: Python 3.10, 3.11, 3.12
  - concurrency: auto-cancel stale runs
- **Pre-commit hooks**: `.pre-commit-config.yaml` with 10 hooks
  - Basic: whitespace, EOF, YAML/JSON/TOML check, merge conflict, private keys
  - Formatting: black (auto-format), isort (import sort)
  - Quality: flake8 (lint), mypy (type check), bandit (security)

### 🔧 Changed
- `.gitignore`: Added `.db`, `.streamlit/`, `.pytest_cache/`, `.mypy_cache/`, coverage
- `requirements.txt`: Added `pre-commit`, `flake8`, `black`, `isort`, `mypy`, `bandit`, `types-requests`

---

## v0.3.0-alpha (Web UI)

**Release date:** 2026-07-27

### 🆕 New Features
- **Streamlit Web UI (`app.py`)**: Chat interface replacing CLI
  - Chat bubbles with avatars, gradient styling, fade-in animations
  - Auto-scroll with MutationObserver
  - Welcome screen, loading spinner via pending_prompt pattern
  - Custom CSS dark theme with gradient header

- **Sidebar Features**:
  - Model Provider selector (Mock / Ollama / OpenAI)
  - Model Info card with provider badge, model name, context size, latency
  - Session management (create, switch, delete all)
  - Memory Stats cards (sessions + messages count)
  - Toast notifications for success/error

### 🔧 Changed
- `requirements.txt`: Added `streamlit>=1.35.0`
- Replaces CLI as primary interface (CLI still available via `python src/main.py`)

---

## v0.2.0-alpha (Memory + Tests)

**Release date:** 2026-07-27

### 🆕 New Features
- **Memory Module (`src/memory/`)**: SQLite-based conversation storage
  - Session management (create, list, switch, delete)
  - Message persistence with auto-timestamps
  - Context loading (`get_context()` with limit parameter)
  - Stats tracking (session count, message count)
  - Context injection into ModelRouter

- **Unit Tests**: pytest framework with 112+ tests
  - `tests/test_core.py`: Core utilities, error classes, timestamp formatting
  - `tests/test_settings.py`: Settings loading, env vars, config.json, cli args
  - `tests/test_model_router.py`: Mock/Ollama/OpenAI models, context injection, error handling
  - `tests/conftest.py`: Shared fixtures

- **Pytest Configuration**: `pytest.ini`, `conftest.py` with temp directory and monkeypatch

### 🔧 Changed
- `src/model_router/__init__.py`: Added context injection for conversation history
- `src/main.py`: Sends conversation context when calling model
- `STATE.json`: Updated progress to 45%

---

## v0.1.0-alpha (Initial Release)

**Release date:** 2026-07-27

### 🆕 Initial Implementation
- **Core Module (`src/core/`)**: Logging, custom error classes, utility functions
- **Settings Module (`src/settings/`)**: Loads configuration from .env, config.json, CLI args
  - Supports Mock, Ollama, OpenAI providers
  - Input validation with `_safe_int`, `_safe_float`
- **Model Router (`src/model_router/`)**: Provider abstraction layer
  - `BaseModel` ABC, `MockModel`, `OllamaModel` (local), `OpenAIModel` (API)
  - `ModelRouter` factory pattern — switch providers at runtime
  - Standardized `ModelResponse` dataclass
- **CLI (`src/main.py`)**: Interactive terminal interface
  - Slash commands: /help, /settings, /mock, /ollama, /openai, /new, /sessions, /exit
  - Connection test on startup
  - Provider switching with rollback on error
