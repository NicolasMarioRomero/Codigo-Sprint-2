from celery import Celery

celery_app = Celery(
    "tasks",
    broker="redis://redis-endpoint:6379/0"
)

@celery_app.task
def generate_heavy_report(company_id):
    # análisis pesado
    import time
    time.sleep(5)

    return {"status": "done"}