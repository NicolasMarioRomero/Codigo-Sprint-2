#!/bin/bash
# deployment/disponibilidad/user_data_app.sh — App Django (Disponibilidad)
# Variables: MONGOS_HOST, VAULT_KEY, AUTH0_DOMAIN, AUTH0_CLIENT
set -e
exec > /var/log/user_data_app_disp.log 2>&1

echo "=== App Disponibilidad Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git nginx postgresql-client

git clone https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git /home/ubuntu/app
cd /home/ubuntu/app

python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt

# Para el experimento de disponibilidad, PostgreSQL se instala localmente
apt-get install -y postgresql postgresql-contrib
systemctl start postgresql
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '${DB_PASSWORD}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE bite_db;" 2>/dev/null || true

cat > /home/ubuntu/app/.env << EOF
DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bite_db
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
RABBITMQ_HOST=localhost
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
VAULT_KEY=${VAULT_KEY}
AUTH0_DOMAIN=${AUTH0_DOMAIN}
AUTH0_CLIENT_ID=${AUTH0_CLIENT}
MONGO_URI=mongodb://${MONGOS_HOST}:27017
EOF

python3 manage.py migrate --noinput

cat > /etc/systemd/system/bite-app.service << 'UNIT'
[Unit]
Description=BITE App Disponibilidad
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/venv/bin/gunicorn monitoring.wsgi:application \
    --bind 0.0.0.0:8000 --workers 3 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bite-app
systemctl start bite-app

cat > /etc/nginx/sites-available/bite << 'NGINX'
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/bite /etc/nginx/sites-enabled/bite
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== App Disponibilidad lista: $(date) ==="
