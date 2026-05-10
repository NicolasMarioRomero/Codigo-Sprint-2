"""
detector/publisher.py — ASR29
Publica eventos de anomalía en RabbitMQ → exchange security_events (topic).

Se publican DOS mensajes por cada anomalía detectada:
  1. credential.revoke.<ambiente>.<credential_id>  → escucha el revoker
  2. security.alert.<client_id>                    → escucha el notifier

Ambos mensajes llevan el mismo cuerpo JSON con toda la información del incidente.
"""
import json
import logging
import pika
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_connection():
    rb = settings.RABBITMQ
    credentials = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
    params = pika.ConnectionParameters(
        host=rb['HOST'],
        port=rb.get('PORT', 5672),
        credentials=credentials,
    )
    return pika.BlockingConnection(params)


def publish_anomaly(event, anomalies):
    """
    Publica dos mensajes de anomalía en el exchange de seguridad.

    :param event:     dict del evento de uso (credential_id, client_id,
                      ambiente, provider, geo_country, source_ip, endpoint, timestamp)
    :param anomalies: lista de dicts con detalles de cada regla disparada
    """
    exchange = settings.RABBITMQ['EXCHANGE_SECURITY']

    body = json.dumps({
        'credential_id': event['credential_id'],
        'client_id':     event['client_id'],
        'ambiente':      event['ambiente'],
        'provider':      event.get('provider'),
        'anomalies':     anomalies,
        'usage': {
            'source_ip':   event.get('source_ip'),
            'geo_country': event.get('geo_country'),
            'endpoint':    event.get('endpoint'),
            'timestamp':   event.get('timestamp'),
        },
    })

    # Routing keys a publicar
    rk_revoke = f"credential.revoke.{event['ambiente']}.{event['credential_id']}"
    rk_alert  = f"security.alert.{event['client_id']}"

    props = pika.BasicProperties(delivery_mode=2, content_type='application/json')

    try:
        conn = _get_connection()
        ch = conn.channel()
        ch.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)

        # 1 – Para el revoker
        ch.basic_publish(exchange=exchange, routing_key=rk_revoke,
                         body=body, properties=props)
        # 2 – Para el notifier
        ch.basic_publish(exchange=exchange, routing_key=rk_alert,
                         body=body, properties=props)

        conn.close()
        logger.info(
            "Anomalía publicada → rk_revoke=%s, rk_alert=%s (%d anomalía(s))",
            rk_revoke, rk_alert, len(anomalies),
        )
    except Exception as exc:
        logger.error("Error publicando anomalía en RabbitMQ: %s", exc)
