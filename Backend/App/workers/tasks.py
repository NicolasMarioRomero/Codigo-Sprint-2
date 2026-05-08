from celery import Celery
import os

celery_app = Celery(
    "tasks",
    broker=f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/0"
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def generate_heavy_report(self, company_id: int):
    """
    Tarea asíncrona para análisis pesado.
    Se ejecuta en background para no bloquear el Report Service.
    """
    try:
        import time
        time.sleep(2)  # Simula procesamiento pesado
        return {"status": "done", "company_id": company_id}
    except Exception as exc:
        raise self.retry(exc=exc)
