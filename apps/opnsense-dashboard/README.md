# 🛡️ OPNsense Security Dashboard - VPS Deployment

Complete Docker setup for hosting your OPNsense security dashboard on a VPS with secure Tailscale connection.

## 🚀 Quick Start

### 1. Copy Files to VPS

```bash
# From your local machine
scp -r C:\Users\Demo\opnsense-vps root@76.13.2.44:/root/opnsense-dashboard
```

### 2. Copy Dashboard Files

```bash
# Copy your dashboard HTML/CSS/JS
cp -r /path/to/dashboard/* /root/opnsense-dashboard/dashboard/
```

### 3. Configure Environment

```bash
cd /root/opnsense-dashboard
cp .env.example .env
nano .env
```

Edit `.env` with your credentials:
```bash
OPNSENSE_HOST=https://10.100.10.1:4443
OPNSENSE_API_KEY=your_actual_key
OPNSENSE_API_SECRET=your_actual_secret
TAILSCALE_AUTHKEY=tskey-auth-xxxxx
```

### 4. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

## 📦 What's Included

### Services

**Nginx** - Web server serving the dashboard
- Port 80 (HTTP)
- Port 443 (HTTPS - when SSL configured)
- Serves static dashboard files
- Proxies API requests to backend

**Flask Backend** - Python API server
- Connects to OPNsense API
- Fetches live IDS/IPS data
- Processes metrics and alerts
- Exposes REST API on port 5000

**Tailscale** - Secure network tunnel
- Connects VPS to your home network
- Encrypted connection to OPNsense
- No need to expose OPNsense to internet

## 🔧 Configuration

### OPNsense API Credentials

Get from OPNsense Web UI:
1. Go to: System → Access → Users
2. Edit your user
3. Create API key
4. Copy key and secret to `.env`

### Tailscale Setup

1. Go to: https://login.tailscale.com/admin/settings/keys
2. Generate auth key (reusable, no expiry)
3. Copy to `.env` as `TAILSCALE_AUTHKEY`

## 🌐 Access Your Dashboard

After deployment:

**Local network:**
```
http://76.13.2.44/opnsense-security/
```

**With domain (optional):**
```
http://security.imagesbyolofsson.se/opnsense-security/
```

## 🔒 SSL/HTTPS Setup (Optional)

### Using Let's Encrypt

```bash
# Install certbot
apt-get install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d security.imagesbyolofsson.se

# Auto-renewal is configured automatically
```

### Manual SSL

1. Place certificates in `./ssl/`
2. Uncomment HTTPS server block in `nginx.conf`
3. Restart: `docker-compose restart nginx`

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f nginx
docker-compose logs -f tailscale
```

### Check Status

```bash
docker-compose ps
```

### Restart Services

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart backend
```

## 🛠️ Troubleshooting

### Backend Can't Connect to OPNsense

**Check Tailscale:**
```bash
docker-compose exec tailscale tailscale status
```

**Test OPNsense connection:**
```bash
docker-compose exec backend curl -k https://10.100.10.1:4443
```

### Dashboard Shows Demo Data

**Check backend health:**
```bash
curl http://localhost:5000/health
```

**Check API endpoint:**
```bash
curl http://localhost:5000/api
```

### Nginx Not Serving Dashboard

**Check nginx logs:**
```bash
docker-compose logs nginx
```

**Verify files:**
```bash
ls -la dashboard/
```

## 🔄 Updates

### Update Dashboard

```bash
# Copy new dashboard files
cp -r /path/to/new/dashboard/* ./dashboard/

# Restart nginx
docker-compose restart nginx
```

### Update Backend

```bash
# Edit backend/api.py
nano backend/api.py

# Rebuild and restart
docker-compose build backend
docker-compose restart backend
```

## 📁 Directory Structure

```
opnsense-dashboard/
├── docker-compose.yml       # Main orchestration
├── .env                     # Environment variables (create from .env.example)
├── .env.example            # Template
├── nginx.conf              # Nginx configuration
├── deploy.sh               # Deployment script
├── README.md               # This file
├── backend/
│   ├── Dockerfile          # Backend container
│   ├── api.py             # Flask API server
│   └── requirements.txt    # Python dependencies
├── dashboard/
│   ├── index.html         # Dashboard UI
│   ├── api.php            # (not used in Docker)
│   └── README.md          # Dashboard docs
└── ssl/                   # SSL certificates (optional)
    ├── cert.pem
    └── key.pem
```

## 🎯 Features

- ✅ **Secure** - Tailscale encrypted tunnel
- ✅ **Live Data** - Real-time IDS/IPS metrics
- ✅ **Dark Theme** - Beautiful UI
- ✅ **Auto-Refresh** - Updates every 10 seconds
- ✅ **Responsive** - Works on all devices
- ✅ **Docker** - Easy deployment and updates
- ✅ **SSL Ready** - HTTPS support included

## 🆘 Support

**Check logs:**
```bash
docker-compose logs -f
```

**Restart everything:**
```bash
docker-compose down
docker-compose up -d
```

**Clean restart:**
```bash
docker-compose down -v
docker-compose up -d
```

---

**Made with 🛡️ for OPNsense**

VPS: 76.13.2.44  
Dashboard: http://76.13.2.44/opnsense-security/
