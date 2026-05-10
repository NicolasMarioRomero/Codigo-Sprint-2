#!/bin/bash
# deployment/asr30/user_data_app.sh — App Django con log masking (ASR30)
set -e
exec > /var/log/user_data_app_asr30.log 2>&1

echo "=== App ASR30 Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git nginx

git clone https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git /home/ubuntu/app
cd /home/ubuntu/app

python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

cat > /home/ubuntu/app/.env << EOF
DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
DB_HOST=${DB_HOST}
DB_PORT=5432
DB_NAME=bite_db
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
RABBITMQ_HOST=${RABBIT_HOST}
RABBITMQ_USER=bite
RABBITMQ_PASSWORD=bitepass
VAULT_KEY=${VAULT_KEY}
AUTH0_DOMAIN=${AUTH0_DOMAIN}
AUTH0_CLIENT_ID=${AUTH0_CLIENT}
MONGO_URI=mongodb://localhost:27017
LOG_STORE_DIR=/var/log/bite/logs
EOF

mkdir -p /var/log/bite/logs
chown -R ubuntu:ubuntu /var/log/bite

python3 manage.py migrate --noinput

cat > /etc/systemd/system/bite-app.service << 'UNIT'
[Unit]
Description=BITE App Django ASR30
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/venv/bin/gunicorn monitoring.wsgi:application \
    --bind 0.0.0.0:${APP_PORT} --workers 3 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bite-app
systemctl start bite-app

# nginx proxy
cat > /etc/nginx/sites-available/bite << 'NGINX'
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/bite /etc/nginx/sites-enabled/bite
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== App ASR30 lista: $(date) ==="
