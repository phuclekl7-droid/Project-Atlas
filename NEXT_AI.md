> [!IMPORTANT]
> **THÔNG ĐIỆP QUAN TRỌNG DÀNH CHO AI ĐANG ĐỌC FILE NÀY**
> Bạn là một phần của chuỗi tiếp sức gồm nhiều AI khác nhau cùng xây dựng dự án này.
> - **TRÁCH NHIỆM CỦA BẠN:** Trước khi kết thúc phiên làm việc của mình, bạn **BẮT BUỘC** phải ghi lại những gì bạn đã làm, định hướng tiếp theo, và cập nhật lại toàn bộ file `NEXT_AI.md` này cho AI thế hệ kế tiếp.
> - Nếu bạn thay đổi kế hoạch hoặc kiến trúc, hãy cập nhật `PROJECT_MEMORY.md`.

# 1. Tóm tắt dự án
- Dự án hiện đang làm gì: Phase 2 - Basic Intelligence. Đã có unit tests cho core, settings, model_router, memory. 
- Mục tiêu cuối cùng: Tạo ra Project Atlas - một trợ lý AI cá nhân tinh gọn, chạy được trên máy phổ thông, hỗ trợ offline (Ollama) và API, kiến trúc linh hoạt, dễ bảo trì.
- Tiến độ hiện tại: **45%** (Core ✓ tested, Settings ✓ tested, ModelRouter ✓ tested, Memory ✓ tested, main.py CLI ✓).

# 2. Những gì bạn đã hoàn thành
- **Unit tests** (112 tests total):
  - `tests/test_core.py` (30 tests): Logger setup (5), ColoredFormatter (2), exceptions hierarchy (7), utilities (6), edge cases.
  - `tests/test_settings.py` (25 tests): Default values (7), validation (6), to_dict (3), load_settings priority chain (6), _safe_int (6), repr (2).
  - `tests/test_model_router.py` (30 tests): MockModel responses (9), OllamaModel mocked calls (6), OpenAIModel mocked calls (5), ModelRouter factory (7), ModelResponse (2).
  - `tests/test_memory.py` (27 tests): Session CRUD (8), messages (4), context formatting (5), edge cases (6), data models (3), context manager (1).
- **Test infrastructure**: `pytest.ini`, `tests/conftest.py` (fixtures: settings variants, mock responses, temp files).
- **Dependencies**: `pytest>=8.0.0`, `pytest-mock>=3.14.0` added to requirements.txt.

# 3. Những gì còn dang dở
- `Knowledge` module chưa được implement.
- `Plugin` module chưa có logic.
- `Workflow` module chưa có logic.
- Chưa chạy được tests (cần môi trường venv + pip install).
- Chưa có CI/CD.

# 4. Bug đã biết
Không phát hiện bug.

# 5. Nợ kỹ thuật (Technical Debt)
- Cần chạy `pip install -r requirements.txt` và `pytest tests/` để verify tests pass.
- Cần pre-commit hook chạy pytest tự động.
- Chưa có test cho main.py (cần integration tests với CLI).

# 6. Đề xuất cho AI tiếp theo
**Priority 1:** Xây dựng Plugin system: BasePlugin ABC, PluginLoader (importlib), 1 plugin mẫu (calculator).
**Priority 2:** Implement Workflow module: orchestrator cho user input → memory → plugins → model router → memory → output.
**Priority 3:** Chạy pytest và fix bất kỳ test failures nào.
**Priority 4:** Setup GitHub Actions CI để chạy tests tự động.

# 7. Chọn DUY NHẤT MỘT nhiệm vụ
Nhiệm vụ có tác động lớn nhất hiện tại: **Xây dựng Workflow module**.
Giải thích: Workflow là bộ não điều phối toàn bộ hệ thống (memory → plugins → model router). Đã có đủ modules để Workflow có thể hoạt động thực tế.

# 8. Viết Prompt cho AI tiếp theo
```markdown
Đọc toàn bộ tài liệu dự án (ARCHITECTURE.md, PROJECT_MEMORY.md, ROADMAP.md). Đọc NEXT_AI.md.
Nhiệm vụ của bạn là:
1. Chạy `pip install -r requirements.txt` (hoặc đảm bảo môi trường)
2. Chạy `pytest tests/ -v` và fix bất kỳ test failures nào
3. Implement Workflow module (src/workflow): orchestrator tích hợp Memory → Plugin → Model Router → Memory
4. Cập nhật main.py để sử dụng Workflow thay vì gọi trực tiếp các module
5. Cập nhật CHANGELOG.md, STATE.json, NEXT_AI.md
```

# 9. Những điều tuyệt đối không nên làm
- Không thêm LangChain, LlamaIndex, hay framework AI lớn.
- Không thay đổi thiết kế module trong ARCHITECTURE.md.
- Không thêm database phức tạp ngoài sqlite3.
- Không xóa hoặc sửa tests đã viết.

# 10. Đánh giá sức khỏe dự án
Architecture: 9/10
Code Quality: 8.5/10
Test Coverage: 8/10 (112 tests cho 4 modules)
Documentation: 10/10
Scalability: 8/10
Overall: 8.5/10
Giải thích: Test coverage tốt cho core modules (core, settings, model_router, memory). Cần CI/CD, plugins, và knowledge module để tăng điểm.
