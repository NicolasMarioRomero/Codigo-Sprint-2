#!/bin/bash
# mongo_cluster/init_sharding.sh
# Conecta al mongos, agrega los 3 shards y habilita sharding en la BD.
#
# USO: bash init_sharding.sh <MONGOS_HOST> <SHARD1_HOST> <SHARD2_HOST> <SHARD3_HOST>
# Ejemplo: bash init_sharding.sh 10.0.1.9 10.0.1.10 10.0.1.11 10.0.1.12

set -e

MONGOS_HOST="${1:-localhost}"
SHARD1_HOST="${2:-localhost}"
SHARD2_HOST="${3:-localhost}"
SHARD3_HOST="${4:-localhost}"

echo "============================================"
echo "Registrando shards en mongos ($MONGOS_HOST)"
echo "============================================"
mongosh --host "$MONGOS_HOST" --port 27017 --eval "
sh.addShard('rs_shard1/${SHARD1_HOST}:27018,${SHARD1_HOST}:27019,${SHARD1_HOST}:27020');
sh.addShard('rs_shard2/${SHARD2_HOST}:27018,${SHARD2_HOST}:27019,${SHARD2_HOST}:27020');
sh.addShard('rs_shard3/${SHARD3_HOST}:27018,${SHARD3_HOST}:27019,${SHARD3_HOST}:27020');

// Habilitar sharding en la base de datos
sh.enableSharding('bite_db');

// Crear colección e índice shard key antes de shardear
db = db.getSiblingDB('bite_db');
db.createCollection('places');
db.places.createIndex({ category: 1, _id: 1 });

// Shardear la colección por categoria + _id (compound shard key)
sh.shardCollection('bite_db.places', { category: 1, _id: 1 });

print('Sharding configurado correctamente.');
sh.status();
"

echo ""
echo "========================================="
echo "Cluster MongoDB sharded listo."
echo "  mongos: ${MONGOS_HOST}:27017"
echo "  BD: bite_db, colección: places"
echo "========================================="
