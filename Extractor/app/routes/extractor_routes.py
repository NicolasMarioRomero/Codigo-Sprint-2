"""
extractor_routes.py
API REST del agente extractor.
Expone endpoints para disparar extracciones y consultar su estado.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.tasks.extract_task import extract_metrics

router = APIRouter(prefix="/api/v1/extractor", tags=["extractor"])


class ExtractionRequest(BaseModel):
    company_id: int
    project_id: int
    provider: str  # 'aws' | 'azure'


@router.post("/extract")
def trigger_extraction(req: ExtractionRequest):
    """
    Encola una tarea de extracción de métricas cloud.
    La tarea se ejecuta de forma asíncrona con reintentos automáticos.
    Retorna el task_id para consultar el estado.
    """
    task = extract_metrics.delay(req.company_id, req.project_id, req.provider)
    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"Extracción encolada para empresa={req.company_id} proveedor={req.provider}",
    }


@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    """
    Consulta el estado de una tarea de extracción.
    Estados posibles: PENDING, STARTED, SUCCESS, FAILURE, RETRY
    """
    from app.tasks.extract_task import celery_app
    result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)

    return response


@router.post("/extract/sync")
def trigger_extraction_sync(req: ExtractionRequest):
    """
    Ejecuta la extracción de forma síncrona (útil para pruebas).
    En producción usar /extract para ejecución asíncrona.
    """
    try:
        result = extract_metrics(req.company_id, req.project_id, req.provider)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
