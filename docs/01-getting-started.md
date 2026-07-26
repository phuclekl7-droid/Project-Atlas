# 🚀 Getting Started with Project Atlas

## Yêu cầu

- Python 3.10+
- Git
- (Optional) Ollama — https://ollama.com
- (Optional) OpenAI API key — https://platform.openai.com/api-keys

## Cài đặt nhanh

```bash
# Clone
git clone https://github.com/phuclekl7-droid/Project-Atlas.git
cd Project-Atlas

# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Dependencies
pip install -r requirements.txt

# Config
cp .env.example .env
# Edit .env với API keys nếu cần
```

## Chạy app

```bash
# Web UI (khuyên dùng)
streamlit run app.py

# CLI (alternative)
python src/main.py
```

## Kiểm tra

```bash
# Chạy tests
python -m pytest tests/ -v

# Coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Deploy lên Cloud

Xem [README.md](../README.md#-deploy-lên-streamlit-community-cloud-miễn-phí) để deploy lên Streamlit Cloud miễn phí.
