#!/bin/bash
# user_data.sh — Bootstrap mínimo de la instancia EC2
# Solo instala Python y nginx. PostgreSQL y Redis los instala deploy.sh vía SSH
# para evitar problemas de timing.

set -e
exec > /var/log/user_data.log 2>&1

echo "=== BITE Sprint2 - Bootstrap iniciado: $(date) ==="

apt-get update -y
sleep 30

apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    git rsync unzip \
    python3 python3-pip python3-venv \
    nginx

systemctl enable nginx

mkdir -p /home/ubuntu/app
chown ubuntu:ubuntu /home/ubuntu/app

apt-get clean
rm -rf /var/lib/apt/lists/*

echo "=== Bootstrap completado: $(date) ==="
echo "=== Python: $(python3 --version) ==="
