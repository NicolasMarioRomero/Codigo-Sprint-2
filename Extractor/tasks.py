"""
extractor/tasks.py
Tarea Celery para extracción de métricas cloud — migrada de FastAPI a Django.
Usa RabbitMQ como broker (ya disponible en Sprint 3) en lugar de Redis.

ASR Escalabilidad: garantiza 100% de éxito mediante:
  - Cola de mensajes (Celery + RabbitMQ) → desacopla extractor del sistema
  - Reintentos con backoff exponencial → resiste ambientes sobrecargados
  - task_acks_late=True → ninguna petición se pierde si el worker muere
"""
import logging
import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

from celery import Celery
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone

from .providers import get_provider
from reports.models import Report

logger = get_task_logger(__name__)

# ── App Celery — broker definido en settings.CELERY_BROKER_URL ───────────────
# Deploy básico → Redis. Experimentos ASR → RabbitMQ (vía RABBITMQ_HOST env).
celery_app = Celery('extractor', broker=settings.CELERY_BROKER_URL)
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_acks_late=True,               # Confirmar sólo si la tarea termina OK
    task_reject_on_worker_lost=True,   # Si el worker muere → tarea vuelve a la cola
    worker_prefetch_multiplier=1,      # Evita acumulación en workers bajo alta carga
)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=2,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,          # Backoff exponencial: 2s, 4s, 8s, 16s, 32s
    retry_backoff_max=60,
    retry_jitter=True,           # Evita thundering herd
    name='extractor.extract_metrics',
)
def extract_metrics(self, company_id: int, project_id: int, provider_name: str):
    """
    Extrae métricas cloud y las persiste en PostgreSQL.

    Parámetros:
        company_id    -- ID de la empresa
        project_id    -- ID del proyecto
        provider_name -- 'aws' | 'gcp'
    """
    attempt = self.request.retries + 1
    logger.info(
        "Extrayendo métricas | empresa=%s proyecto=%s proveedor=%s intento=%s/%s",
        company_id, project_id, provider_name, attempt, self.max_retries + 1,
    )

    try:
        provider = get_provider(provider_name)
        metrics = provider.fetch_metrics(company_id, project_id)

        valid = [m for m in metrics if provider.validate(m)]
        invalid = len(metrics) - len(valid)
        if invalid:
            logger.warning("%d registros inválidos descartados para %s", invalid, provider_name)

        # Persistir en PostgreSQL
        Report.objects.bulk_create([
            Report(
                company_id=m['company_id'],
                project_id=m['project_id'],
                service_name=m['service_name'],
                provider=m['provider'],
                cost=m['cost'],
                usage=m['usage'],
                currency=m.get('currency', 'USD'),
                timestamp=timezone.now(),
            )
            for m in valid
        ])

        logger.info("OK — %d métricas de %s persistidas en DB", len(valid), provider_name)
        return {
            'status':        'success',
            'company_id':    company_id,
            'project_id':    project_id,
            'provider':      provider_name,
            'metrics_count': len(valid),
        }

    except (ConnectionError, TimeoutError) as exc:
        logger.warning(
            "Error de conexión con %s: %s. Reintentando (intento %s)...",
            provider_name, exc, attempt,
        )
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.error("Error inesperado con %s: %s", provider_name, exc)
        raise
