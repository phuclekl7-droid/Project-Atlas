> [!IMPORTANT]
> **THÔNG ĐIỆP QUAN TRỌNG DÀNH CHO AI ĐANG ĐỌC FILE NÀY**
> Bạn là một phần của chuỗi tiếp sức gồm nhiều AI khác nhau cùng xây dựng dự án này.
> - **TRÁCH NHIỆM CỦA BẠN:** Trước khi kết thúc phiên làm việc, bạn **BẮT BUỘC** phải ghi lại những gì bạn đã làm, định hướng tiếp theo, và cập nhật lại toàn bộ file `NEXT_AI.md` này cho AI thế hệ kế tiếp.
> - Nếu bạn thay đổi kế hoạch hoặc kiến trúc, hãy cập nhật `PROJECT_MEMORY.md`.

# 1. Tóm tắt dự án

- **Tên dự án**: Project Atlas
- **Repo**: https://github.com/phuclekl7-droid/Project-Atlas
- **Streamlit Cloud**: https://phuclekl7-droid-project-atlas.streamlit.app
- **Docker Hub**: `${{ secrets.DOCKER_USERNAME }}/project-atlas` (GHCR: `ghcr.io/phuclekl7-droid/project-atlas`)
- **Mô tả**: Trợ lý AI cá nhân tinh gọn, module hóa, chạy được offline (Ollama) hoặc online (OpenAI).
- **Tiến độ hiện tại**: **98%**
- **Version**: v0.6.0-alpha

## Modules đã hoàn thành

| Module | Status | Ghi chú |
|---|---|---|
| Core | ✅ Tested | Logging, errors, utilities, caching layer |
| Settings | ✅ Tested | .env, config.json, CLI args |
| Model Router | ✅ Tested + Async | Mock, Ollama, OpenAI + async_generate() |
| Memory | ✅ Tested + Fixed | SQLite, `check_same_thread=False` cho Cloud |
| Plugin | ✅ Tested | BasePlugin, PluginLoader, CalculatorPlugin, WebSearchPlugin |
| Workflow | ✅ Tested | Orchestrator + knowledge + web search enrichment |
| Knowledge | ✅ Tested | ChromaDB + SimpleKnowledgeBase fallback |
| Streamlit UI | ✅ Implemented | Chat + sidebar + dark theme |
| CLI | ✅ Implemented | Slash commands + provider switching |
| CI/CD | ✅ Running | GitHub Actions (test + docker build) |
| Deployment | ✅ Live | Streamlit Cloud + Docker + GHCR |
| Community | ✅ Setup | Issue/PR templates, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY |
| Docs | ✅ Setup | 5 Wiki pages + comprehensive README |
| Caching | ✅ Implemented | TTL cache cho knowledge search + model responses |
| Async Support | ✅ Implemented | aiohttp cho non-blocking API calls |

# 2. Những gì đã hoàn thành gần đây

## Web Search Plugin (`src/plugins/web_search.py`)
- Dùng DuckDuckGo HTML API (không cần API key)
- Regex-based HTML parsing với fallback warning khi structure thay đổi
- Format kết quả dạng markdown (title, snippet, URL)
- 20+ tests

## Auto Web Search Enrichment (trong Workflow)
- `Workflow._enrich_with_web_search()` — auto-detect câu hỏi (có `?`, starts with *what/why/how*...)
- Tự động search DuckDuckGo và inject 3 kết quả đầu vào LLM prompt
- Skip greeting và câu ngắn (dưới 3 từ)
- Hoạt động cùng với knowledge enrichment (cả hai đều được inject)

## Async Model Calls (`src/model_router/__init__.py`)
- `BaseModel.async_generate()` — abstract method, fallback về `asyncio.to_thread()`
- `MockModel.async_generate()` — dùng `asyncio.sleep(0.3)` thay `time.sleep(0.3)`
- `OllamaModel.async_generate()` — dùng `aiohttp` thay `requests`
- `OpenAIModel.async_generate()` — dùng `aiohttp` thay `requests`
- `ModelRouter.generate_async()` — support cache giống sync
- Refactored code: `_build_payload()`, `_parse_response()`, `_build_headers()` dùng chung cho sync + async
- Thêm `aiohttp>=3.9.0` + `types-aiohttp>=3.9.0` vào requirements.txt
- 20+ tests (sync/async consistency, parallel calls)

## Docker Auto-build Workflow (`.github/workflows/docker.yml`)
- Trigger: push tag `v*`
- Job 1: Chạy pytest (chỉ build nếu tests pass)
- Job 2: Build + Push Docker image
- Dual registry: Docker Hub (`${{ secrets.DOCKER_USERNAME }}/project-atlas`) + GHCR
- Tags: `v0.6.0`, `v0.6`, `latest`
- Cache: GitHub Actions cache (`type=gha`) cho build nhanh hơn

# 3. Những gì còn dang dở

**Phase 5: Polish & Production (gần hoàn thành)**

- **Async Workflow processor**: Thêm `process_async()` vào Workflow để tận dụng async model calls
- **GitHub Discussions**: Đã setup template nhưng chưa có bài post đầu tiên
- **GitHub Release**: Cần tạo official release v0.6.0-alpha

**Phase 6: Advanced Features (chưa bắt đầu)**

- **Multi-modal**: Hỗ trợ hình ảnh, audio (GPT-4V)
- **LangChain integration**: Agents thay vì plugin tự viết
- **Persistent storage**: PostgreSQL support cho production deploy

# 4. Bug đã biết

- **Streamlit Cloud ephemeral storage**: SQLite + ChromaDB data reset ~24h (đã document)
- **Ollama không chạy trên Cloud**: Cần GPU local (đã document)
- **Web search HTML parsing fragile**: DuckDuckGo có thể thay đổi HTML structure bất kỳ lúc nào (đã có fallback warning)

# 5. Nợ kỹ thuật (Technical Debt)

- **Integration tests**: Chưa có test cho full pipeline async (Model → Workflow → UI)
- **main.py CLI**: Chưa có test cho interactive loop
- **Error handling**: Một số except quá broad (bare `except Exception`) trong `_try_plugin`
- **Thread safety**: `check_same_thread=False` là workaround, không phải solution

# 6. Đề xuất cho AI tiếp theo

**Priority 1:** Async Workflow processor — thêm `process_async()` vào Workflow để tận dụng `model_router.generate_async()`.

**Priority 2:** GitHub Release v0.6.0-alpha — tạo official release với release notes.

**Priority 3:** Integration tests — test full async pipeline (Model → Workflow).

**Priority 4:** GitHub Discussions — post bài introduction đầu tiên.

# 7. Chọn DUY NHẤT MỘT nhiệm vụ

Nhiệm vụ có tác động lớn nhất hiện tại: **Async Workflow processor**.

Giải thích: Đã có async model calls ở ModelRouter, nhưng Workflow.process() vẫn dùng sync. Thêm `process_async()` sẽ cho phép toàn bộ pipeline chạy non-blocking, giúp UI mượt mà hơn trên Streamlit Cloud.

# 8. Prompt cho AI tiếp theo (TẬP TRUNG vào MỘT nhiệm vụ)

```markdown
## Nhiệm vụ: Async Workflow processor

Đọc PROJECT_MEMORY.md, STATE.json, NEXT_AI.md. Đây là nhiệm vụ DUY NHẤT của bạn.

### Bước 0 — Baseline test
```powershell
cd D:\personal_ai_assistant
pip install -r requirements.txt
python -m pytest tests/ -v --tb=short
# Ghi lại số tests pass (dự kiến ~290+)
```

### Bước 1 — Thêm process_async() vào Workflow
File: src/workflow/__init__.py
- Thêm `async process_async()` method (tương tự process() nhưng dùng await)
- Gọi `await self.model_router.generate_async()` thay vì `self.model_router.generate()`
- Web search + knowledge enrichment cũng nên chạy async (nếu có thể)
- Giữ nguyên process() sync cho backward compatibility

### Bước 2 — Verify
python -m pytest tests/ -v --tb=short  # Tất cả phải pass

### Bước 3 — Cập nhật tài liệu
- CHANGELOG.md: thêm entry mới
- STATE.json: tăng progress lên 99%
- PROJECT_MEMORY.md: thêm ADR về async workflow
- NEXT_AI.md: viết lại cho AI tiếp theo

### Bước 4 — Commit + Push
```powershell
git add .
git commit -m "feat: Async Workflow processor

Thêm process_async() vào Workflow dùng generate_async().
Toàn bộ pipeline chạy non-blocking từ input → response.

🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>"
git push
```
```

# 9. Những điều tuyệt đối không nên làm

- Không thêm LangChain, LlamaIndex hay framework AI lớn
- Không thay đổi kiến trúc module (core, settings, model_router, memory, plugin, workflow, knowledge)
- Không thêm database ngoài SQLite + ChromaDB
- Không xóa tests đã viết
- Không hardcode API keys
- Không sửa .streamlit/config.toml (cần cho Streamlit Cloud)

# 10. Đánh giá sức khỏe dự án

| Tiêu chí | Điểm | Ghi chú |
|---|---|---|
| Architecture | 9.5/10 | Module hóa rõ ràng, async support, caching |
| Code Quality | 9/10 | Type hints, shared helpers, consistent patterns |
| Test Coverage | 8.5/10 | 290+ tests, async tests, mỗi module có test riêng |
| Documentation | 10/10 | README, Wiki docs, handover notes, PROJECT_MEMORY |
| Deployment | 9.5/10 | Streamlit Cloud + Docker + GHCR + GitHub Actions |
| Performance | 8/10 | Caching + async model calls (cần async workflow để hoàn thiện) |
| UI/UX | 8.5/10 | Dark theme, animations, responsive sidebar, web search |
| Overall | 9/10 | Dự án gần hoàn chỉnh cho beta release |
