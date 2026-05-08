"""
notifier/consumer.py — ASR29
Consumidor RabbitMQ que escucha alertas de seguridad y envía notificaciones
por correo electrónico mediante SMTP (Gmail App Password).

Exchange: security_events (topic)
Queue:    notifier.queue
Binding:  security.alert.#

Variables de entorno requeridas:
  SMTP_USER         — dirección Gmail del remitente (ej: bite.alerts@gmail.com)
  SMTP_APP_PASSWORD — App Password de 16 caracteres generado en la cuenta Gmail
  ADMIN_EMAIL       — destinatario de las alertas (puede ser igual a SMTP_USER)
"""
import json
import logging
import os
import smtplib
import django
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

import pika
from django.conf import settings
from credentials.models import AuditLog

logger = logging.getLogger(__name__)

QUEUE_NAME  = 'notifier.queue'
BINDING_KEY = 'security.alert.#'

SMTP_HOST         = 'smtp.gmail.com'
SMTP_PORT         = 587
SMTP_USER         = os.environ.get('SMTP_USER', '')
SMTP_APP_PASSWORD = os.environ.get('SMTP_APP_PASSWORD', '')
ADMIN_EMAIL       = os.environ.get('ADMIN_EMAIL', SMTP_USER)


def _send_email_notification(credential_id, client_id, ambiente, anomalies):
    """
    Envía un correo de alerta usando SMTP con Gmail App Password.
    Retorna True si el envío fue exitoso, False en caso contrario.
    """
    if not SMTP_USER or not SMTP_APP_PASSWORD:
        logger.warning("SMTP_USER o SMTP_APP_PASSWORD no configurados — notificación omitida")
        return False

    rules_triggered = [a.get('rule', 'UNKNOWN') for a in anomalies]
    subject = f"[BITE.co] ALERTA: Credencial comprometida — {credential_id}"
    body = (
        f"ALERTA DE SEGURIDAD — Credencial comprometida\n"
        f"{'=' * 50}\n"
        f"  Credencial : {credential_id}\n"
        f"  Cliente    : {client_id}\n"
        f"  Ambiente   : {ambiente}\n"
        f"  Anomalías  : {', '.join(rules_triggered)}\n\n"
        f"Detalles:\n{json.dumps(anomalies, indent=2, ensure_ascii=False)}\n\n"
        f"La credencial ha sido revocada automáticamente."
    )

    msg = MIMEMultipart()
    msg['From']    = SMTP_USER
    msg['To']      = ADMIN_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_USER, [ADMIN_EMAIL], msg.as_string())
        logger.info("Notificación enviada a %s para credencial %s", ADMIN_EMAIL, credential_id)
        return True
    except Exception as exc:
        logger.error("Error enviando correo SMTP: %s", exc)
        return False


def _callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        credential_id = data['credential_id']
        client_id     = data.get('client_id', 'unknown')
        ambiente      = data.get('ambiente', 'unknown')
        anomalies     = data.get('anomalies', [])

        sent = _send_email_notification(credential_id, client_id, ambiente, anomalies)

        AuditLog.objects.create(
            event_type='NOTIFICATION',
            credential_id=credential_id,
            details={
                'notified': sent,
                'anomalies': anomalies,
                'client_id': client_id,
            },
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as exc:
        logger.error("Error en notifier callback: %s", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consuming():
    rb       = settings.RABBITMQ
    exchange = rb['EXCHANGE_SECURITY']   # security_events

    creds  = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
    params = pika.ConnectionParameters(
        host=rb['HOST'],
        port=rb.get('PORT', 5672),
        credentials=creds,
    )

    conn = pika.BlockingConnection(params)
    ch   = conn.channel()

    ch.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(exchange=exchange, queue=QUEUE_NAME, routing_key=BINDING_KEY)

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_callback, auto_ack=False)

    logger.info("Notifier escuchando en '%s' con binding '%s'", QUEUE_NAME, BINDING_KEY)
    ch.start_consuming()


if __name__ == '__main__':
    start_consuming()
