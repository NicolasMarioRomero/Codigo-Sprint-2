#!/bin/bash
# user_data_shard.sh — Bootstrap para EC2s de shard MongoDB
# Instala Docker + docker-compose. El deploy.sh copia el compose y lo levanta.

set -e
exec > /var/log/user_data.log 2>&1

echo "=== BITE Shard Bootstrap iniciado: $(date) ==="

apt-get update -y
sleep 20

apt-get install -y ca-certificates curl gnupg lsb-release git

# ── Docker ────────────────────────────────────────────────────
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker && systemctl start docker
usermod -aG docker ubuntu

apt-get clean
rm -rf /var/lib/apt/lists/*

echo "=== Shard Bootstrap completado: $(date) ==="
echo "=== Docker: $(docker --version) ==="
