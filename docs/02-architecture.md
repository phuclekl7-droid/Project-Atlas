# 🏗️ Kiến trúc Project Atlas

## Tổng quan

Project Atlas được thiết kế theo kiến trúc **module hóa**, mỗi module độc lập và có thể thay thế:

```
┌────────────────────────────────────────────────────────┐
│                    User Interface                       │
│  ┌──────────────┐    ┌──────────────────────────────┐  │
│  │  app.py       │    │  src/main.py                 │  │
│  │  (Streamlit)  │    │  (CLI)                      │  │
│  └──────┬───────┘    └──────┬───────────────────────┘  │
│         │                   │                          │
└─────────┼───────────────────┼──────────────────────────┘
          │                   │
          ▼                   ▼
┌────────────────────────────────────────────────────────┐
│                  Workflow Orchestrator                   │
│  ┌────────┐    ┌──────────┐    ┌───────────────┐       │
│  │ Memory │───→│ Plugin   │───→│ Model Router   │       │
│  │(SQLite)│    │(extend)  │    │(Mock/Ollama/   │       │
│  └────────┘    └──────────┘    │ OpenAI)        │       │
│                                └───────┬───────┘       │
│  ┌────────┐                           │               │
│  │Knowledge│←──────────────────────────┘               │
│  │(RAG)    │  (enriches LLM prompt)                    │
│  └────────┘                                            │
└────────────────────────────────────────────────────────┘
```

## Modules

### Core (`src/core/`)
Xương sống của dự án: logging, error classes, utilities.
- `setup_logger()` — logging cho mọi module
- `AssistantError`, `ConfigurationError`, `ModelConnectionError`, `PluginExecutionError`
- `truncate_text()`, `format_timestamp()` — utilities

### Settings (`src/settings/`)
Đọc cấu hình từ nhiều nguồn với priority:
1. Environment variables
2. `.env` file
3. `config.json`
4. Default values

### Model Router (`src/model_router/`)
Abstract factory pattern cho LLM providers:
- `BaseModel` — abstract class
- `MockModel` — test không cần API
- `OllamaModel` — local LLM
- `OpenAIModel` — cloud API
- `ModelRouter` — factory routing

### Memory (`src/memory/`)
SQLite-based conversation storage:
- Session CRUD
- Message persistence
- Context loading với limit
- Stats tracking

### Plugin (`src/plugin/`)
Extensible plugin architecture:
- `BasePlugin` ABC
- `PluginLoader` với importlib auto-discovery
- `PluginResult` dataclass

### Plugin mẫu: Calculator (`src/plugins/calculator.py`)
8 phép toán: +, -, *, /, ^, **, sqrt, !, %

### Workflow (`src/workflow/`)
Orchestrator trung tâm:
1. Save user message → Memory
2. Load context → Memory
3. Try plugins → Plugin
4. Call LLM → Model Router
5. Save response → Memory
6. Return result

### Knowledge (`src/knowledge/`)
RAG system với hai backend:
- `ChromaDBKnowledgeBase` — vector search
- `SimpleKnowledgeBase` — keyword fallback
- Text chunking với paragraph/sentence/space boundaries

## Data Flow

### User sends message

```
Input → Memory.save() → Context.load()
→ Plugin.try_all() → (matched?) → Plugin result
                      (not matched) → ModelRouter.generate()
→ Memory.save(response) → Output
```

### Knowledge enrichment

```
User prompt → Search KB → Found chunks?
    → Yes: Enrich prompt with knowledge → Model Router
    → No: Original prompt → Model Router
```

## Error Handling

Mọi lỗi đều được wrap trong các custom exception:
- `ConfigurationError` — sai cấu hình
- `ModelConnectionError` — mất kết nối
- `PluginExecutionError` — lỗi plugin
- `AssistantError` — lỗi chung
