# 🤝 Đóng góp cho Project Atlas

Cảm ơn bạn đã quan tâm đến việc đóng góp cho **Project Atlas**! 
Dưới đây là hướng dẫn để bạn có thể tham gia phát triển dự án.

---

## 📋 Mục lục

- [Quy tắc ứng xử](#quy-tắc-ứng-xử)
- [Bắt đầu](#bắt-đầu)
- [Báo cáo lỗi](#báo-cáo-lỗi)
- [Đề xuất tính năng](#đề-xuất-tính-năng)
- [Phát triển](#phát-triển)
- [Kiến trúc module](#kiến-trúc-module)
- [Code style](#code-style)
- [Testing](#testing)
- [Quy trình Pull Request](#quy-trình-pull-request)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)

---

## Quy tắc ứng xử

Dự án này tuân theo [Code of Conduct](CODE_OF_CONDUCT.md). Khi tham gia, bạn đồng ý tuân thủ các quy tắc này.

## Bắt đầu

### 1. Fork repo

```bash
# Fork trên GitHub, sau đó clone
git clone https://github.com/YOUR_USERNAME/Project-Atlas.git
cd Project-Atlas
```

### 2. Thiết lập môi trường

```bash
# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Cài dependencies
pip install -r requirements.txt

# Cài pre-commit hooks (bắt buộc)
pre-commit install
```

### 3. Chạy thử

```bash
# Kiểm tra app chạy được không
streamlit run app.py

# Hoặc CLI
python src/main.py
```

## Báo cáo lỗi

Sử dụng template **Bug Report** khi tạo issue:
https://github.com/phuclekl7-droid/Project-Atlas/issues/new?template=bug_report.md

**Trước khi tạo issue:**
- Kiểm tra [FAQ](https://github.com/phuclekl7-droid/Project-Atlas/wiki/FAQ)
- Tìm kiếm [existing issues](https://github.com/phuclekl7-droid/Project-Atlas/issues)
- Đảm bảo có thể tái hiện lỗi với Mock provider

## Đề xuất tính năng

Sử dụng template **Feature Request**:
https://github.com/phuclekl7-droid/Project-Atlas/issues/new?template=feature_request.md

## Phát triển

### Nhánh (Branch)

```bash
# Tạo nhánh từ main
git checkout -b feature/ten-tinh-nang
git checkout -b fix/ten-loi
git checkout -b docs/ten-tai-lieu
```

### Luồng làm việc

1. Tạo issue → thảo luận → assign
2. Fork + branch
3. Code + test
4. Commit + push
5. Tạo Pull Request

## Kiến trúc module

```
src/
├── core/          # Logging, errors, utilities
├── settings/      # Env vars, config loading
├── model_router/  # LLM providers (Mock, Ollama, OpenAI)
├── memory/        # SQLite session storage
├── plugin/        # Plugin system (BasePlugin, PluginLoader)
├── plugins/       # Built-in plugins (Calculator)
├── workflow/      # Orchestrator: Memory→Plugin→Model→Memory
└── knowledge/     # RAG: ChromaDB + keyword fallback
```

Mỗi module có:
- Interface rõ ràng (import từ `__init__.py`)
- Unit tests trong `tests/`
- Error handling qua `src.core.AssistantError`

## Code Style

### Yêu cầu bắt buộc

- **Python 3.10+** type hints cho mọi function
- **Black** formatting (line-length=100)
- **isort** import sorting (profile=black)
- **flake8** linting (max-complexity=10)
- **mypy** type checking (strict mode cho new code)

### Format tự động

```bash
# Format code
black src/ tests/ --line-length=100

# Sắp xếp imports
isort src/ tests/ --profile=black

# Kiểm tra lint
flake8 src/ tests/ --max-line-length=100 --max-complexity=10

# Type check
mypy src/
```

### Commit Message

```
[type] Short description (50 chars max)

Longer description (wrap at 72 chars).
Explain what and why, not how.

- Bullet points for details
- Reference issues: #123
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

## Testing

### Viết test

- **pytest** framework
- Test file: `tests/test_<module>.py`
- Sử dụng fixtures cho dependencies
- Mock external calls (API requests)

### Chạy test

```bash
# Tất cả tests
python -m pytest tests/ -v

# Module cụ thể
python -m pytest tests/test_plugin.py -v

# Coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Coverage yêu cầu
- Module mới: ≥ 80%
- Bug fix: có test tái hiện lỗi
- Feature mới: test case cho success + error + edge cases

## Quy trình Pull Request

### Trước khi tạo PR

- [ ] `pre-commit run --all-files` (format + lint + type check)
- [ ] `python -m pytest tests/ -v` (all green)
- [ ] `streamlit run app.py` (UI không lỗi)
- [ ] `python src/main.py` (CLI không lỗi)
- [ ] Đã update documentation nếu cần

### Review checklist

Reviewer sẽ kiểm tra:
1. **Design**: Có đúng pattern của module không?
2. **Errors**: Có xử lý edge cases không?
3. **Tests**: Test đủ success + error + edge cases?
4. **Security**: Có lộ API keys không?
5. **Docs**: Cần update README/docs không?

## Cấu trúc thư mục

```
Project-Atlas/
├── .github/
│   ├── workflows/       # CI/CD
│   └── ISSUE_TEMPLATE/  # Issue templates
├── docs/                # Wiki-style documentation
├── src/                 # Source code
│   ├── core/
│   ├── settings/
│   ├── model_router/
│   ├── memory/
│   ├── plugin/
│   ├── plugins/
│   ├── workflow/
│   └── knowledge/
├── tests/               # Unit tests
├── .streamlit/          # Streamlit config
├── app.py               # Web UI
└── requirements.txt     # Dependencies
```

---

## 📧 Liên hệ

- **Issues**: https://github.com/phuclekl7-droid/Project-Atlas/issues
- **Discussions**: https://github.com/phuclekl7-droid/Project-Atlas/discussions

Cảm ơn bạn đã đóng góp! 🎉
