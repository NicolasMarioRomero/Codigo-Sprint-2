"""
revoker/consumer.py — ASR29
Consumidor RabbitMQ que escucha mensajes de revocación y revoca la credencial
comprometida en PostgreSQL + registra un AuditLog.

Se despliega UNA instancia por ambiente (dev/test/prod).
El ambiente se configura con la variable de entorno AMBIENTE (default: dev).

Exchange: security_events (topic)
Queue:    revoker.<AMBIENTE>.queue
Binding:  credential.revoke.<AMBIENTE>.#
"""
import json
import logging
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

import pika
from django.conf import settings
from django.utils import timezone
from credentials.models import Credential, AuditLog

logger = logging.getLogger(__name__)

AMBIENTE    = os.environ.get('AMBIENTE', 'dev')
QUEUE_NAME  = f'revoker.{AMBIENTE}.queue'
BINDING_KEY = f'credential.revoke.{AMBIENTE}.#'


def _revoke(credential_id, details):
    """Marca la credencial como revocada y escribe en AuditLog."""
    try:
        cred = Credential.objects.get(credential_id=credential_id, is_active=True)
        cred.is_active = False
        cred.revoked_at = timezone.now()
        cred.save(update_fields=['is_active', 'revoked_at'])

        AuditLog.objects.create(
            event_type='REVOCATION',
            credential_id=credential_id,
            details=details,
        )
        logger.info("Credencial revocada: %s", credential_id)
        return True

    except Credential.DoesNotExist:
        logger.warning("Credencial ya revocada o inexistente: %s", credential_id)
        return False


def _callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        credential_id = data['credential_id']

        revoked = _revoke(credential_id, {
            'anomalies': data.get('anomalies', []),
            'usage': data.get('usage', {}),
            'client_id': data.get('client_id'),
            'ambiente': data.get('ambiente'),
        })

        if revoked:
            logger.warning("REVOCACIÓN completada para %s", credential_id)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        logger.error("Error en revoker callback: %s", exc)
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
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_callback)

    logger.info("Revoker escuchando en '%s' con binding '%s'", QUEUE_NAME, BINDING_KEY)
    ch.start_consuming()


if __name__ == '__main__':
    start_consuming()
