#!/bin/bash
# deployment/asr29/user_data_notifier.sh — Notifier (ASR29)
set -e
exec > /var/log/user_data_notifier.log 2>&1

echo "=== Notifier Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git

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
AUTH0_MGMT_TOKEN=${AUTH0_MGMT_TOKEN}
MONGO_URI=mongodb://localhost:27017
EOF

cat > /etc/systemd/system/bite-notifier.service << 'UNIT'
[Unit]
Description=BITE Notifier de Alertas (ASR29)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/venv/bin/python notifier/consumer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bite-notifier
systemctl start bite-notifier

echo "=== Notifier listo: $(date) ==="
