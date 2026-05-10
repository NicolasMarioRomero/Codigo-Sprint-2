"""
log_handlers/rabbit_handler.py — ASR30
Handler de logging de Python que publica cada registro (ya enmascarado) en
RabbitMQ para que el log_store_consumer los persista en archivos rotativos.

Exchange   : logs         (topic, durable)
Routing key: logs.<ambiente>.<level>   ej: logs.prod.warning

Uso en LOGGING (settings.py):
    'rabbit': {
        'class': 'log_handlers.rabbit_handler.RabbitMQHandler',
        'rabbit_host': 'localhost',
        'ambiente': 'dev',
        'filters': ['sanitize'],
        'formatter': 'standard',
    }
"""
import json
import logging
import threading
import pika


class RabbitMQHandler(logging.Handler):
    """
    Publica cada LogRecord en RabbitMQ como JSON.
    Conexión lazy, recreada automáticamente si se pierde.
    Thread-safe mediante Lock.
    """

    def __init__(self, rabbit_host='localhost', ambiente='dev', level=logging.NOTSET):
        """
        :param rabbit_host: host de RabbitMQ (ej: 'localhost' o IP de la EC2)
        :param ambiente:    entorno de despliegue ('dev', 'test', 'prod')
        :param level:       nivel mínimo de logging
        """
        super().__init__(level)
        self._rabbit_host = rabbit_host
        self._ambiente    = ambiente
        self._lock_conn   = threading.Lock()
        self._conn        = None
        self._channel     = None

    # ── Conexión lazy ─────────────────────────────────────────────────────────

    def _connect(self):
        from django.conf import settings
        rb = settings.RABBITMQ
        creds = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
        params = pika.ConnectionParameters(
            host=self._rabbit_host,
            port=rb.get('PORT', 5672),
            credentials=creds,
            connection_attempts=2,
            retry_delay=1,
        )
        self._conn    = pika.BlockingConnection(params)
        self._channel = self._conn.channel()
        self._channel.exchange_declare(
            exchange='logs',
            exchange_type='topic',
            durable=True,
        )

    def _ensure_connection(self):
        if self._conn is None or self._conn.is_closed:
            self._connect()

    # ── Emisión del log ───────────────────────────────────────────────────────

    def emit(self, record):
        try:
            import datetime
            msg = self.format(record)
            body = json.dumps({
                'level':     record.levelname,
                'logger':    record.name,
                'message':   msg,
                'timestamp': datetime.datetime.utcfromtimestamp(record.created).isoformat(),
                'module':    record.module,
                'funcName':  record.funcName,
                'lineno':    record.lineno,
                'ambiente':  self._ambiente,
            })
            routing_key = f"logs.{self._ambiente}.{record.levelname.lower()}"

            with self._lock_conn:
                self._ensure_connection()
                self._channel.basic_publish(
                    exchange='logs',
                    routing_key=routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json',
                    ),
                )
        except Exception:
            # No lanzar excepciones desde el handler para no romper el flujo
            self.handleError(record)

    def close(self):
        with self._lock_conn:
            try:
                if self._conn and not self._conn.is_closed:
                    self._conn.close()
            except Exception:
                pass
        super().close()
