#!/bin/bash
# deployment/disponibilidad/user_data_mongos.sh
# Levanta mongos y registra los shards.
# Variables: CONFIGSVR_HOST, SHARD1_HOST, SHARD2_HOST, SHARD3_HOST
set -e
exec > /var/log/user_data_mongos.log 2>&1

echo "=== mongos Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io

systemctl enable docker
systemctl start docker

# Esperar a que los config servers estén listos
sleep 60

docker run -d --name mongos --restart always \
  -p 27017:27017 \
  mongo:6.0 mongos \
    --configdb "rs_config/${CONFIGSVR_HOST}:27019,${CONFIGSVR_HOST}:27020,${CONFIGSVR_HOST}:27021" \
    --port 27017 \
    --bind_ip_all

sleep 30

# Registrar shards y configurar sharding
docker exec mongos mongosh --port 27017 --eval "
sh.addShard('rs_shard1/${SHARD1_HOST}:27101,${SHARD1_HOST}:27102,${SHARD1_HOST}:27103');
sh.addShard('rs_shard2/${SHARD2_HOST}:27201,${SHARD2_HOST}:27202,${SHARD2_HOST}:27203');
sh.addShard('rs_shard3/${SHARD3_HOST}:27301,${SHARD3_HOST}:27302,${SHARD3_HOST}:27303');

sh.enableSharding('bite_db');

db = db.getSiblingDB('bite_db');
db.createCollection('places');
db.places.createIndex({ category: 1, _id: 1 });
sh.shardCollection('bite_db.places', { category: 1, _id: 1 });

print('Cluster configurado.');
sh.status();
"

echo "=== mongos listo: $(date) ==="
