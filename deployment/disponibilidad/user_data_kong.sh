#!/bin/bash
# deployment/disponibilidad/user_data_kong.sh — Kong API Gateway
# Variable: APP_HOST (IP privada de la app Django)
set -e
exec > /var/log/user_data_kong.log 2>&1

echo "=== Kong Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl

# Instalar Kong
curl -Lo /tmp/kong.deb "https://packages.konghq.com/public/gateway-36/deb/ubuntu/pool/jammy/main/k/ko/kong_3.6.1/kong_3.6.1_amd64.deb"
apt-get install -y /tmp/kong.deb

mkdir -p /etc/kong /var/log/kong

# Configuración declarativa
cat > /etc/kong/kong.yml << EOF
_format_version: "3.0"
_transform: true

upstreams:
  - name: bite_upstream
    algorithm: round-robin
    healthchecks:
      active:
        concurrency: 5
        healthy:
          interval: 5
          successes: 2
        unhealthy:
          interval: 5
          http_failures: 3
          tcp_failures: 3
          timeouts: 3
        http_path: /places/health/
        type: http
      passive:
        healthy:
          successes: 5
        unhealthy:
          http_failures: 5

    targets:
      - target: ${APP_HOST}:8000
        weight: 100

services:
  - name: bite-places
    host: bite_upstream
    port: 8000
    protocol: http
    routes:
      - name: places-route
        paths:
          - /places
        strip_path: false

  - name: bite-credentials
    host: bite_upstream
    port: 8000
    protocol: http
    routes:
      - name: credentials-route
        paths:
          - /credentials
        strip_path: false

plugins:
  - name: rate-limiting
    config:
      minute: 300
      policy: local
      fault_tolerant: true
  - name: file-log
    config:
      path: /var/log/kong/access.log
      reopen: true
EOF

# Configurar Kong en modo DB-less
cat > /etc/kong/kong.conf << 'CONF'
database = off
declarative_config = /etc/kong/kong.yml
proxy_listen = 0.0.0.0:80
admin_listen = 0.0.0.0:8001
CONF

kong start --conf /etc/kong/kong.conf

# Servicio systemd para Kong
cat > /etc/systemd/system/kong.service << 'UNIT'
[Unit]
Description=Kong API Gateway
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/kong start --conf /etc/kong/kong.conf
ExecStop=/usr/local/bin/kong stop
PIDFile=/usr/local/kong/pids/nginx.pid
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable kong

echo "=== Kong listo: $(date) ==="
