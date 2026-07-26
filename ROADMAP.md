# Roadmap (Lộ trình phát triển)

Project Atlas - Dự án phát triển một trợ lý AI cá nhân tinh gọn, chạy trên máy cá nhân hoặc API.

## Phase 1: Nền Móng (Foundation) - Đang thực hiện
- [x] Thiết lập thư mục và cấu trúc module.
- [x] Xây dựng tài liệu tiêu chuẩn cho các hệ hệ AI.
- [ ] Thiết lập luồng xử lý core (nhận prompt, routing, mock response).
- [ ] Xây dựng Settings loading.

## Phase 2: Trí thông minh cơ bản (Basic Intelligence)
- [ ] Kết nối Model Router (Hỗ trợ Ollama và 1 API như OpenAI hoặc Gemini).
- [ ] Xây dựng Workflow cơ bản (Hỏi - Đáp đơn giản).
- [ ] Xây dựng Memory (Short-term memory với file JSON/SQLite).

## Phase 3: Công cụ & Mở rộng (Tools & Extensibility)
- [ ] Khởi tạo hệ thống Plugin (Load module động).
- [ ] Tạo plugin đầu tiên (ví dụ: đọc thời tiết hoặc thực thi script cục bộ).
- [ ] Xây dựng Knowledge (Quản lý RAG tĩnh, có thể dựa trên vector store đơn giản).

## Phase 4: UI/UX & Khả năng tự chủ
- [ ] Thiết lập giao diện dòng lệnh (CLI) thân thiện hoặc TUI.
- [ ] Hỗ trợ đa luồng để thực thi tác vụ ngầm (Background tasks).
