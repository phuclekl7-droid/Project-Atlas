# 📦 Chi tiết các Module

## 🧠 Memory Module

### API

```python
from src.memory import Memory

memory = Memory(db_path="data/memory.db")

# Sessions
session_id = memory.create_session(name="Chat 1")
session = memory.get_session(session_id)
sessions = memory.list_sessions(limit=10)

# Messages
memory.add_message(session_id, "user", "Hello!")
messages = memory.get_messages(session_id, limit=50)
context = memory.get_context(session_id, limit=10)

# Stats
stats = memory.get_total_stats()

# Cleanup
memory.delete_all_sessions()
memory.close()
```

### Schema

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'Chat',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

---

## 🔌 Plugin System

### Tạo Plugin mới

```python
from src.plugin import BasePlugin, PluginResult

class MyPlugin(BasePlugin):
    name = "my_plugin"
    description = "A custom plugin"
    
    def execute(self, input_str: str) -> PluginResult:
        # Xử lý input
        if "hello" in input_str.lower():
            return PluginResult(
                success=True,
                output="Hello from MyPlugin!",
                data={"greeted": True}
            )
        return PluginResult(
            success=False,
            error="Cannot handle this input"
        )
```

### Đăng ký Plugin

Tạo file `src/plugins/my_plugin.py` — `PluginLoader` sẽ tự động discover.

### CalculatorPlugin API

```python
# Phép tính hỗ trợ
2 + 3        # Cộng → 5
10 - 4       # Trừ → 6
6 * 7        # Nhân → 42
20 / 4       # Chia → 5.0
2 ^ 10       # Lũy thừa → 1024
sqrt 16      # Căn bậc 2 → 4.0
5!           # Giai thừa → 120
10 % 3       # Chia lấy dư → 1
```

---

## 🔄 Workflow

### API

```python
from src.workflow import Workflow

workflow = Workflow(
    memory=memory,
    model_router=router,
    plugin_loader=loader,
    knowledge_base=kb,  # Optional
    max_context_messages=10,
)

result = workflow.process(
    user_input="Hello!",
    session_id="abc123",
)

print(result.source)       # "llm" or "plugin"
print(result.output_text)  # Response text
print(result.latency_ms)   # Execution time
print(result.response)     # ModelResponse or None
```

---

## 📚 Knowledge Base

### API

```python
from src.knowledge import create_knowledge_base

# Auto-select: ChromaDB or SimpleKeyword
kb = create_knowledge_base(path="data/knowledge")

# Add document
doc_id = kb.add_text("report.txt", "Q1 revenue grew 20%...")

# Search
results = kb.search("financial results", n_results=3)
for r in results:
    print(f"[{r.filename}] score={r.score:.2f}: {r.content[:100]}")

# Manage
docs = kb.list_documents()
kb.delete_document(doc_id)
kb.delete_all()
stats = kb.get_stats()
# {available: bool, chunks: int, documents: int}
```

### Text Chunking

Thuật toán chia văn bản với 3 mức ưu tiên:
1. **Paragraph boundaries** (`\n\n`)
2. **Sentence boundaries** (`. `, `! `, `? `)
3. **Space boundaries**

Parameters: `chunk_size=500`, `overlap=100`

---

## 🔌 Model Router

### API

```python
from src.settings import load_settings
from src.model_router import ModelRouter

settings = load_settings()
router = ModelRouter(settings)

# Switch provider runtime
settings.model_provider = "openai"
router.__init__(settings)  # Re-initialize

# Generate
response = router.generate("Hello!", context=history)
print(response.text)       # Generated text
print(response.provider)   # "mock" | "ollama" | "openai"
print(response.latency_ms) # Response time
print(response.model_name) # Model identifier
```
