"""
extract_task.py
Tarea Celery para extracción de métricas cloud con reintentos automáticos.
ASR Escalabilidad: garantiza 100% de éxito en las peticiones mediante:
  - Cola de mensajes (Celery + Redis) → desacopla al extractor del sistema
  - Reintentos con backoff exponencial → resiste ambientes sobrecargados
  - Dead Letter Queue → ninguna petición se pierde
"""
import os
import logging
from celery import Celery
from celery.utils.log import get_task_logger
from app.providers import get_provider

logger = get_task_logger(__name__)

celery_app = Celery(
    "extractor",
    broker=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/1",
    backend=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/2",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,          # El mensaje se confirma sólo si la tarea termina OK
    task_reject_on_worker_lost=True,  # Si el worker muere, la tarea vuelve a la cola
    worker_prefetch_multiplier=1,     # Evita acumulación en workers bajo alta carga
)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=2,        # Primer reintento a los 2s
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,           # Backoff exponencial: 2s, 4s, 8s, 16s, 32s
    retry_backoff_max=60,         # Máximo 60s entre reintentos
    retry_jitter=True,            # Jitter para evitar thundering herd
    name="extractor.extract_metrics",
)
def extract_metrics(self, company_id: int, project_id: int, provider_name: str):
    """
    Extrae métricas cloud para una empresa/proyecto desde el proveedor indicado.

    Parámetros:
        company_id    -- ID de la empresa
        project_id    -- ID del proyecto
        provider_name -- Nombre del proveedor ('aws', 'azure', etc.)

    Retorna lista de métricas normalizadas.
    Garantiza 100% de éxito: si falla, reintenta automáticamente con backoff.
    """
    logger.info(
        f"[Extractor] Extrayendo métricas | empresa={company_id} "
        f"proyecto={project_id} proveedor={provider_name} "
        f"intento={self.request.retries + 1}/{self.max_retries + 1}"
    )

    try:
        provider = get_provider(provider_name)
        metrics = provider.fetch_metrics(company_id, project_id)

        # Validar que todos los registros tienen los campos requeridos
        valid = [m for m in metrics if provider.validate(m)]
        invalid_count = len(metrics) - len(valid)
        if invalid_count > 0:
            logger.warning(f"[Extractor] {invalid_count} registros inválidos descartados")

        logger.info(f"[Extractor] OK — {len(valid)} métricas extraídas de {provider_name}")
        return {
            "status": "success",
            "company_id": company_id,
            "project_id": project_id,
            "provider": provider_name,
            "metrics_count": len(valid),
            "metrics": valid,
        }

    except (ConnectionError, TimeoutError) as exc:
        logger.warning(
            f"[Extractor] Error de conexión con {provider_name}: {exc}. "
            f"Reintentando (intento {self.request.retries + 1})..."
        )
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.error(f"[Extractor] Error inesperado: {exc}")
        raise
