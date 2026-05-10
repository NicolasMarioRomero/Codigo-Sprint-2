"""
reports/services.py
Lógica de negocio para reportes — migrada de report_service.py (FastAPI).
Mantiene la táctica de caché Redis (TTL 60s para reportes, 30s para dashboard).
ASR Latencia: responde < 3s bajo 5000 usuarios concurrentes gracias al caché.
"""
import json
import logging
from django.core.cache import cache
from django.db.models import Sum, Count
from .models import Report

logger = logging.getLogger(__name__)

CACHE_TTL     = 60   # segundos — reportes individuales
DASHBOARD_TTL = 30   # segundos — dashboard (agregaciones, más costosas)


def get_report(company_id: int) -> dict:
    """
    Retorna los últimos 50 reportes de una empresa.
    Táctica: primero busca en Redis; si no hay, consulta PostgreSQL y cachea.
    """
    cache_key = f'report:{company_id}'

    cached = cache.get(cache_key)
    if cached:
        logger.info("Cache HIT para report:%s", company_id)
        return {'source': 'cache', 'data': cached}

    rows = (
        Report.objects
        .filter(company_id=company_id)
        .order_by('-timestamp')[:50]
    )
    data = [r.to_dict() for r in rows]

    cache.set(cache_key, data, CACHE_TTL)
    logger.info("Cache MISS para report:%s — %d registros cargados de DB", company_id, len(data))
    return {'source': 'db', 'data': data}


def get_dashboard_summary(company_id: int) -> dict:
    """
    Métricas agregadas del dashboard.
    Táctica: caché agresiva (TTL 30s) + agregación SQL para minimizar latencia.
    ASR Latencia: debe responder < 3s bajo 5000 usuarios concurrentes.
    """
    cache_key = f'dashboard:{company_id}'

    cached = cache.get(cache_key)
    if cached:
        logger.info("Cache HIT para dashboard:%s", company_id)
        return {'source': 'cache', 'summary': cached}

    qs = Report.objects.filter(company_id=company_id)

    totals = qs.aggregate(
        total_cost=Sum('cost'),
        total_usage=Sum('usage'),
        record_count=Count('id'),
    )

    service_qs = (
        qs.values('service_name')
        .annotate(total_cost=Sum('cost'))
        .order_by()
    )
    service_breakdown = {
        row['service_name']: round(row['total_cost'] or 0, 2)
        for row in service_qs
        if row['service_name']
    }

    provider_qs = (
        qs.values('provider')
        .annotate(total_cost=Sum('cost'))
        .order_by()
    )
    provider_breakdown = {
        row['provider']: round(row['total_cost'] or 0, 2)
        for row in provider_qs
    }

    project_count = qs.values('project_id').distinct().count()

    summary = {
        'company_id':        company_id,
        'total_cost':        round(totals['total_cost'] or 0, 2),
        'total_usage':       round(totals['total_usage'] or 0, 2),
        'record_count':      totals['record_count'] or 0,
        'project_count':     project_count,
        'service_breakdown': service_breakdown,
        'provider_breakdown': provider_breakdown,
    }

    cache.set(cache_key, summary, DASHBOARD_TTL)
    logger.info("Cache MISS para dashboard:%s — agregación completada", company_id)
    return {'source': 'db', 'summary': summary}
