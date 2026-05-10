"""
log_handlers/log_store_consumer.py — ASR30
Consumidor RabbitMQ que persiste los logs en archivos con rotación diaria.
Los mensajes provienen del RabbitMQHandler (ya enmascarados por SensitiveDataFilter).

Exchange : logs        (topic, durable)
Queue    : log_store.queue
Binding  : logs.#

Archivos: /var/log/bite/<ambiente>/app.log  — rotación diaria (TimedRotatingFileHandler)
"""
import json
import logging
import logging.handlers
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()  # no-op si ya fue inicializado

import pika
from django.conf import settings

# ── Logger de este consumidor (stdout only — no re-publicar en RabbitMQ) ─────
local_logger = logging.getLogger('log_store')
local_logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
local_logger.addHandler(_ch)

# ── Cache de handlers por ambiente ───────────────────────────────────────────
_ambiente_handlers: dict = {}

BASE_LOG_DIR = os.getenv('LOG_STORE_BASE_DIR', '/var/log/bite')


def _get_handler(ambiente: str) -> logging.Handler:
    """
    Devuelve (creando si no existe) un TimedRotatingFileHandler por ambiente.
    Rota diariamente y conserva los últimos 30 archivos.
    """
    if ambiente not in _ambiente_handlers:
        log_dir = os.path.join(BASE_LOG_DIR, ambiente)
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, 'app.log')
        h = logging.handlers.TimedRotatingFileHandler(
            path,
            when='D',           # rotación diaria
            interval=1,
            backupCount=30,
            encoding='utf-8',
            utc=True,
        )
        h.setFormatter(logging.Formatter('%(message)s'))
        _ambiente_handlers[ambiente] = h
        local_logger.info("Handler creado para ambiente '%s' → %s", ambiente, path)
    return _ambiente_handlers[ambiente]


def _callback(ch, method, properties, body):
    try:
        data      = json.loads(body)
        level     = data.get('level', 'INFO').upper()
        message   = data.get('message', '')
        timestamp = data.get('timestamp', '')
        ambiente  = data.get('ambiente', 'dev')

        line = f"[{timestamp}] [{level}] {message}"

        handler = _get_handler(ambiente)
        record  = logging.makeLogRecord({'msg': line, 'levelname': level})
        handler.emit(record)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        local_logger.error("Error en log_store_consumer callback: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consuming():
    rb       = settings.RABBITMQ
    exchange = rb['EXCHANGE_LOGS']   # 'logs'

    creds  = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
    params = pika.ConnectionParameters(
        host=rb['HOST'],
        port=rb.get('PORT', 5672),
        credentials=creds,
    )

    conn    = pika.BlockingConnection(params)
    channel = conn.channel()

    channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
    channel.queue_declare(queue='log_store.queue', durable=True)
    channel.queue_bind(exchange=exchange, queue='log_store.queue', routing_key='logs.#')

    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue='log_store.queue', on_message_callback=_callback, auto_ack=False)

    local_logger.info("Log store escuchando en 'log_store.queue' (binding: logs.#)")
    channel.start_consuming()


if __name__ == '__main__':
    start_consuming()
