#!/bin/bash
# user_data.sh — Bootstrap de la instancia EC2
# Se ejecuta automáticamente al lanzar la instancia con Terraform.
# Instala Python, PostgreSQL, Redis y nginx directamente (sin Docker).

set -e
exec > /var/log/user_data.log 2>&1

echo "=== BITE Sprint2 - Bootstrap iniciado: $(date) ==="

# ── Actualizar sistema ─────────────────────────────────────
apt-get update -y
# Nota: se omite apt-get upgrade para ahorrar espacio (~1-2 GB de parches)

# ── Dependencias base ──────────────────────────────────────
apt-get install -y \
    ca-certificates curl gnupg lsb-release \
    git rsync unzip \
    python3 python3-pip python3-venv \
    nginx

# ── PostgreSQL 15 ──────────────────────────────────────────
apt-get install -y postgresql postgresql-contrib

systemctl start postgresql
systemctl enable postgresql

# Establecer contraseña del usuario postgres y crear base de datos
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'password';"
sudo -u postgres psql -c "CREATE DATABASE cloudcosts;" 2>/dev/null || true

# Permitir conexiones TCP locales con contraseña
# (PostgreSQL por defecto usa 'peer' para socket unix; necesitamos md5 para TCP)
PG_HBA=$(sudo -u postgres psql -t -c "SHOW hba_file;" | tr -d ' ')
sed -i 's/^host\s\+all\s\+all\s\+127\.0\.0\.1\/32\s\+.*/host    all             all             127.0.0.1\/32            md5/' "$PG_HBA"
sed -i 's/^host\s\+all\s\+all\s\+::1\/128\s\+.*/host    all             all             ::1\/128                 md5/' "$PG_HBA"
systemctl restart postgresql

echo "=== PostgreSQL listo ==="

# ── Redis ──────────────────────────────────────────────────
apt-get install -y redis-server

# Escuchar solo en localhost
sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf

systemctl start redis-server
systemctl enable redis-server

echo "=== Redis listo ==="

# ── Limpiar caché de apt (libera ~1-2 GB) ─────────────────
apt-get clean
rm -rf /var/lib/apt/lists/*
echo "=== Caché apt limpiada ==="

# ── nginx — se habilita; deploy.sh copiará la configuración ─
systemctl enable nginx

# ── Directorio de la app ───────────────────────────────────
mkdir -p /home/ubuntu/app
chown ubuntu:ubuntu /home/ubuntu/app

echo "=== Bootstrap completado: $(date) ==="
echo "=== Python: $(python3 --version) ==="
echo "=== PostgreSQL: $(psql --version) ==="
echo "=== Redis: $(redis-cli --version) ==="
echo "=== nginx: $(nginx -v 2>&1