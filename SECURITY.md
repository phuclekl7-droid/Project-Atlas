# 🔒 Security Policy — Project Atlas

## 🔐 Bảo mật API Keys

Project Atlas có thể sử dụng API keys cho OpenAI và các dịch vụ khác. 
**Không bao giờ** commit API keys vào repository.

### Quy tắc bảo mật

1. **Không commit `.env`** — file này đã được `.gitignore` bỏ qua
2. **Không hardcode keys** — luôn dùng environment variables
3. **Trên Streamlit Cloud** — dùng Secrets dashboard thay vì file
4. **Kiểm tra trước commit** — chạy `git status` để xem có file lạ không

## 🐛 Báo cáo lỗ hổng bảo mật

Project Atlas đang ở giai đoạn alpha, nhưng chúng tôi vẫn coi trọng bảo mật.

### Nếu bạn phát hiện lỗ hổng:

1. **Không tạo issue public** — tạo issue với label `security`
2. Hoặc gửi email qua GitHub Issues với mô tả chi tiết
3. Chúng tôi sẽ phản hồi trong vòng 48h

### Chúng tôi khuyến khích:

- Báo cáo lỗ hổng một cách có trách nhiệm
- Cho chúng tôi thời gian hợp lý để fix trước khi công bố
- Làm việc với chúng tôi để giải quyết vấn đề

## ✅ Best Practices

### Local Development

```bash
# Cấu hình API keys trong .env (đã được .gitignore)
cp .env.example .env
# Sau đó edit .env với API keys thật
```

### Streamlit Cloud

Dùng **Secrets dashboard** để inject environment variables:
```
MODEL_PROVIDER = "openai"
OPENAI_API_KEY = "sk-proj-..."
```

### Pre-commit hooks

Dự án có sẵn pre-commit hook `detect-private-key` để tự động 
phát hiện keys bị commit nhầm:

```bash
pre-commit install
# Hook sẽ chạy tự động mỗi lần git commit
```

## 📋 Phiên bản được hỗ trợ

Hiện tại chỉ có phiên bản `v0.5.x-alpha` — security updates 
sẽ được backport khi cần thiết.
