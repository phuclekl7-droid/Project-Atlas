# 🌤️ Cloudflare Tunnel Setup Guide (Feature #89)

> Expose your local Project Atlas instance to the internet securely
> using Cloudflare Tunnel — no port forwarding needed!

## 📋 Prerequisites

- A domain managed by Cloudflare (e.g., `your-domain.com`)
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) installed
- Project Atlas running locally on port 8501 (Streamlit default)

## 🚀 Quick Start

### 1. Install cloudflared

**Windows (PowerShell Admin):**
```powershell
winget install cloudflare.cloudflared
# Or download manually from:
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
```

**macOS:**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Linux:**
```bash
sudo apt install cloudflared  # Debian/Ubuntu
# Or download the binary:
# wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
# sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
# sudo chmod +x /usr/local/bin/cloudflared
```

### 2. Authenticate cloudflared

```bash
cloudflared tunnel login
```

This opens a browser window. Log in to your Cloudflare account and select your domain.

### 3. Create a Tunnel

```bash
cloudflared tunnel create project-atlas
```

This generates:
- A tunnel ID (UUID)
- A credentials file at: `~/.cloudflared/<tunnel-id>.json`

### 4. Configure the Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <your-tunnel-id>
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  # Route to Project Atlas Streamlit app
  - hostname: atlas.your-domain.com
    service: http://localhost:8501

  # Route to API (if FastAPI is running)
  - hostname: api.atlas.your-domain.com
    service: http://localhost:8000

  # Catch-all rule
  - service: http_status:404
```

### 5. Configure DNS

```bash
# Create DNS records for your tunnel
cloudflared tunnel route dns project-atlas atlas.your-domain.com
cloudflared tunnel route dns project-atlas api.atlas.your-domain.com
```

### 6. Start the Tunnel

```bash
cloudflared tunnel run project-atlas
```

Your app is now live at: **https://atlas.your-domain.com** 🎉

## 🐳 Docker Deployment

### docker-compose.yml Integration

Add to your existing `docker-compose.yml`:

```yaml
services:
  # ... your existing atlas service ...

  tunnel:
    image: cloudflare/cloudflared:latest
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN:-}
    volumes:
      - ~/.cloudflared:/etc/cloudflared
    depends_on:
      - atlas
```

### Using TUNNEL_TOKEN (Cloudflare Zero Trust)

1. Go to Cloudflare Zero Trust → Access → Tunnels
2. Create a tunnel → Copy the token
3. Run:

```bash
cloudflared tunnel --token <your-token> run
```

For Docker:
```bash
docker run -d --name atlas-tunnel \
  cloudflare/cloudflared:latest tunnel \
  --token <your-token> run
```

## 🔄 Auto-start with systemd

### Linux (systemd)

Create `/etc/systemd/system/atlas-tunnel.service`:

```ini
[Unit]
Description=Cloudflare Tunnel for Project Atlas
After=network.target

[Service]
Type=simple
User=atlas
ExecStart=/usr/local/bin/cloudflared tunnel run project-atlas
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable atlas-tunnel
sudo systemctl start atlas-tunnel
sudo systemctl status atlas-tunnel
```

### Windows (Task Scheduler)

```powershell
# Create a scheduled task to start the tunnel on login
$action = New-ScheduledTaskAction -Execute "cloudflared.exe" -Argument "tunnel run project-atlas"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "AtlasTunnel" -Action $action -Trigger $trigger -RunLevel Highest
```

## 🔒 Security Notes

- Cloudflare Tunnel encrypts traffic end-to-end (no need for self-signed certs)
- All traffic is proxied through Cloudflare (hides your real IP)
- Enable **Bot Fight Mode** in Cloudflare Dashboard → Security → Bots
- Use **Access Policies** for additional authentication:
  - Go to Zero Trust → Access → Applications
  - Add your domain → Require email/one-time PIN

## 🔧 Troubleshooting

| Problem | Solution |
|:--------|:---------|
| `ERR_TUNNEL_UNAUTHORIZED` | Run `cloudflared tunnel login` again |
| `failed to connect to origin` | Ensure Streamlit is running on port 8501 |
| DNS not propagating | Check `cloudflared tunnel route dns list` |
| High latency | Choose a Cloudflare data center near you |
| Tunnel keeps disconnecting | Check internet stability; add `--retries 5` |

## 📚 References

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [cloudflared GitHub](https://github.com/cloudflare/cloudflared)
- [Zero Trust Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)
