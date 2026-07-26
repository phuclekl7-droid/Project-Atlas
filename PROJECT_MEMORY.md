# Ký ức Dự án (Project Memory)

> [!IMPORTANT]
> **TÀI LIỆU CỐT LÕI CHO HỆ THỐNG ĐA AI (MULTI-AI RELAY)**
> Dự án này được thiết kế để phát triển bởi hàng chục phiên bản AI khác nhau qua từng phiên làm việc riêng biệt. Mọi quyết định quan trọng, định hướng, hay thay đổi kiến trúc **phải** được ghi lại vào file này. Tuyệt đối không được giữ các thông tin này trong bộ nhớ hội thoại tạm thời (chat context), vì AI tiếp theo sẽ không thể thấy chúng!

## Quyết định Kiến trúc & Bối cảnh

### 1. Triết lý Thiết kế
- **Đơn giản:** Chỉ xây dựng những gì thực sự cần thiết, không over-engineering.
- **Ít phụ thuộc:** Hạn chế tối đa sử dụng thư viện bên thứ 3 (đặc biệt là các framework khổng lồ như LangChain, LlamaIndex nếu tự code được).
- **Phổ thông:** Hệ thống phải chạy mượt trên máy cấu hình yếu, RAM ít, không cần GPU (với lựa chọn kết nối API hoặc local model nhẹ).
- **Offline-first (Tùy chọn):** Sẵn sàng để chạy mô hình qua Ollama.

### 2. Ràng buộc Phần cứng (Hardware Constraints) - BẮT BUỘC TUÂN THỦ
- **Nền tảng:** Máy tính cá nhân phổ thông, **KHÔNG CÓ GPU MẠNH**, **RAM RẤT ÍT**.
- **Hệ quả thiết kế đối với mọi AI:** 
  - Tuyệt đối không đề xuất hay tích hợp các Vector Database nặng (như Milvus, Qdrant). Chỉ dùng SQLite hoặc Flat file (JSON/Markdown).
  - Không bao giờ mặc định tải các model LLM lớn (ví dụ: Llama 3 8B). Luôn khuyến nghị các model siêu nhẹ như `qwen2:0.5b` hoặc `gemma2:2b` cho môi trường local, hoặc chuyển tải sang API (OpenAI/Gemini).
  - Bản thân mã nguồn Python phải ngốn cực kỳ ít RAM. Không load toàn bộ file lớn vào bộ nhớ.

### 3. Các Quyết định (ADR - Architecture Decision Records)

**ADR 001: Lựa chọn Ngôn ngữ**
- **Quyết định:** Sử dụng Python.
- **Lý do:** Hệ sinh thái AI mạnh mẽ, dễ viết script, dễ hiểu đối với các thế hệ AI bảo trì sau này.
- **Tình trạng:** Chấp nhận.

**ADR 002: Kiến trúc Module**
- **Quyết định:** Tách dự án thành 7 module chính (`core`, `memory`, `knowledge`, `workflow`, `plugin`, `settings`, `model_router`).
- **Lý do:** Giúp phát triển và test độc lập. Dễ dàng để AI (như tôi) sửa 1 phần mà không ảnh hưởng toàn bộ.
- **Tình trạng:** Chấp nhận.

**ADR 003: Quản lý Trạng thái & Tri thức AI**
- **Quyết định:** Sử dụng file `NEXT_AI.md` để handover (bàn giao), `STATE.json` để phần mềm/AI đọc nhanh tiến độ, và `PROJECT_MEMORY.md` để lưu tri thức vĩnh viễn.
- **Lý do:** Để đảm bảo dự án có thể được phát triển liên tục bởi hàng chục phiên bản AI khác nhau mà không mất mát bối cảnh từ các cuộc trò chuyện đã qua.
- **Tình trạng:** Chấp nhận.

**ADR 004: Tên Dự án**
- **Quyết định:** Đặt tên chính thức cho dự án là **"Project Atlas"**.
- **Lý do:** Người dùng yêu cầu đổi tên để cá nhân hóa hệ thống.
- **Tình trạng:** Chấp nhận.
