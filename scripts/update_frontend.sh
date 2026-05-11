#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# update_frontend.sh  — Sube el frontend actualizado al servidor
# y arregla los permisos de nginx en /home/ubuntu
#
# Uso: ./scripts/update_frontend.sh <KEY_PATH> <APP_IP>
# Ej:  ./scripts/update_frontend.sh ~/labsuser.pem 98.84.159.214
# ─────────────────────────────────────────────────────────────

set -euo pipefail

KEY_PATH="${1:?Uso: $0 <ruta_clave_pem> <ip_servidor>}"
APP_IP="${2:?Uso: $0 <ruta_clave_pem> <ip_servidor>}"

SSH_OPTS="-i $KEY_PATH -o StrictHostKeyChecking=no -o ConnectTimeout=15"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BITE — Actualizar Frontend"
echo "  Servidor: $APP_IP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Subir los tres archivos del frontend
echo "→ Subiendo frontend/index.html..."
scp $SSH_OPTS frontend/index.html ubuntu@$APP_IP:/tmp/index.html

echo "→ Subiendo frontend/app.js..."
scp $SSH_OPTS frontend/app.js ubuntu@$APP_IP:/tmp/app.js

echo "→ Subiendo frontend/style.css..."
scp $SSH_OPTS frontend/style.css ubuntu@$APP_IP:/tmp/style.css

# Mover al destino y arreglar permisos
echo "→ Aplicando archivos y arreglando permisos..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    # Crear directorio si no existe
    mkdir -p /home/ubuntu/app/frontend

    # Mover archivos
    cp /tmp/index.html /home/ubuntu/app/frontend/index.html
    cp /tmp/app.js     /home/ubuntu/app/frontend/app.js
    cp /tmp/style.css  /home/ubuntu/app/frontend/style.css

    # Arreglar permisos para que nginx (www-data) pueda leer
    chmod o+x /home/ubuntu
    chmod o+x /home/ubuntu/app
    chmod -R o+r /home/ubuntu/app/frontend

    # Recargar nginx (no restart — evita downtime)
    sudo nginx -t && sudo systemctl reload nginx && echo '✓ nginx recargado'
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Frontend actualizado"
echo "  Abre: http://$APP_IP/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
