#!/bin/bash
# deployment/asr29/user_data_rabbit.sh
# Instala y configura RabbitMQ en Ubuntu 22.04 para ASR29.
set -e
exec > /var/log/user_data_rabbit.log 2>&1

echo "=== RabbitMQ Bootstrap: $(date) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl gnupg

# Instalar Erlang + RabbitMQ desde repositorio oficial
curl -1sLf 'https://packagecloud.io/rabbitmq/rabbitmq-server/gpgkey' | apt-key add -
curl -1sLf 'https://packagecloud.io/rabbitmq/erlang/gpgkey' | apt-key add -

apt-get install -y erlang-base erlang-asn1 erlang-crypto erlang-eldap erlang-ftp \
  erlang-inets erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
  erlang-runtime-tools erlang-snmp erlang-ssl erlang-syntax-tools erlang-tftp \
  erlang-tools erlang-xmerl

curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.deb.sh | bash
apt-get install -y rabbitmq-server

# Habilitar management plugin
rabbitmq-plugins enable rabbitmq_management

# Usuario para la app
rabbitmqctl add_user bite bitepass 2>/dev/null || true
rabbitmqctl set_permissions -p / bite ".*" ".*" ".*"
rabbitmqctl set_user_tags bite administrator

# Exchanges duraderos
sleep 5
rabbitmqadmin declare exchange --vhost=/ name=security.alerts type=topic durable=true
rabbitmqadmin declare exchange --vhost=/ name=logs.exchange type=topic durable=true

systemctl enable rabbitmq-server
systemctl start rabbitmq-server

echo "=== RabbitMQ listo: $(date) ==="
