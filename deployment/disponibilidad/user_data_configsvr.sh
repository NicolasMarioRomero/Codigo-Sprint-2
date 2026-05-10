#!/bin/bash
# deployment/disponibilidad/user_data_configsvr.sh
# Levanta 3 nodos Config Server en la misma EC2 con Docker.
set -e
exec > /var/log/user_data_configsvr.log 2>&1

echo "=== Config Server Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io

systemctl enable docker
systemctl start docker

mkdir -p /data/configsvr/{1,2,3}

docker run -d --name configsvr1 --restart always \
  -p 27019:27019 \
  -v /data/configsvr/1:/data/db \
  mongo:6.0 mongod --configsvr --replSet rs_config --port 27019 --bind_ip_all

docker run -d --name configsvr2 --restart always \
  -p 27020:27020 \
  -v /data/configsvr/2:/data/db \
  mongo:6.0 mongod --configsvr --replSet rs_config --port 27020 --bind_ip_all

docker run -d --name configsvr3 --restart always \
  -p 27021:27021 \
  -v /data/configsvr/3:/data/db \
  mongo:6.0 mongod --configsvr --replSet rs_config --port 27021 --bind_ip_all

sleep 20

MY_IP=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

docker exec configsvr1 mongosh --port 27019 --eval "
rs.initiate({
  _id: 'rs_config',
  configsvr: true,
  members: [
    { _id: 0, host: '${MY_IP}:27019', priority: 2 },
    { _id: 1, host: '${MY_IP}:27020', priority: 1 },
    { _id: 2, host: '${MY_IP}:27021', priority: 1 }
  ],
  settings: { electionTimeoutMillis: 2000, heartbeatIntervalMillis: 500 }
});
"

echo "=== Config Server RS iniciado: $(date) ==="
