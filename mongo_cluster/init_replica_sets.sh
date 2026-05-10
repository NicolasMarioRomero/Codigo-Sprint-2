#!/bin/bash
# mongo_cluster/init_replica_sets.sh
# Inicializa los 4 Replica Sets (3 shards + config server) — MongoDB 7.0
# electionTimeoutMillis=2000 garantiza failover < 5 segundos.
#
# TOPOLOGÍA:
#   Shard EC2 (3 instancias independientes):  puertos 27018/27019/27020
#   Config Server EC2 (1 instancia):          puertos 27019/27020/27021
#
# USO: bash init_replica_sets.sh <SHARD1_HOST> <SHARD2_HOST> <SHARD3_HOST> <CONFIGSVR_HOST>
# Ejemplo: bash init_replica_sets.sh 10.0.1.10 10.0.1.11 10.0.1.12 10.0.1.13

set -e

SHARD1_HOST="${1:-localhost}"
SHARD2_HOST="${2:-localhost}"
SHARD3_HOST="${3:-localhost}"
CONFIGSVR_HOST="${4:-localhost}"

echo "========================================"
echo "Inicializando Config Server Replica Set"
echo "========================================"
mongosh --host "$CONFIGSVR_HOST" --port 27019 --eval "
rs.initiate({
  _id: 'rs_config',
  configsvr: true,
  members: [
    { _id: 0, host: '${CONFIGSVR_HOST}:27019', priority: 2 },
    { _id: 1, host: '${CONFIGSVR_HOST}:27020', priority: 1 },
    { _id: 2, host: '${CONFIGSVR_HOST}:27021', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

sleep 5

echo "========================================"
echo "Inicializando Shard 1 Replica Set"
echo "========================================"
mongosh --host "$SHARD1_HOST" --port 27018 --eval "
rs.initiate({
  _id: 'rs_shard1',
  members: [
    { _id: 0, host: '${SHARD1_HOST}:27018', priority: 2 },
    { _id: 1, host: '${SHARD1_HOST}:27019', priority: 1 },
    { _id: 2, host: '${SHARD1_HOST}:27020', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

echo "========================================"
echo "Inicializando Shard 2 Replica Set"
echo "========================================"
mongosh --host "$SHARD2_HOST" --port 27018 --eval "
rs.initiate({
  _id: 'rs_shard2',
  members: [
    { _id: 0, host: '${SHARD2_HOST}:27018', priority: 2 },
    { _id: 1, host: '${SHARD2_HOST}:27019', priority: 1 },
    { _id: 2, host: '${SHARD2_HOST}:27020', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

echo "========================================"
echo "Inicializando Shard 3 Replica Set"
echo "========================================"
mongosh --host "$SHARD3_HOST" --port 27018 --eval "
rs.initiate({
  _id: 'rs_shard3',
  members: [
    { _id: 0, host: '${SHARD3_HOST}:27018', priority: 2 },
    { _id: 1, host: '${SHARD3_HOST}:27019', priority: 1 },
    { _id: 2, host: '${SHARD3_HOST}:27020', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

echo ""
echo "Esperando que los primarios sean elegidos (15s)..."
sleep 15

echo "========================================="
echo "Replica Sets inicializados correctamente."
echo "Ejecutar ahora: bash init_sharding.sh"
echo "========================================="
