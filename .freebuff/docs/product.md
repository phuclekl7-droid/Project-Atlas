## Multi-Model Conversation Routing (v0.7.0)

Added SmartRouter feature: tự động chọn provider (Ollama/OpenAI/Gemini) dựa trên nội dung câu hỏi, giữ cùng session.

### Files created/modified

| File | Change |
|---|---|
| `src/model_router/smart_router.py` | **NEW** — SmartRouter class with keyword-based routing rules |
| `src/memory/__init__.py` | Added `provider` field to Message + DB schema + migration |
| `src/model_router/__init__.py` | Added `generate_with_provider_async()` |
| `src/workflow/__init__.py` | Added `_call_model_with_routing()` + `_call_model_with_routing_async()` |
| `app.py` | Multi-model toggle in sidebar + provider badge on messages |
| `tests/test_smart_router.py` | **NEW** — 30+ tests |

### How SmartRouting works

- 3 keyword categories: **Code** → Ollama, **Creative** → OpenAI, **Analysis** → Gemini
- Short prompts (< 50 chars) → default provider
- Long prompts (> 500 chars) → Gemini
- Weak single keyword match → routed by category

### UI

- Toggle in sidebar: "🧠 Smart Routing" with `st.toggle`
- Model Info card shows ON/OFF status
- Assistant messages show `provider-badge` tags (e.g., [OLLAMA], [OPENAI])
- Provider stored in DB for session persistence

### Known limitation

Streaming (`process_stream`) always uses default provider's stream even with routing enabled (provider name is stored for display but actual generation goes through default).
