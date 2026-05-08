"""
extractor/views.py
Endpoints REST para disparar extracciones — migrados de FastAPI a Django.
POST /api/v1/extract/
GET  /api/v1/extract/<task_id>/
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .tasks import extract_metrics

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(['POST'])
def trigger_extraction(request):
    """
    Encola una tarea de extracción asíncrona.
    Body: {"company_id": 1, "project_id": 10, "provider": "aws"}
    """
    try:
        data = json.loads(request.body)
        company_id   = int(data['company_id'])
        project_id   = int(data['project_id'])
        provider     = data.get('provider', 'aws')

        task = extract_metrics.delay(company_id, project_id, provider)
        logger.info("Extracción encolada: task_id=%s empresa=%s proveedor=%s",
                    task.id, company_id, provider)

        return JsonResponse({
            'status':   'queued',
            'task_id':  task.id,
            'company_id': company_id,
            'project_id': project_id,
            'provider': provider,
        }, status=202)

    except KeyError as e:
        return JsonResponse({'error': f'Campo requerido: {e}'}, status=400)
    except Exception as e:
        logger.error("Error encolando extracción: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(['GET'])
def task_status(request, task_id: str):
    """Consulta el estado de una tarea de extracción."""
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    return JsonResponse({
        'task_id': task_id,
        'status':  result.status,
        'result':  result.result if result.ready() else None,
    })
