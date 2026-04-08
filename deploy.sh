#!/bin/bash
# deploy.sh — Script de despliegue completo en AWS (sin Docker)
# Los servicios corren directamente en EC2 con uvicorn + systemd.
#
# Uso: ./deploy.sh [KEY_PATH]
# Ejemplo: ./deploy.sh ~/.ssh/labsuser.pem

set -e

# ── Configuración ──────────────────────────────────────────
KEY_PATH="${1:-~/.ssh/labsuser.pem}"
TERRAFORM_DIR="./terraform"

# ── Colores ────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── 1. Verificar dependencias ──────────────────────────────
info "Verificando dependencias..."
command -v terraform >/dev/null 2>&1 || err "Terraform no encontrado. Ejecuta: sh install_terraform.sh"
command -v ssh       >/dev/null 2>&1 || err "SSH no encontrado"
command -v rsync     >/dev/null 2>&1 || err "rsync no encontrado"
[ -f "$KEY_PATH" ] || err "Key pair no encontrado: $KEY_PATH"

# ── 2. Terraform: init + apply ─────────────────────────────
info "Inicializando Terraform..."
cd "$TERRAFORM_DIR"
terraform init -upgrade

info "Aplicando infraestructura en AWS..."
terraform apply -auto-approve \
    -var="private_key_path=$KEY_PATH"

PUBLIC_IP=$(terraform output -raw public_ip)
log "Instancia EC2 creada: $PUBLIC_IP"
cd ..

# ── 3. Esperar a que la instancia esté lista ───────────────
info "Esperando que la instancia arranque (~90 segundos para bootstrap)..."
sleep 30

SSH_OPTS="-i $KEY_PATH -o StrictHostKeyChecking=no -o ConnectTimeout=10"
RETRIES=20
for i in $(seq 1 $RETRIES); do
    if ssh $SSH_OPTS ubuntu@$PUBLIC_IP "python3 --version" 2>/dev/null; then
        log "SSH disponible y Python listo"
        break
    fi
    warn "Intento $i/$RETRIES — esperando SSH..."
    sleep 15
    [ $i -eq $RETRIES ] && err "La instancia no respondió a tiempo"
done

# Esperar a que el bootstrap (user_data.sh) termine de instalar PostgreSQL y Redis
info "Esperando que PostgreSQL y Redis estén listos..."
for i in $(seq 1 30); do
    PG_OK=$(ssh $SSH_OPTS ubuntu@$PUBLIC_IP "pg_isready -h localhost -U postgres" 2>/dev/null && echo "ok" || echo "no")
    if [ "$PG_OK" = "ok" ]; then
        log "PostgreSQL listo"
        break
    fi
    warn "Intento $i/30 — PostgreSQL no disponible aún..."
    sleep 10
    [ $i -eq 30 ] && err "PostgreSQL no arrancó a tiempo. Revisa /var/log/user_data.log en EC2."
done

# ── 4. Copiar código al servidor ───────────────────────────
info "Copiando código al servidor..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='terraform' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='venv' \
    --exclude='*.jmx' \
    -e "ssh $SSH_OPTS" \
    . ubuntu@$PUBLIC_IP:/home/ubuntu/app/

log "Código copiado"

# ── 5. Crear virtualenvs e instalar dependencias ───────────
info "Creando virtualenvs e instalando dependencias Python..."
ssh $SSH_OPTS ubuntu@$PUBLIC_IP "
    # Backend
    python3 -m venv /home/ubuntu/venv-backend
    /home/ubuntu/venv-backend/bin/pip install --quiet --upgrade pip
    /home/ubuntu/venv-backend/bin/pip install --quiet -r /home/ubuntu/app/Backend/requirements.txt
    echo '→ Backend deps OK'

    # Extractor
    python3 -m venv /home/ubuntu/venv-extractor
    /home/ubuntu/venv-extractor/bin/pip install --quiet --upgrade pip
    /home/ubuntu/venv-extractor/bin/pip install --quiet -r /home/ubuntu/app/Extractor/requirements.txt
    echo '→ Extractor deps OK'
"
log "Dependencias instaladas"

# ── 6. Crear servicios systemd ─────────────────────────────
info "Creando servicios systemd..."
ssh $SSH_OPTS ubuntu@$PUBLIC_IP "sudo bash -s" << 'ENDSSH'

DB_URL="postgresql://postgres:password@localhost:5432/cloudcosts"
REDIS_HOST="localhost"
REDIS_PORT="6379"

# ── bite-backend-1 (puerto 8000) ────────────────────────────
cat > /etc/systemd/system/bite-backend-1.service << EOF
[Unit]
Description=BITE Report Service instancia 1
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app/Backend
Environment="DATABASE_URL=${DB_URL}"
Environment="REDIS_HOST=${REDIS_HOST}"
Environment="REDIS_PORT=${REDIS_PORT}"
ExecStart=/home/ubuntu/venv-backend/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ── bite-backend-2 (puerto 8002) ────────────────────────────
cat > /etc/systemd/system/bite-backend-2.service << EOF
[Unit]
Description=BITE Report Service instancia 2
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app/Backend
Environment="DATABASE_URL=${DB_URL}"
Environment="REDIS_HOST=${REDIS_HOST}"
Environment="REDIS_PORT=${REDIS_PORT}"
ExecStart=/home/ubuntu/venv-backend/bin/uvicorn main:app --host 0.0.0.0 --port 8002 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ── bite-extractor (puerto 8001) ────────────────────────────
cat > /etc/systemd/system/bite-extractor.service << EOF
[Unit]
Description=BITE Extractor Agent
After=network.target redis.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app/Extractor
Environment="REDIS_HOST=${REDIS_HOST}"
Environment="REDIS_PORT=${REDIS_PORT}"
ExecStart=/home/ubuntu/venv-extractor/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# ── bite-celery (worker de Celery para el extractor) ────────
cat > /etc/systemd/system/bite-celery.service << EOF
[Unit]
Description=BITE Celery Worker
After=network.target redis.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app/Extractor
Environment="REDIS_HOST=${REDIS_HOST}"
Environment="REDIS_PORT=${REDIS_PORT}"
ExecStart=/home/ubuntu/venv-extractor/bin/celery -A app.tasks.extract_task.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bite-backend-1 bite-backend-2 bite-extractor bite-celery
echo "→ Servicios systemd creados y habilitados"
ENDSSH

log "Servicios systemd configurados"

# ── 7. Configurar nginx ────────────────────────────────────
info "Configurando nginx..."
ssh $SSH_OPTS ubuntu@$PUBLIC_IP "sudo bash -s" << 'ENDSSH'
    cp /home/ubuntu/app/nginx/nginx.conf /etc/nginx/nginx.conf
    nginx -t && systemctl restart nginx
    echo "→ nginx OK"
ENDSSH
log "nginx configurado"

# ── 8. Arrancar todos los servicios ───────────────────────
info "Arrancando servicios..."
ssh $SSH_OPTS ubuntu@$PUBLIC_IP "
    sudo systemctl start bite-backend-1 bite-backend-2 bite-extractor bite-celery
    sleep 5
    echo '── Estado de servicios ──'
    sudo systemctl is-active bite-backend-1 bite-backend-2 bite-extractor bite-celery
"
log "Servicios arrancados"

# ── 9. Seed de datos ───────────────────────────────────────
info "Cargando datos de prueba en la base de datos..."
ssh $SSH_OPTS ubuntu@$PUBLIC_IP "
    cd /home/ubuntu/app
    DATABASE_URL='postgresql://postgres:password@localhost:5432/cloudcosts' \
        /home/ubuntu/venv-backend/bin/python seed_data.py
"
log "Base de datos cargada con datos de prueba (~60.000 registros)"

# ── 10. Health checks ──────────────────────────────────────
info "Verificando servicios..."
sleep 3

HEALTH=$(curl -sf "http://$PUBLIC_IP/health" || echo "ERROR")
if echo "$HEALTH" | grep -q "ok"; then
    log "Backend (nginx → load balancer) responde correctamente"
else
    warn "Health check del backend falló. Revisar con:"
    warn "  ssh -i $KEY_PATH ubuntu@$PUBLIC_IP 'sudo journalctl -u bite-backend-1 --no-pager -n 30'"
fi

EXT_HEALTH=$(curl -sf "http://$PUBLIC_IP:8001/health" || echo "ERROR")
if echo "$EXT_HEALTH" | grep -q "ok"; then
    log "Extractor responde correctamente"
else
    warn "Extractor health check falló. Revisar:"
    warn "  ssh -i $KEY_PATH ubuntu@$PUBLIC_IP 'sudo journalctl -u bite-extractor --no-pager -n 30'"
fi

# ── 11. Resumen final ──────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ DESPLIEGUE COMPLETADO (sin Docker)${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend / API:   ${CYAN}http://$PUBLIC_IP${NC}"
echo -e "  API Backend:      ${CYAN}http://$PUBLIC_IP/api/v1/${NC}"
echo -e "  Extractor:        ${CYAN}http://$PUBLIC_IP:8001/docs${NC}"
echo -e "  Health check:     ${CYAN}http://$PUBLIC_IP/health${NC}"
echo ""
echo -e "${YELLOW}  ┌─ JMeter — Actualizar HOST en ambos archivos ────────┐${NC}"
echo -e "${YELLOW}  │  jmeter_latencia.jmx      → HOST = $PUBLIC_IP  PORT = 80${NC}"
echo -e "${YELLOW}  │  jmeter_escalabilidad.jmx → HOST = $PUBLIC_IP  PORT = 8001${NC}"
echo -e "${YELLOW}  └────────────────────────────────────────────────────┘${NC}"
echo ""
echo -e "  SSH: ssh -i $KEY_PATH ubuntu@$PUBLIC_IP"
echo ""
echo -e "  Logs de servicios:"
echo -e "    sudo journalctl -u bite-backend-1 -f"
echo -e "    sudo journalctl -u bite-backend-2 -f"
echo -e "    sudo journalctl -u bite-extractor -f"
echo -e "    sudo journalctl -u bite-celery -f"
echo ""
