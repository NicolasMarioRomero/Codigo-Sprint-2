#!/bin/bash
# deploy.sh — Despliegue completo BITE.co en AWS (4 EC2s)
#
# Infraestructura levantada por Terraform:
#   bite-sprint3-app      (t3.large)  — Django + PostgreSQL + Redis + RabbitMQ
#                                       + Celery + Detector + Revoker + Notifier
#                                       + LogStore + nginx + ConfigSvr + mongos
#   bite-sprint3-shard1   (t3.medium) — MongoDB Shard 1 (3 nodos via Docker)
#   bite-sprint3-shard2   (t3.medium) — MongoDB Shard 2 (3 nodos via Docker)
#   bite-sprint3-shard3   (t3.medium) — MongoDB Shard 3 (3 nodos via Docker)
#
# Puertos expuestos:
#   80   → nginx LB → reports/dashboard       (JMeter latencia)
#   8001 → extractor directo                  (JMeter escalabilidad)
#
# Uso: ./deploy.sh [KEY_PATH]
#
# Prerequisitos: terraform instalado, AWS credentials configuradas
#   (AWS Academy: exportar variables desde Account Details)

set -e

TERRAFORM_DIR="./terraform"

# ── Resolver .pem ──────────────────────────────────────────────
if [ -n "$1" ]; then
    KEY_PATH="$1"
elif [ -f "$HOME/Downloads/labsuser.pem" ]; then
    KEY_PATH="$HOME/Downloads/labsuser.pem"
elif [ -f "$HOME/.ssh/labsuser.pem" ]; then
    KEY_PATH="$HOME/.ssh/labsuser.pem"
else
    echo "[✗] No se encontró labsuser.pem."
    echo "    Descárgalo desde AWS Academy → Account Details → Download PEM"
    echo "    Luego: chmod 400 ~/labsuser.pem && ./deploy.sh ~/labsuser.pem"
    exit 1
fi
chmod 400 "$KEY_PATH" 2>/dev/null || true

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

SSH_OPTS="-i $KEY_PATH -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=30"

wait_ssh() {
    local host="$1" label="$2"
    info "Esperando SSH en $label ($host)..."
    for i in $(seq 1 25); do
        if ssh $SSH_OPTS ubuntu@$host "echo ok" 2>/dev/null; then
            log "SSH disponible en $label"
            return 0
        fi
        warn "Intento $i/25 — esperando SSH en $label..."
        sleep 15
    done
    err "La instancia $label no respondió a tiempo"
}

# ══════════════════════════════════════════════════════════════
# 1. Terraform — levantar las 4 EC2s
# ══════════════════════════════════════════════════════════════
info "Inicializando Terraform..."
export TF_PLUGIN_CACHE_DIR=/tmp/tf-plugin-cache
mkdir -p "$TF_PLUGIN_CACHE_DIR"
cd "$TERRAFORM_DIR"
terraform init -upgrade

info "Aplicando infraestructura (4 EC2s)..."
terraform apply -auto-approve -var="private_key_path=$KEY_PATH"

APP_IP=$(terraform output -raw app_public_ip)
APP_PRIV=$(terraform output -raw app_private_ip)
SHARD1_IP=$(terraform output -json shard_public_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0])")
SHARD2_IP=$(terraform output -json shard_public_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[1])")
SHARD3_IP=$(terraform output -json shard_public_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[2])")
SHARD1_PRIV=$(terraform output -json shard_private_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0])")
SHARD2_PRIV=$(terraform output -json shard_private_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[1])")
SHARD3_PRIV=$(terraform output -json shard_private_ips | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[2])")

log "App:    $APP_IP (privada: $APP_PRIV)"
log "Shard1: $SHARD1_IP (privada: $SHARD1_PRIV)"
log "Shard2: $SHARD2_IP (privada: $SHARD2_PRIV)"
log "Shard3: $SHARD3_IP (privada: $SHARD3_PRIV)"
cd ..

sleep 30

# ══════════════════════════════════════════════════════════════
# 2. Esperar SSH en todas las instancias
# ══════════════════════════════════════════════════════════════
wait_ssh "$APP_IP"    "app"
wait_ssh "$SHARD1_IP" "shard1"
wait_ssh "$SHARD2_IP" "shard2"
wait_ssh "$SHARD3_IP" "shard3"

# ══════════════════════════════════════════════════════════════
# 3. Instalar servicios base en la EC2 principal
# ══════════════════════════════════════════════════════════════
info "Instalando servicios en EC2 principal..."
ssh $SSH_OPTS ubuntu@$APP_IP "sudo bash -s" << 'ENDSSH'
    set -e
    export DEBIAN_FRONTEND=noninteractive

    echo "→ Esperando que user_data.sh finalice..."
    WAIT=0
    until grep -q "Bootstrap completado" /var/log/user_data.log 2>/dev/null; do
        WAIT=$((WAIT+5)); echo "  user_data en progreso (${WAIT}s)..."; sleep 5
        [ $WAIT -ge 300 ] && echo "TIMEOUT esperando user_data" && exit 1
    done
    echo "→ user_data completado"

    # Liberar apt locks
    systemctl stop unattended-upgrades apt-daily.service apt-daily-upgrade.service 2>/dev/null || true
    WAIT=0
    until ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
       && ! fuser /var/lib/dpkg/lock >/dev/null 2>&1; do
        WAIT=$((WAIT+5)); echo "  apt ocupado (${WAIT}s)..."; sleep 5
        [ $WAIT -ge 120 ] && echo "TIMEOUT apt lock" && exit 1
    done

    apt-get update -y
    apt-get install -y postgresql postgresql-contrib redis-server

    # ── PostgreSQL ─────────────────────────────────────────────
    systemctl start postgresql && systemctl enable postgresql
    sudo -u postgres psql -c "CREATE USER monitoring_user WITH PASSWORD 'isis2503';" 2>/dev/null || true
    sudo -u postgres psql -c "ALTER USER monitoring_user WITH PASSWORD 'isis2503';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE monitoring_db OWNER monitoring_user;" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE monitoring_db TO monitoring_user;" 2>/dev/null || true
    PG_HBA=$(sudo -u postgres psql -t -c "SHOW hba_file;" | tr -d ' ')
    sed -i "s|scram-sha-256|md5|g" "$PG_HBA"
    systemctl restart postgresql
    echo "→ PostgreSQL listo"

    # ── Redis ──────────────────────────────────────────────────
    sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf
    systemctl start redis-server && systemctl enable redis-server
    echo "→ Redis listo"

    # ── RabbitMQ via Docker ────────────────────────────────────
    # Evitamos el conflicto Erlang 25/26 usando la imagen oficial de Docker.
    # Docker ya está instalado por user_data.sh.
    docker rm -f rabbitmq 2>/dev/null || true
    docker run -d \
        --name rabbitmq \
        --restart unless-stopped \
        --hostname rabbitmq \
        -p 5672:5672 \
        -p 15672:15672 \
        -e RABBITMQ_DEFAULT_USER=monitoring_user \
        -e RABBITMQ_DEFAULT_PASS=isis2503 \
        rabbitmq:3.13-management

    echo "→ Esperando RabbitMQ (30s)..."
    sleep 30

    docker exec rabbitmq rabbitmqadmin \
        -u monitoring_user -p isis2503 \
        declare exchange name=security_events type=topic durable=true 2>/dev/null || true
    docker exec rabbitmq rabbitmqadmin \
        -u monitoring_user -p isis2503 \
        declare exchange name=logs type=topic durable=true 2>/dev/null || true
    echo "→ RabbitMQ listo (Docker)"

    echo "=== Servicios base instalados ==="
ENDSSH
log "PostgreSQL, Redis, RabbitMQ listos"

# ══════════════════════════════════════════════════════════════
# 4. Copiar código a la EC2 principal
# ══════════════════════════════════════════════════════════════
info "Copiando código al servidor principal..."
ssh $SSH_OPTS ubuntu@$APP_IP "mkdir -p /home/ubuntu/app"
tar czf - \
    --exclude='./.git' \
    --exclude='./terraform' \
    --exclude='./__pycache__' \
    --exclude='./*.pyc' \
    --exclude='./.env' \
    --exclude='./venv' \
    --exclude='./*.jmx' \
    --exclude='./deployment' \
    . | ssh $SSH_OPTS ubuntu@$APP_IP "tar xzf - -C /home/ubuntu/app/"
log "Código copiado"

# ══════════════════════════════════════════════════════════════
# 5. Virtualenv + dependencias Python
# ══════════════════════════════════════════════════════════════
info "Instalando dependencias Python..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    python3 -m venv /home/ubuntu/venv
    /home/ubuntu/venv/bin/pip install --quiet --no-cache-dir --upgrade pip
    /home/ubuntu/venv/bin/pip install --quiet --no-cache-dir -r /home/ubuntu/app/requirements.txt
    rm -rf /home/ubuntu/.cache/pip
    echo '→ Dependencias OK'
"
log "Dependencias instaladas"

# ══════════════════════════════════════════════════════════════
# 6. Generar VAULT_KEY y escribir .env
# ══════════════════════════════════════════════════════════════
info "Generando variables de entorno..."
VAULT_KEY=$(ssh $SSH_OPTS ubuntu@$APP_IP \
    "/home/ubuntu/venv/bin/python -c \
    'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")

# MONGO_URI apunta al mongos corriendo en localhost (Docker)
ssh $SSH_OPTS ubuntu@$APP_IP "cat > /home/ubuntu/app/.env << EOF
DJANGO_SETTINGS_MODULE=monitoring.settings
DJANGO_SECRET_KEY=bite-sprint3-$(date +%s)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=monitoring_db
DB_USER=monitoring_user
DB_PASSWORD=isis2503
REDIS_HOST=localhost
REDIS_PORT=6379
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=monitoring_user
RABBITMQ_PASSWORD=isis2503
MONGO_URI=mongodb://localhost:27017/bite_db
VAULT_KEY=$VAULT_KEY
AMBIENTE=dev
SMTP_USER=
SMTP_APP_PASSWORD=
ADMIN_EMAIL=
EOF
chmod 600 /home/ubuntu/app/.env"
log "Variables de entorno configuradas"

# ══════════════════════════════════════════════════════════════
# 7. Migraciones Django
# ══════════════════════════════════════════════════════════════
info "Ejecutando migraciones Django..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    cd /home/ubuntu/app
    set -a && source .env && set +a
    /home/ubuntu/venv/bin/python manage.py migrate --noinput
    echo '→ Migraciones OK'
"
log "Migraciones aplicadas"

# ══════════════════════════════════════════════════════════════
# 8. Crear servicios systemd en EC2 principal
# ══════════════════════════════════════════════════════════════
info "Creando servicios systemd..."
ssh $SSH_OPTS ubuntu@$APP_IP "sudo bash -s" << 'ENDSSH'

VENV="/home/ubuntu/venv"
APP="/home/ubuntu/app"
ENV_FILE="/home/ubuntu/app/.env"

make_service() {
    local name="$1" desc="$2" cmd="$3" after="${4:-network.target}"
    cat > /etc/systemd/system/${name}.service << EOF
[Unit]
Description=${desc}
After=${after}

[Service]
User=ubuntu
WorkingDirectory=${APP}
EnvironmentFile=${ENV_FILE}
ExecStart=${cmd}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
}

GUNICORN="${VENV}/bin/gunicorn monitoring.wsgi:application"
PYTHON="${VENV}/bin/python"

make_service "bite-backend-1"  "BITE Django instancia 1 (8000)" \
    "${GUNICORN} --bind 0.0.0.0:8000 --workers 4 --timeout 120" \
    "network.target postgresql.service"

make_service "bite-backend-2"  "BITE Django instancia 2 (8002)" \
    "${GUNICORN} --bind 0.0.0.0:8002 --workers 4 --timeout 120" \
    "network.target postgresql.service"

make_service "bite-extractor"  "BITE Django extractor (8001)" \
    "${GUNICORN} --bind 0.0.0.0:8001 --workers 2 --timeout 120" \
    "network.target redis.service"

make_service "bite-celery"     "BITE Celery Worker" \
    "${VENV}/bin/celery -A Extractor.tasks.celery_app worker --loglevel=info --concurrency=4" \
    "network.target redis.service rabbitmq-server.service"

make_service "bite-detector"   "BITE Detector ASR29" \
    "${PYTHON} detector/consumer.py" \
    "network.target rabbitmq-server.service postgresql.service"

make_service "bite-revoker"    "BITE Revoker ASR29 (dev)" \
    "${PYTHON} revoker/consumer.py" \
    "network.target rabbitmq-server.service postgresql.service"

make_service "bite-notifier"   "BITE Notifier ASR29" \
    "${PYTHON} notifier/consumer.py" \
    "network.target rabbitmq-server.service postgresql.service"

make_service "bite-logstore"   "BITE Log Store ASR30" \
    "${PYTHON} log_handlers/log_store_consumer.py" \
    "network.target rabbitmq-server.service"

systemctl daemon-reload
systemctl enable \
    bite-backend-1 bite-backend-2 bite-extractor bite-celery \
    bite-detector bite-revoker bite-notifier bite-logstore
echo "→ Servicios systemd creados"
ENDSSH
log "Servicios systemd configurados"

# ══════════════════════════════════════════════════════════════
# 9. nginx
# ══════════════════════════════════════════════════════════════
info "Configurando nginx..."
ssh $SSH_OPTS ubuntu@$APP_IP "sudo bash -s" << 'ENDSSH'
    cp /home/ubuntu/app/nginx/nginx.conf /etc/nginx/nginx.conf
    nginx -t && systemctl restart nginx
    echo "→ nginx OK"
ENDSSH
log "nginx configurado"

# ══════════════════════════════════════════════════════════════
# 10. Arrancar servicios de la app
# ══════════════════════════════════════════════════════════════
info "Arrancando servicios de la app..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    sudo systemctl start \
        bite-backend-1 bite-backend-2 bite-extractor bite-celery \
        bite-detector bite-revoker bite-notifier bite-logstore
    sleep 5
    sudo systemctl is-active --quiet bite-backend-1 && echo '→ backends OK' || echo '→ backends FALLO'
"
log "App arrancada"

# ══════════════════════════════════════════════════════════════
# 11. Seed de datos
# ══════════════════════════════════════════════════════════════
info "Cargando datos de prueba..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    cd /home/ubuntu/app
    set -a && source .env && set +a
    /home/ubuntu/venv/bin/python seed_data.py
    /home/ubuntu/venv/bin/python scripts/seed_history.py
"
log "Datos de prueba cargados"

# ══════════════════════════════════════════════════════════════
# 12. Desplegar MongoDB shards en las 3 EC2s
# ══════════════════════════════════════════════════════════════
info "Desplegando MongoDB shards..."

deploy_shard() {
    local shard_ip="$1" shard_num="$2"
    info "  Desplegando shard $shard_num en $shard_ip..."

    # Esperar que Docker esté listo (instalado por user_data_shard.sh)
    ssh $SSH_OPTS ubuntu@$shard_ip "
        echo '→ Esperando Docker...'
        WAIT=0
        until grep -q 'Shard Bootstrap completado' /var/log/user_data.log 2>/dev/null; do
            WAIT=\$((WAIT+5)); echo \"  Bootstrap en progreso (\${WAIT}s)...\"; sleep 5
            [ \$WAIT -ge 300 ] && echo 'TIMEOUT bootstrap' && exit 1
        done
        echo '→ Bootstrap OK'
    "

    # Copiar docker-compose-shard.yml
    scp $SSH_OPTS \
        mongo_cluster/docker-compose-shard.yml \
        ubuntu@${shard_ip}:/home/ubuntu/docker-compose-shard.yml

    # Levantar el shard
    ssh $SSH_OPTS ubuntu@$shard_ip "
        cd /home/ubuntu
        SHARD_NUM=$shard_num docker compose -f docker-compose-shard.yml up -d
        sleep 10
        docker ps --format 'table {{.Names}}\t{{.Status}}' | grep shard
        echo '→ Shard $shard_num contenedores arriba'
    "
    log "  Shard $shard_num desplegado en $shard_ip"
}

deploy_shard "$SHARD1_IP" 1
deploy_shard "$SHARD2_IP" 2
deploy_shard "$SHARD3_IP" 3

# ══════════════════════════════════════════════════════════════
# 13. Desplegar Config Server + mongos en EC2 principal
# ══════════════════════════════════════════════════════════════
info "Desplegando Config Server y mongos en EC2 principal..."

ssh $SSH_OPTS ubuntu@$APP_IP "
    mkdir -p /home/ubuntu/mongo_cluster
"
scp $SSH_OPTS \
    mongo_cluster/docker-compose-configsvr.yml \
    ubuntu@${APP_IP}:/home/ubuntu/mongo_cluster/docker-compose-configsvr.yml

ssh $SSH_OPTS ubuntu@$APP_IP "
    cd /home/ubuntu/mongo_cluster
    sudo docker compose -f docker-compose-configsvr.yml up -d
    echo '→ Esperando que configsvr arranque (20s)...'
    sleep 20
    sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'configsvr|mongos'
"
log "Config Server y mongos arrancados"

# ══════════════════════════════════════════════════════════════
# 14. Inicializar replica sets y sharding
# ══════════════════════════════════════════════════════════════
info "Inicializando Config Server Replica Set..."
ssh $SSH_OPTS ubuntu@$APP_IP "
sudo docker exec configsvr1 mongosh --port 27019 --quiet --eval \"
try {
  rs.initiate({
    _id: 'rs_config',
    configsvr: true,
    members: [
      { _id: 0, host: 'configsvr1:27019', priority: 2 },
      { _id: 1, host: 'configsvr2:27020', priority: 1 },
      { _id: 2, host: 'configsvr3:27021', priority: 1 }
    ],
    settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
  });
  print('Config RS iniciado');
} catch(e) {
  if (e.codeName === 'AlreadyInitialized' || e.message.includes('already initialized')) {
    print('Config RS ya inicializado, continuando...');
  } else { throw e; }
}
\"
" || true

info "Esperando primario del Config RS..."
for i in $(seq 1 24); do
    STATUS=$(ssh $SSH_OPTS ubuntu@$APP_IP \
        "sudo docker exec configsvr1 mongosh --port 27019 --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null" \
        || echo "false")
    if [ "$STATUS" = "true" ]; then
        log "Config RS primario elegido (intento $i)"
        break
    fi
    warn "Esperando primario config RS ($i/24)..."
    sleep 5
done

info "Reiniciando mongos para reconectar al Config RS..."
ssh $SSH_OPTS ubuntu@$APP_IP "sudo docker restart mongos"
sleep 5

info "Esperando que mongos conecte al Config RS..."
for i in $(seq 1 24); do
    STATUS=$(ssh $SSH_OPTS ubuntu@$APP_IP \
        "sudo docker exec mongos mongosh --port 27017 --quiet --eval \
        'try { db.getSiblingDB(\"config\").shards.find().toArray(); print(\"ok\"); } catch(e) { print(\"err\"); }' \
        2>/dev/null" || echo "err")
    if echo "$STATUS" | grep -q "^ok$"; then
        log "mongos conectado al Config RS (intento $i)"
        break
    fi
    warn "mongos no conectado todavia ($i/24)..."
    sleep 5
done

info "Inicializando Shard 1 Replica Set (${SHARD1_PRIV})..."
ssh $SSH_OPTS ubuntu@$SHARD1_IP "
docker exec shard1a mongosh --port 27018 --quiet --eval \"
try {
  rs.initiate({
    _id: 'rs_shard1',
    members: [
      { _id: 0, host: '${SHARD1_PRIV}:27018', priority: 2 },
      { _id: 1, host: '${SHARD1_PRIV}:27019', priority: 1 },
      { _id: 2, host: '${SHARD1_PRIV}:27020', priority: 1 }
    ],
    settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
  });
  print('Shard 1 RS iniciado');
} catch(e) {
  if (e.codeName === 'AlreadyInitialized' || e.message.includes('already initialized')) {
    print('Shard 1 RS ya inicializado, continuando...');
  } else { throw e; }
}
\"
" || true

info "Inicializando Shard 2 Replica Set (${SHARD2_PRIV})..."
ssh $SSH_OPTS ubuntu@$SHARD2_IP "
docker exec shard2a mongosh --port 27018 --quiet --eval \"
try {
  rs.initiate({
    _id: 'rs_shard2',
    members: [
      { _id: 0, host: '${SHARD2_PRIV}:27018', priority: 2 },
      { _id: 1, host: '${SHARD2_PRIV}:27019', priority: 1 },
      { _id: 2, host: '${SHARD2_PRIV}:27020', priority: 1 }
    ],
    settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
  });
  print('Shard 2 RS iniciado');
} catch(e) {
  if (e.codeName === 'AlreadyInitialized' || e.message.includes('already initialized')) {
    print('Shard 2 RS ya inicializado, continuando...');
  } else { throw e; }
}
\"
" || true

info "Inicializando Shard 3 Replica Set (${SHARD3_PRIV})..."
ssh $SSH_OPTS ubuntu@$SHARD3_IP "
docker exec shard3a mongosh --port 27018 --quiet --eval \"
try {
  rs.initiate({
    _id: 'rs_shard3',
    members: [
      { _id: 0, host: '${SHARD3_PRIV}:27018', priority: 2 },
      { _id: 1, host: '${SHARD3_PRIV}:27019', priority: 1 },
      { _id: 2, host: '${SHARD3_PRIV}:27020', priority: 1 }
    ],
    settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
  });
  print('Shard 3 RS iniciado');
} catch(e) {
  if (e.codeName === 'AlreadyInitialized' || e.message.includes('already initialized')) {
    print('Shard 3 RS ya inicializado, continuando...');
  } else { throw e; }
}
\"
" || true

info "Esperando primarios de los 3 shards..."
for shard_num in 1 2 3; do
    eval "SHARD_IP=\$SHARD${shard_num}_IP"
    CONTAINER="shard${shard_num}a"
    for i in $(seq 1 24); do
        STATUS=$(ssh $SSH_OPTS ubuntu@$SHARD_IP \
            "docker exec $CONTAINER mongosh --port 27018 --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null" \
            || echo "false")
        if [ "$STATUS" = "true" ]; then
            log "Shard $shard_num primario elegido (intento $i)"
            break
        fi
        warn "Esperando primario shard $shard_num ($i/24)..."
        sleep 5
    done
done

info "Registrando shards en mongos y habilitando sharding..."
ssh $SSH_OPTS ubuntu@$APP_IP "
sudo docker exec mongos mongosh --port 27017 --quiet --eval \"
function addShardSafe(connStr) {
  try { sh.addShard(connStr); }
  catch(e) {
    if (e.message && e.message.includes('already')) {
      print('Shard ya registrado: ' + connStr);
    } else { throw e; }
  }
}
addShardSafe('rs_shard1/${SHARD1_PRIV}:27018,${SHARD1_PRIV}:27019,${SHARD1_PRIV}:27020');
addShardSafe('rs_shard2/${SHARD2_PRIV}:27018,${SHARD2_PRIV}:27019,${SHARD2_PRIV}:27020');
addShardSafe('rs_shard3/${SHARD3_PRIV}:27018,${SHARD3_PRIV}:27019,${SHARD3_PRIV}:27020');

try { sh.enableSharding('bite_db'); } catch(e) { print('sharding ya habilitado'); }

db = db.getSiblingDB('bite_db');
try { db.createCollection('places'); } catch(e) {}
try { db.places.createIndex({ category: 1, _id: 1 }); } catch(e) {}
try { sh.shardCollection('bite_db.places', { category: 1, _id: 1 }); } catch(e) { print('places ya sharded'); }

print('Cluster sharded listo');
sh.status();
\"
"
log "Cluster MongoDB sharded configurado"

# ══════════════════════════════════════════════════════════════
# 15. Seed de datos MongoDB
# ══════════════════════════════════════════════════════════════
info "Cargando datos en MongoDB (places)..."
ssh $SSH_OPTS ubuntu@$APP_IP "
    cd /home/ubuntu/app
    set -a && source .env && set +a
    /home/ubuntu/venv/bin/python scripts/seed_places.py 2>/dev/null || \
    /home/ubuntu/venv/bin/python manage.py seed_places 2>/dev/null || \
    echo '→ Seed places omitido (script no encontrado)'
"
log "Datos MongoDB cargados"

# ══════════════════════════════════════════════════════════════
# 16. Health checks
# ══════════════════════════════════════════════════════════════
info "Verificando servicios..."
sleep 5

check() {
    local label="$1" url="$2"
    local resp=$(curl -sf "$url" 2>/dev/null || echo "ERROR")
    if echo "$resp" | grep -qiE "ok|places|credentials|status|health"; then
        log "$label → OK"
    else
        warn "$label → FALLO ($url)"
    fi
}

check "Health (puerto 80)"      "http://$APP_IP/health/"
check "Report empresa 1"        "http://$APP_IP/api/v1/report/1/"
check "Dashboard empresa 1"     "http://$APP_IP/api/v1/dashboard/1/"
check "Extractor (puerto 8001)" "http://$APP_IP:8001/health/"
check "Credentials list"        "http://$APP_IP/credentials/client-test-001/"
check "Places (MongoDB)"        "http://$APP_IP/places/health/"
check "Audit log (ASR29)"       "http://$APP_IP/credentials/audit/"

# ══════════════════════════════════════════════════════════════
# 17. Resumen final
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  DESPLIEGUE COMPLETO — Sprint 2 + Sprint 3 (4 EC2s)${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}── Instancias AWS ────────────────────────────────────────${NC}"
echo -e "  App:     $APP_IP  (Django + todos los servicios)"
echo -e "  Shard 1: $SHARD1_IP"
echo -e "  Shard 2: $SHARD2_IP"
echo -e "  Shard 3: $SHARD3_IP"
echo ""
echo -e "  ${CYAN}── Sprint 2 (Latencia / Escalabilidad) ─────────────────${NC}"
echo -e "  Health:       http://$APP_IP/health/"
echo -e "  Report:       http://$APP_IP/api/v1/report/1/"
echo -e "  Dashboard:    http://$APP_IP/api/v1/dashboard/1/"
echo -e "  Extractor:    http://$APP_IP:8001/api/v1/extract/"
echo ""
echo -e "  ${CYAN}── ASR29 (Vault de credenciales) ────────────────────────${NC}"
echo -e "  Registrar:    POST http://$APP_IP/credentials/register/"
echo -e "  Usar:         POST http://$APP_IP/credentials/use/"
echo -e "  Audit log:    http://$APP_IP/credentials/audit/"
echo ""
echo -e "  ${CYAN}── ASR30 (Enmascaramiento de logs) ──────────────────────${NC}"
echo -e "  Leak AWS key: http://$APP_IP/test/leak/aws-key/"
echo -e "  Leak JWT:     http://$APP_IP/test/leak/jwt/"
echo ""
echo -e "  ${CYAN}── Disponibilidad (MongoDB Sharded) ─────────────────────${NC}"
echo -e "  Places:       http://$APP_IP/places/"
echo -e "  Health Mongo: http://$APP_IP/places/health/"
echo -e "  Cluster:      mongos en $APP_IP:27017"
echo -e "  Shards:       $SHARD1_IP / $SHARD2_IP / $SHARD3_IP"
echo ""
echo -e "  ${YELLOW}┌─ JMeter ─────────────────────────────────────────────┐${NC}"
echo -e "  ${YELLOW}│  jmeter_latencia.jmx       HOST=$APP_IP PORT=80     │${NC}"
echo -e "  ${YELLOW}│  jmeter_escalabilidad.jmx  HOST=$APP_IP PORT=8001   │${NC}"
echo -e "  ${YELLOW}└──────────────────────────────────────────────────────┘${NC}"
echo ""
echo -e "  SSH app: ssh -i $KEY_PATH ubuntu@$APP_IP"
echo ""
