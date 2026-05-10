#!/bin/bash
# deployment/asr30/user_data_log_store.sh — Log Store Consumer (ASR30)
set -e
exec > /var/log/user_data_logstore.log 2>&1

echo "=== LogStore Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git

git clone https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git /home/ubuntu/app
cd /home/ubuntu/app

python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

mkdir -p /var/log/bite/logs
chown -R ubuntu:ubuntu /var/log/bite

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
MONGO_URI=mongodb://localhost:27017
LOG_STORE_DIR=/var/log/bite/logs
EOF

cat > /etc/systemd/system/bite-logstore.service << 'UNIT'
[Unit]
Description=BITE Log Store Consumer (ASR30)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/venv/bin/python log_handlers/log_store_consumer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bite-logstore
systemctl start bite-logstore

echo "=== LogStore listo: $(date) ==="
