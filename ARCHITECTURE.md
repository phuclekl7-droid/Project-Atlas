# Kiến Trúc Hệ Thống (System Architecture)

## 1. Nguyên Tắc Thiết Kế (Design Principles)
- **Độc lập (Loose Coupling):** Các module `memory`, `knowledge`, `workflow` không được import chéo lẫn nhau một cách trực tiếp mà nên thông qua `core` hoặc các Interface trừu tượng.
- **Trạng thái cấu hình (Configuration-Driven):** Mọi phụ thuộc vào model hoặc đường dẫn file phải nằm trong `settings`.
- **Plug-and-play cho Model:** Việc đổi từ ChatGPT sang Ollama chỉ cần thay đổi 1 dòng config trong Settings, `model_router` sẽ tự lo phần còn lại.

## 2. Thiết Kế Các Module

### Core (`src/core`)
Chứa các thành phần tiện ích cốt lõi dùng chung: logger, error handler, utils, interface definitions (ABC).

### Settings (`src/settings`)
Load các biến môi trường và thiết lập. Ví dụ: `MODEL_PROVIDER=ollama`, `OLLAMA_URL=http://localhost:11434`.

### Model Router (`src/model_router`)
Có nhiệm vụ: Nhận prompt -> Bọc lại (Wrap) với format đúng -> Gọi API (hoặc Ollama) -> Trả về text đơn giản. Không chứa logic xử lý trí nhớ ở đây.

### Memory (`src/memory`)
Lưu giữ Session Chat. Có 2 loại dự kiến:
- Short-term: Lưu cuộc hội thoại hiện tại.
- Long-term: Lưu các fact, tóm tắt người dùng (Dùng SQLite).

### Knowledge (`src/knowledge`)
Khác với Memory (thu thập từ chat), Knowledge là nguồn tài nguyên người dùng cung cấp (ví dụ: các file text, pdf...). Xử lý RAG tinh gọn (vector db nhẹ như chromadb hoặc faiss).

### Plugin (`src/plugin`)
Quản lý các tool (chẳng hạn như search web, thao tác file). Tuân theo cấu trúc Interface 1 hàm `execute()`.

### Workflow (`src/workflow`)
Quản lý chu trình: Ví dụ user gõ -> Workflow gọi Memory lấy context -> Workflow gọi Plugin lấy data -> Workflow gửi cho Model Router -> Workflow in ra màn hình.
