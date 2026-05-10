"""
detector/consumer.py — ASR29
Consumidor RabbitMQ que escucha usos de credenciales y aplica las reglas de
detección de anomalías. Si detecta una anomalía publica dos mensajes:
  - credential.revoke.<ambiente>.<credential_id>  → para el revoker
  - security.alert.<client_id>                    → para el notifier

Exchange entrada:  security_events (topic)
Queue:             detector.queue
Binding:           credential.usage.#
"""
import json
import logging
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()  # no-op si ya fue inicializado por gunicorn/systemd

import pika
from django.conf import settings
from credentials.models import Credential, CredentialUsage
from .anomaly_rules import evaluate
from .publisher import publish_anomaly

logger = logging.getLogger(__name__)

QUEUE_NAME = 'detector.queue'
BINDING_KEY = 'credential.usage.#'


def _callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        credential_id = data['credential_id']
        usage_id = data['usage_id']

        # Obtener objetos desde BD para enriquecer el evento
        cred = Credential.objects.get(credential_id=credential_id, is_active=True)
        usage = CredentialUsage.objects.get(id=usage_id)

        # Construir el evento como dict para evaluate()
        event = {
            'credential_id': cred.credential_id,
            'client_id':     cred.client_id,
            'ambiente':      cred.ambiente,
            'provider':      cred.provider,
            'geo_country':   usage.geo_country,
            'source_ip':     usage.source_ip,
            'endpoint':      usage.endpoint,
            'timestamp':     usage.timestamp.isoformat(),
        }

        anomalies = evaluate(event)
        if anomalies:
            logger.warning(
                "Anomalía detectada en credencial %s: %d regla(s)",
                credential_id, len(anomalies),
            )
            publish_anomaly(event, anomalies)
        else:
            logger.info("Uso normal para %s", credential_id)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Credential.DoesNotExist:
        logger.error("Credencial no encontrada o ya revocada: %s", data.get('credential_id'))
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as exc:
        logger.error("Error en detector callback: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consuming():
    rb = settings.RABBITMQ
    exchange = rb['EXCHANGE_SECURITY']

    credentials = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
    params = pika.ConnectionParameters(
        host=rb['HOST'],
        port=rb.get('PORT', 5672),
        credentials=credentials,
    )

    conn = pika.BlockingConnection(params)
    ch = conn.channel()

    ch.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(exchange=exchange, queue=QUEUE_NAME, routing_key=BINDING_KEY)

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_callback, auto_ack=False)

    logger.info("Detector escuchando en '%s' con binding '%s'", QUEUE_NAME, BINDING_KEY)
    ch.start_consuming()


if __name__ == '__main__':
    start_consuming()
