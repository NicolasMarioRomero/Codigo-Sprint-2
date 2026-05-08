#!/bin/bash
# deployment/disponibilidad/user_data_shard.sh
# Levanta 3 nodos mongod de un shard en la misma EC2 usando Docker.
# Variables: SHARD_ID (1/2/3), PORT_START (27101/27201/27301)
set -e
exec > /var/log/user_data_shard.log 2>&1

echo "=== Shard ${SHARD_ID} Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose

systemctl enable docker
systemctl start docker

RS_NAME="rs_shard${SHARD_ID}"
PORT1=${PORT_START}
PORT2=$((${PORT_START} + 1))
PORT3=$((${PORT_START} + 2))

mkdir -p /data/shard${SHARD_ID}/{a,b,c}

docker run -d --name shard${SHARD_ID}a --restart always \
  -p ${PORT1}:${PORT1} \
  -v /data/shard${SHARD_ID}/a:/data/db \
  mongo:6.0 mongod --shardsvr --replSet ${RS_NAME} --port ${PORT1} --bind_ip_all

docker run -d --name shard${SHARD_ID}b --restart always \
  -p ${PORT2}:${PORT2} \
  -v /data/shard${SHARD_ID}/b:/data/db \
  mongo:6.0 mongod --shardsvr --replSet ${RS_NAME} --port ${PORT2} --bind_ip_all

docker run -d --name shard${SHARD_ID}c --restart always \
  -p ${PORT3}:${PORT3} \
  -v /data/shard${SHARD_ID}/c:/data/db \
  mongo:6.0 mongod --shardsvr --replSet ${RS_NAME} --port ${PORT3} --bind_ip_all

echo "=== Esperando que los nodos inicien... ==="
sleep 20

# Obtener la IP privada de esta instancia
MY_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

# Inicializar el Replica Set con electionTimeoutMillis bajo
docker exec shard${SHARD_ID}a mongosh --port ${PORT1} --eval "
rs.initiate({
  _id: '${RS_NAME}',
  members: [
    { _id: 0, host: '${MY_IP}:${PORT1}', priority: 2 },
    { _id: 1, host: '${MY_IP}:${PORT2}', priority: 1 },
    { _id: 2, host: '${MY_IP}:${PORT3}', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

echo "=== Shard ${SHARD_ID} (${RS_NAME}) iniciado: $(date) ==="
