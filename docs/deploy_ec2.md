# CellLineFinder — EC2 Deployment Guide

Single EC2 instance running Nginx (serves React frontend + reverse-proxies FastAPI backend).

---

## Architecture

```
Browser → :80 Nginx
              ├── /           → React static files (dist/)
              └── /api/*      → proxy_pass → localhost:8000 (FastAPI + DuckDB)
```

---

## Step 1 — Launch EC2 Instance

1. Open **EC2 → Launch Instance** in the AWS Console.
2. Settings:
   - **Name**: `celllinefinder`
   - **AMI**: Ubuntu 22.04 LTS (free-tier eligible)
   - **Instance type**: `t3.medium` (2 vCPU, 4 GB RAM) — DuckDB needs memory for Parquet queries. `t2.micro` will be too small.
   - **Key pair**: Create or select one (you'll need the `.pem` file to SSH in)
   - **Storage**: 20 GB gp3 (default 8 GB is too tight with Parquet data)
   - **Security group**: Allow:
     - SSH (port 22) — your IP only
     - HTTP (port 80) — anywhere (0.0.0.0/0)
     - HTTPS (port 443) — anywhere (optional, if adding SSL later)
3. Click **Launch Instance**.

---

## Step 2 — SSH Into the Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

---

## Step 3 — Install System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

# Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Node.js 20 (for building the frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Nginx
sudo apt install -y nginx

# Git
sudo apt install -y git
```

---

## Step 4 — Clone the Repository

```bash
cd /home/ubuntu
git clone https://github.com/<your-username>/celllinefinder.git
cd celllinefinder
# Or if using a specific branch:
# git checkout prab-branch
```

> If your repo is private, use a GitHub personal access token or deploy key.
> Alternatively, you can `scp` your local code to EC2:
> ```bash
> scp -i your-key.pem -r ./prab-branch ubuntu@<EC2-PUBLIC-IP>:/home/ubuntu/celllinefinder
> ```

---

## Step 5 — Pull Parquet Data from Google Drive

```bash
pip install gdown

# Use the download script
chmod +x scripts/pull_data.sh
./scripts/pull_data.sh

# Verify all 8 files are present
ls -lh data_prepare/data/
```

You should see all 8 `.parquet` files. If `gdown` fails (Google rate limits large folders), download manually on your local machine and `scp` them:

```bash
# From your local machine:
scp -i your-key.pem data_prepare/data/*.parquet ubuntu@<EC2-PUBLIC-IP>:/home/ubuntu/celllinefinder/data_prepare/data/
```

---

## Step 6 — Set Up the Backend

```bash
cd /home/ubuntu/celllinefinder/backend_api

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Quick test — should print "Application startup complete"
python run.py
# Ctrl+C to stop
```

---

## Step 7 — Run Backend as a Service (systemd)

Create a systemd service so the backend starts automatically and survives reboots:

```bash
sudo tee /etc/systemd/system/celllinefinder.service > /dev/null <<EOF
[Unit]
Description=CellLineFinder FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/celllinefinder/backend_api
Environment="PATH=/home/ubuntu/celllinefinder/backend_api/venv/bin:/usr/bin"
Environment="CLF_DATA_DIR=/home/ubuntu/celllinefinder/data_prepare/data"
ExecStart=/home/ubuntu/celllinefinder/backend_api/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable celllinefinder
sudo systemctl start celllinefinder

# Check it's running
sudo systemctl status celllinefinder
curl http://localhost:8000/health
```

---

## Step 8 — Build the Frontend

```bash
cd /home/ubuntu/celllinefinder/frontend

npm install
npm run build
# This creates the dist/ folder with static files
```

---

## Step 9 — Configure Nginx

```bash
sudo tee /etc/nginx/sites-available/celllinefinder > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    # React frontend (static files)
    root /home/ubuntu/celllinefinder/frontend/dist;
    index index.html;

    # SPA fallback — all non-file routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy → FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;   # ranking can take a few seconds
    }
}
EOF

# Enable the site, disable default
sudo ln -sf /etc/nginx/sites-available/celllinefinder /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 10 — Verify

Open your browser and go to:

```
http://<EC2-PUBLIC-IP>
```

You should see the CellLineFinder UI. Try searching for a gene (e.g., EGFR) and running a ranking.

Check the API directly:

```
http://<EC2-PUBLIC-IP>/api/health
http://<EC2-PUBLIC-IP>/api/filters/lineages
```

---

## Optional — Custom Domain + SSL

If you have a domain name:

1. Point your domain's A record to the EC2 public IP (in your DNS provider).
2. Install Certbot for free SSL:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

Certbot auto-configures Nginx for HTTPS and sets up auto-renewal.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `502 Bad Gateway` | Backend isn't running. Check: `sudo systemctl status celllinefinder` |
| `404` on page refresh | Nginx `try_files` not configured — check Step 9 |
| Frontend loads but API fails | Check security group allows port 80 inbound |
| DuckDB out of memory | Upgrade to `t3.large` (8 GB RAM) |
| `gdown` rate limited | Download Parquet locally, then `scp` to EC2 |
| Backend log errors | `sudo journalctl -u celllinefinder -f` |

---

## Cost Estimate

| Resource | Monthly cost |
|----------|-------------|
| `t3.medium` EC2 (on-demand) | ~$30 |
| 20 GB EBS storage | ~$2 |
| Data transfer (light usage) | ~$1 |
| **Total** | **~$33/month** |

> For a short demo period (e.g., project presentation), this is about **$1/day**. Stop the instance when not in use to save costs.
