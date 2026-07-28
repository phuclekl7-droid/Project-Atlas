<div align="center">

# 🤖 Project Atlas (Decoupled Architecture)

**Trợ lý AI cá nhân toàn diện với 160+ tính năng, kiến trúc Backend-Frontend độc lập.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)

</div>

---

## 🚀 Giới thiệu

Project Atlas vừa trải qua một đợt nâng cấp toàn diện, chuyển đổi từ kiến trúc nguyên khối (Streamlit) sang **Kiến trúc Tách rời (Decoupled Architecture)** chuyên nghiệp:

1. **Lõi Trí Tuệ (Core AI - 160+ Tính năng)**: Nền tảng AI xử lý logic, lập kế hoạch, RAG, quản lý plugin cực kỳ đồ sộ.
2. **Backend (FastAPI)**: Đóng vai trò là cầu nối, cung cấp các chuẩn RESTful API và giao tiếp luồng dữ liệu thời gian thực (SSE/WebSockets).
3. **Frontend (Next.js)**: Giao diện người dùng hiện đại, tách biệt hoàn toàn (sắp ra mắt).

---

## 📋 Tính năng nổi bật

Dự án sở hữu hơn 160 tính năng độc lập, trong đó nổi bật là:

- 🧠 **Smart Model Router**: Tự động định tuyến câu hỏi đến các mô hình phù hợp.
- 🧩 **Plugin Ecosystem**: Hỗ trợ hàng loạt plugin từ tìm kiếm Web, tóm tắt Youtube, xử lý âm thanh, vẽ biểu đồ...
- 📚 **Knowledge RAG**: Xử lý tài liệu, trích xuất văn bản, tìm kiếm Vector tốc độ cao.
- ⚡ **Real-time Streaming**: Trả về dữ liệu kiểu gõ chữ (Typewriter) mượt mà với Server-Sent Events (SSE).
- 🛡️ **Enterprise Security**: Tích hợp Rate Limiter, RBAC, Authentication, và Audit Logging.
- 💾 **Advanced Memory**: Phân loại bộ nhớ, nén Token, gợi nhớ tự động dựa trên mức độ quan trọng.
- 🧪 **Test Coverage**: Đảm bảo tính ổn định với hàng trăm Unit Tests chuyên sâu.

---

## 🏗️ Kiến trúc Hệ thống mới

```text
┌────────────────────────────────────────────────────────┐
│                      Next.js Frontend                  │
│               (Giao diện người dùng hiện đại)          │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP REST / SSE (Streaming)
                           ▼
┌────────────────────────────────────────────────────────┐
│                      FastAPI Backend                   │
│        (api/main.py - Dependency Injection, Routing)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Giao tiếp logic lõi
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Core AI Engine (src/)                │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │ Memory   │───→│ Orchestrator│───→│ Smart Router  │  │
│  └──────────┘    └─────────────┘    └───────────────┘  │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐  │
│  │ Knowledge│    │ 20+ Plugins │    │ Security/Auth │  │
│  └──────────┘    └─────────────┘    └───────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 🎮 Hướng dẫn chạy Local (Backend API)

### Yêu cầu
- Python 3.10+
- Git

### Cài đặt và Khởi chạy

```bash
# 1. Clone repo
git clone https://github.com/phuclekl7-droid/Project-Atlas.git
cd Project-Atlas

# 2. Tạo virtual environment (khuyên dùng)
python -m venv venv
.\venv\Scripts\activate   # Trên Windows

# 3. Cài dependencies
pip install -r requirements.txt
pip install fastapi uvicorn sse-starlette pydantic  # Đảm bảo cài đủ các gói backend

# 4. Khởi động API Server
uvicorn api.main:app --reload
```

Sau khi khởi động, truy cập trang tài liệu Swagger UI tự động tại:
👉 **http://localhost:8000/docs**

---

## 🤝 Đóng góp

Project Atlas là open source! Mọi đóng góp đều được chào đón. Xem các file hướng dẫn đóng góp trong repo để biết thêm chi tiết.
