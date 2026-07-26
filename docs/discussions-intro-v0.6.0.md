---
title: "🚀 Project Atlas v0.6.0 — Async Support + Web Search + Docker CI/CD"
labels: ["announcement", "release"]
---

<div align="center">

# 🤖 **Project Atlas v0.6.0**

**Personal AI Assistant — Modular, Offline-capable, Cloud-ready**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://phuclekl7-droid-project-atlas.streamlit.app)
[![GitHub Release](https://img.shields.io/github/v/release/phuclekl7-droid/Project-Atlas?include_prereleases&label=version)](https://github.com/phuclekl7-droid/Project-Atlas/releases)
[![Tests](https://img.shields.io/github/actions/workflow/status/phuclekl7-droid/Project-Atlas/test.yml?label=tests)](https://github.com/phuclekl7-droid/Project-Atlas/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)

---

</div>

## 📖 Giới thiệu

**Project Atlas** là một trợ lý AI cá nhân **mã nguồn mở**, được thiết kế theo hướng **module hóa** để dễ phát triển và mở rộng. 

Bạn có thể chạy Atlas **hoàn toàn offline** với Ollama (model nhẹ ~1B tham số), hoặc kết nối **OpenAI API** để có câu trả lời thông minh hơn — và chuyển đổi giữa hai chế độ chỉ bằng một cú click!

---

## 🆕 Tính năng mới trong v0.6.0

### ⚡ Async Model Calls (Non-blocking API)

Toàn bộ Model Router đã được **refactor thành async** với `aiohttp`:

```python
# Cũ — blocking
response = router.generate("Hello!")

# Mới — non-blocking 🚀
response = await router.generate_async("Hello!")

# Gửi nhiều câu hỏi song song!
q1, q2, q3 = await asyncio.gather(
    router.generate_async("Question 1"),
    router.generate_async("Question 2"),
    router.generate_async("Question 3"),
)
```

| Model | Sync | Async |
|---|---|---|
| **Mock** | `time.sleep(0.3)` | `asyncio.sleep(0.3)` |
| **Ollama** | `requests.post()` | `aiohttp session.post()` |
| **OpenAI** | `requests.post()` | `aiohttp session.post()` |

> ⏱️ Async giúp UI không bị đơ khi chờ API — đặc biệt quan trọng trên Streamlit Cloud!

### 🔍 Web Search Plugin (DuckDuckGo — không cần API key)

Plugin tìm kiếm web **tích hợp sẵn vào Workflow**:

```
User hỏi: "Thủ đô của Pháp là gì?"
    │
    ├── 1. enrich_with_knowledge() → search Knowledge Base
    ├── 2. enrich_with_web_search() → auto-detect câu hỏi
    │       └── DuckDuckGo → 3 kết quả đầu → inject vào prompt
    └── 3. Gửi prompt đã enriched → LLM trả lời dựa trên web!
```

- ✅ **Zero API key** — dùng DuckDuckGo HTML search endpoint
- ✅ **Auto-detect** — tự động search khi phát hiện câu hỏi (`?`, *what/why/how*...)
- ✅ **Markdown format** — kết quả đẹp, dễ đọc

### 🐳 Docker CI/CD — Auto-build on Tag

GitHub Actions workflow tự động build Docker image khi push tag:

```
git tag v0.6.0
git push origin v0.6.0
    │
    ├── Job 1: 🔍 pytest (chỉ build nếu pass)
    └── Job 2: 🐳 Build & Push
        ├── Docker Hub → project-atlas:v0.6.0
        └── GHCR       → ghcr.io/phuclekl7-droid/project-atlas:v0.6.0
```

---

## 📦 Modules Overview

| Module | Công nghệ | Trạng thái |
|---|---|---|
| **Core** | Logging, errors, utilities, caching | ✅ Tested |
| **Settings** | .env, config.json, CLI args | ✅ Tested |
| **Model Router** | Mock / Ollama / OpenAI (sync + async) | ✅ Tested |
| **Memory** | SQLite with session management | ✅ Tested + Fixed |
| **Plugin** | Calculator + WebSearch (auto-discovery) | ✅ Tested |
| **Workflow** | Orchestrator + knowledge + web enrichment | ✅ Tested |
| **Knowledge** | ChromaDB + keyword fallback | ✅ Tested |
| **Web UI** | Streamlit — dark theme, sidebar | ✅ Implemented |
| **CLI** | Slash commands, provider switching | ✅ Implemented |
| **Caching** | TTL cache cho KB + model responses | ✅ Implemented |
| **Async** | aiohttp non-blocking model calls | ✅ Implemented |
| **Docker** | Multi-stage, non-root, healthcheck | ✅ Ready |

---

## 🧪 Testing

```
292+ tests — tất cả đều pass! ✅

tests/
├── test_core.py                ~30 tests
├── test_settings.py            ~25 tests
├── test_model_router.py        ~30 tests
├── test_model_router_async.py  ~20 tests  ← Mới!
├── test_memory.py              ~27 tests
├── test_plugin.py              ~40 tests
├── test_workflow.py            ~20 tests
├── test_knowledge.py           ~55 tests
├── test_cache.py               ~25 tests  ← Mới!
├── test_web_search.py          ~20 tests  ← Mới!
```

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/phuclekl7-droid/Project-Atlas.git
cd Project-Atlas

# 2. Cài đặt
pip install -r requirements.txt
cp .env.example .env

# 3. Chạy
streamlit run app.py
```

**Deploy 1-click**: https://phuclekl7-droid-project-atlas.streamlit.app

---

## 🗺️ Roadmap

| Phase | Tính năng | Trạng thái |
|---|---|---|
| ✅ Phase 1 | Foundation (core, settings, model_router) | Done |
| ✅ Phase 2 | Plugin + Workflow Orchestrator | Done |
| ✅ Phase 3 | Knowledge RAG (ChromaDB) | Done |
| ✅ Phase 4 | Web UI, Caching, Async, Docker, Community | Done |
| 🔄 Phase 5 | Async Workflow, Integration tests | In progress |
| ⏳ Phase 6 | Multi-modal, WebSocket streaming, Persistent storage | Future |

---

## 🤝 Tham gia đóng góp

Project Atlas là mã nguồn mở và rất hoan nghênh mọi đóng góp!

- 🐛 **Báo lỗi**: [Open an Issue](https://github.com/phuclekl7-droid/Project-Atlas/issues/new?template=bug_report.md)
- 💡 **Gợi ý tính năng**: [Feature Request](https://github.com/phuclekl7-droid/Project-Atlas/issues/new?template=feature_request.md)
- 📖 **Hướng dẫn**: [CONTRIBUTING.md](https://github.com/phuclekl7-droid/Project-Atlas/blob/main/CONTRIBUTING.md)
- 💬 **Thảo luận**: Ngay tại đây — Discussions!

---

<div align="center">

**Made with ❤️ for the open-source community**

⭐ Star repo nếu bạn thấy hữu ích! ⭐

[GitHub](https://github.com/phuclekl7-droid/Project-Atlas) · [Streamlit App](https://phuclekl7-droid-project-atlas.streamlit.app) · [Docs](https://github.com/phuclekl7-droid/Project-Atlas/tree/main/docs)

</div>
