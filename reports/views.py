"""
reports/views.py
Endpoints REST de reportes — migrados de FastAPI a Django.
GET /api/v1/report/<company_id>/
GET /api/v1/dashboard/<company_id>/
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .services import get_report, get_dashboard_summary

logger = logging.getLogger(__name__)


@require_http_methods(['GET'])
def report(request, company_id: int):
    """Retorna los reportes de consumo cloud de una empresa."""
    try:
        return JsonResponse(get_report(company_id))
    except Exception as e:
        logger.error("Error en GET /report/%s: %s", company_id, e)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(['GET'])
def dashboard(request, company_id: int):
    """
    Dashboard con métricas agregadas.
    ASR Latencia: debe responder < 3s bajo 5000 usuarios concurrentes.
    """
    try:
        return JsonResponse(get_dashboard_summary(company_id))
    except Exception as e:
        logger.error("Error en GET /dashboard/%s: %s", company_id, e)
        return JsonResponse({'error': str(e)}, status=500)
