<div align="center">

# 🤖 Personal AI Assistant

**Một trợ lý AI cá nhân tinh gọn, module hóa, chạy được offline hoặc trên Cloud.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://phuclekl7-droid-project-atlas.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Actions](https://github.com/phuclekl7-droid/Project-Atlas/actions/workflows/test.yml/badge.svg)](https://github.com/phuclekl7-droid/Project-Atlas/actions)

</div>

---

## 📋 Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🧠 **Memory** | Lưu trữ hội thoại theo session với SQLite |
| 🧩 **Plugins** | Hệ thống plugin mở rộng (Calculator, ...) |
| 🔄 **Workflow** | Orchestrator: Memory → Plugin → Model Router → Memory |
| 📚 **Knowledge RAG** | Upload file .txt, ChromaDB vector search, auto-inject vào LLM |
| 🔌 **3 Providers** | Mock (test), Ollama (local), OpenAI (API) |
| 🌐 **Web UI** | Streamlit giao diện đẹp với dark theme |
| 🖥️ **CLI** | Terminal interface song song với Web UI |
| 🧪 **Tests** | 200+ unit tests với pytest |

---

## 🚀 Deploy lên Streamlit Community Cloud (Miễn phí)

Chỉ **5 phút** để deploy app lên cloud — không cần cài đặt gì trên máy!

> 💡 **GitHub Pages vs Streamlit Cloud**: GitHub Pages chỉ host static site (HTML/CSS/JS).
> Vì app của chúng ta là Python/Streamlit (dynamic web app), chúng ta dùng **Streamlit Community Cloud**
> — nền tảng free hosting chính thức cho Streamlit apps.
>
> Badge URLs đã được cập nhật với repo **phuclekl7-droid/Project-Atlas** ✅

### Bước 1: Commit code

```powershell
cd D:\personal_ai_assistant

# Nếu chưa init git
git init
git branch -M main

# Thêm tất cả file
# LƯU Ý: .env và data/ sẽ tự động được .gitignore bỏ qua
git add .

# Kiểm tra xem có file nào lạ không
git status

# Commit
git commit -m "Initial commit: Personal AI Assistant v0.5.0-alpha

- Core, Settings, ModelRouter, Memory modules
- Plugin system with CalculatorPlugin
- Workflow orchestrator
- Knowledge RAG with ChromaDB
- Streamlit Web UI + CLI
- 200+ unit tests with pytest
- CI/CD: GitHub Actions + pre-commit hooks

🤖 Generated with Codebuff
Co-Authored-By: Codebuff <noreply@codebuff.com>"
```

### Bước 2: Push lên GitHub (đã có repo sẵn!)

```powershell
git remote add origin https://github.com/phuclekl7-droid/Project-Atlas.git
git push -u origin main
```

> 💡 Cần cài Git cho Windows? Tải tại https://git-scm.com/download/win

### Bước 3: Deploy lên Streamlit Cloud

1. **Truy cập** https://share.streamlit.io và đăng nhập bằng GitHub
2. **Click "New app"** → Chọn tab "Public app from GitHub"
3. **Chọn repository**: `phuclekl7-droid/Project-Atlas`
4. **Branch**: `main`
5. **Main file**: `app.py` (Streamlit tự detect)
6. **Click "Deploy!"** 🚀

⏳ Đợi 2-5 phút, app sẽ tự động build và deploy.

Sau deploy, app sẽ live tại:
**https://phuclekl7-droid-project-atlas.streamlit.app**

### Bước 4: ⚡ Cấu hình OpenAI để app trả lời thông minh

Sau khi deploy, app mặc định dùng **Mock** (trả lời giả lập). Để có câu trả lời thực từ AI:

**a) Thêm API Key vào Streamlit Cloud Secrets:**

1. Vào https://share.streamlit.io
2. Chọn app **Project-Atlas**
3. Vào **☰ → Settings → Secrets**
4. Paste vào ô text:
```toml
# PROJECT_ATLAS Secrets — 18/09/2024

# Chọn provider mặc định (openai | mock)
MODEL_PROVIDER = "openai"

# 👇 OpenAI API key — lấy từ https://platform.openai.com/api-keys
OPENAI_API_KEY = "sk-proj-...cua_ban_o_day..."

# Model (optional, mặc định gpt-4o-mini — rẻ và nhanh)
# OPENAI_MODEL = "gpt-4o-mini"

# Log level
LOG_LEVEL = "INFO"
```

5. Click **Save**
6. Vào **☰ → Settings → General → ⏻ Reboot app** (cần reboot để secrets生效)

> 💡 **Chưa có OpenAI key?** 
> 1. Vào https://platform.openai.com/api-keys
> 2. Click **+ Create new secret key**
> 3. Copy key dạng `sk-proj-...`
> 4. Dán vào Secrets ở trên
> 5. Cần $5 credit — đăng ký mới được tặng $5 free!

**b) Dùng thử ngay trên app:**

Sau khi reboot, vào sidebar → **Model Provider** → chọn **🔵 OpenAI** → app sẽ dùng GPT trả lời thực tế!

| Secret Key | Giá trị | Bắt buộc? |
|---|---|---|
| `MODEL_PROVIDER` | `"openai"` | ✅ Để dùng OpenAI |
| `OPENAI_API_KEY` | `"sk-proj-..."` | ✅ Bắt buộc |
| `OPENAI_MODEL` | `"gpt-4o-mini"` | Optional |
| `LOG_LEVEL` | `"INFO"` | Optional |

> ⚠️ **Lưu ý**: Secrets chỉ có hiệu lực sau khi **Reboot** app. Streamlit Cloud tự động restart app khi secrets thay đổi, nhưng nếu không, hãy reboot thủ công.
>
> **Ollama không chạy được trên Cloud** — cần GPU local. Trên Cloud chỉ dùng Mock hoặc OpenAI.
>
> 💡 Repo của bạn tên là **Project-Atlas**, phù hợp với tên dự án gốc!

---

## 🤝 Đóng góp

Project Atlas là open source! Mọi đóng góp đều được chào đón:

| File | Mô tả |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) 📖 | Hướng dẫn đóng góp chi tiết |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 📜 | Quy tắc ứng xử |
| [SECURITY.md](SECURITY.md) 🔒 | Chính sách bảo mật |
| [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) 🐛 | Templates cho Bug Report & Feature Request |
| [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) 🔀 | Template cho Pull Request |
| [docs/](docs/) 📚 | Wiki-style documentation (modules, FAQ, architecture) |

### Cách đóng góp nhanh

```bash
1. Fork repo
2. Tạo branch: git checkout -b feature/ten-tinh-nang
3. Code + Test
4. Commit: git commit -m "feat: Mô tả"
5. Push + Pull Request
```

---

## 🎮 Local Development

### Yêu cầu

- Python 3.10+
- Git (cho Windows: https://git-scm.com/download/win)
- (Optional) Ollama: https://ollama.com

### Cài đặt

```bash
# Clone repo
git clone https://github.com/phuclekl7-droid/Project-Atlas.git
cd Project-Atlas

# Tạo virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# Cài dependencies
pip install -r requirements.txt

# Copy .env.example thành .env và cấu hình
copy .env.example .env    # Windows
# cp .env.example .env     # Linux/Mac
```

### Chạy

```bash
# 🌐 Web UI (khuyên dùng)
streamlit run app.py

# 🖥️ CLI (alternative)
python src/main.py
```

### Test

```bash
# Chạy tất cả tests
python -m pytest tests/ -v

# Chạy test cụ thể
python -m pytest tests/test_knowledge.py -v

# Với coverage
pip install pytest-cov
python -m pytest tests/ --cov=src -v
```

---

## 🏗️ Kiến trúc Module

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

---

## 🛠️ Cấu hình

Tạo file `.env` từ `.env.example`:

| Variable | Default | Mô tả |
|---|---|---|
| `MODEL_PROVIDER` | `mock` | `mock`, `ollama`, hoặc `openai` |
| `OLLAMA_URL` | `http://localhost:11434` | URL của Ollama server |
| `OLLAMA_MODEL` | `llama3.2:1b` | Model name trong Ollama |
| `OPENAI_API_KEY` | — | API key từ OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name của OpenAI |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MAX_CONTEXT_MESSAGES` | `10` | Số tin nhắn context gửi lên model |
| `MEMORY_PATH` | `data/chat.db` | Đường dẫn SQLite database |

---

## 🧪 Testing

Dự án có **200+ unit tests** với pytest:

```bash
# Toàn bộ test suite
python -m pytest tests/ -v

# Test coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing

# Test riêng từng module
python -m pytest tests/test_knowledge.py -v
python -m pytest tests/test_plugin.py -v
python -m pytest tests/test_workflow.py -v
python -m pytest tests/test_settings.py -v
```

---

## ☁️ So sánh: Local vs Cloud

| Tính năng | Local | Streamlit Cloud |
|---|---|---|
| Mock model | ✅ | ✅ |
| OpenAI API | ✅ | ✅ |
| Ollama (local) | ✅ | ❌ |
| Memory (SQLite) | ✅ | ✅ (ephemeral) |
| Knowledge RAG | ✅ (ChromaDB) | ✅ (keyword fallback) |
| Plugin Calculator | ✅ | ✅ |
| File upload | ✅ | ✅ |
| Tốc độ | Phụ thuộc GPU | 1 vCPU miễn phí |

> ⚠️ **Lưu ý về Storage trên Cloud**:
> - **Memory (SQLite)**: Database được lưu trên ephemeral storage, sẽ reset mỗi khi app khởi động lại (~24h trên free tier).
> - **Knowledge (ChromaDB)**: Vector data trong `data/knowledge/` cũng là ephemeral — file upload sẽ mất sau mỗi lần deploy restart.
> - **Workaround**: Dữ liệu vẫn tồn tại trong suốt phiên làm việc. Nếu cần persistent storage, nâng cấp lên Streamlit Team tier hoặc dùng external database.

---

## 📈 Tiến độ dự án

```
Phase 1 — Foundation      ████████████████░░ 80%
Phase 2 — Plugin+Workflow ████████████████░░ 80%
Phase 3 — Knowledge RAG   ██████████████████ 100% ✅
Phase 4 — Polish          ████████░░░░░░░░░░ 40%
```

Xem chi tiết tại [STATE.json](STATE.json) và [ROADMAP.md](ROADMAP.md).

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE) để biết chi tiết.

---

<div align="center">
  
  **Made with ❤️ for the Personal AI Assistant project**
  
  [Report Bug](https://github.com/phuclekl7-droid/Project-Atlas/issues) · [Request Feature](https://github.com/phuclekl7-droid/Project-Atlas/issues)

</div>
