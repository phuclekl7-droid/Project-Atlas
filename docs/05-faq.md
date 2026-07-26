# ❓ FAQ — Câu hỏi thường gặp

## Chung

### Project Atlas là gì?
Project Atlas là một trợ lý AI cá nhân tinh gọn, module hóa.
Có thể chạy local với Ollama hoặc dùng API (OpenAI).

### Project Atlas có miễn phí không?
Có! Code hoàn toàn open source (MIT).
Chi phí chỉ phát sinh nếu bạn dùng OpenAI API (rất rẻ: ~$0.15/1M tokens với GPT-4o-mini).

### Tôi có cần GPU không?
Không. Nếu dùng Mock hoặc OpenAI, không cần GPU.
Nếu dùng Ollama local, bạn có thể chạy model nhỏ (1B-3B parameters) trên CPU.

## Cài đặt

### Lỗi `pip install`?

```bash
# Update pip
python -m pip install --upgrade pip

# Cài từ requirements.txt
pip install -r requirements.txt

# Nếu lỗi chromadb, có thể bỏ qua:
# pip install -r requirements.txt --no-deps chromadb
```

### Lỗi `streamlit: command not found`?

```bash
# Cài Streamlit
pip install streamlit

# Hoặc chạy bằng Python module
python -m streamlit run app.py
```

## Sử dụng

### Làm sao để chuyển provider?
Trong sidebar → **Model Provider** → chọn Mock / Ollama / OpenAI.
Trong CLI: gõ `/mock`, `/ollama`, hoặc `/openai`.

### Mock model có trả lời thật không?
Không. Mock trả lời giả lập để test luồng hoạt động.
Để có câu trả lời thực, dùng Ollama hoặc OpenAI.

### File upload hoạt động thế nào?
Upload file `.txt` → tự động chunk → lưu vào knowledge base.
Khi bạn hỏi, Workflow tự động search KB và inject kiến thức vào prompt.

### Dữ liệu của tôi có an toàn không?
- **Local**: 100% private, không gửi dữ liệu đi đâu (trừ khi dùng OpenAI API)
- **Cloud**: Dữ liệu lưu trên ephemeral storage, reset sau ~24h

## Phát triển

### Làm sao để tạo plugin mới?

```python
# src/plugins/my_plugin.py
from src.plugin import BasePlugin, PluginResult

class MyPlugin(BasePlugin):
    name = "my_plugin"
    description = "..."
    def execute(self, input_str):
        return PluginResult(success=True, output="ok")
```

Plugin sẽ tự động được `PluginLoader` phát hiện.

### Làm sao để test?

```bash
python -m pytest tests/ -v
python -m pytest tests/test_knowledge.py -v
```

### Làm sao để đóng góp?
Xem [CONTRIBUTING.md](../CONTRIBUTING.md) và [docs/04-contributing.md](04-contributing.md).

## Troubleshooting

### App không khởi động được

```bash
# Kiểm tra logs
streamlit run app.py 2>&1

# Lỗi phổ biến: thiếu .env
cp .env.example .env

# Lỗi phổ biến: thiếu dependencies
pip install -r requirements.txt
```

### OpenAIModel lỗi "API key not configured"

Kiểm tra:
1. Đã set `OPENAI_API_KEY` trong `.env`?
2. Trên Cloud: đã thêm vào Secrets dashboard?
3. Đã reboot app sau khi thêm secrets?

### ChromaDB không hoạt động

```bash
# Cài chromadb
pip install chromadb

# Hoặc dùng keyword search (mặc định)
# Không cần cài gì thêm
```
