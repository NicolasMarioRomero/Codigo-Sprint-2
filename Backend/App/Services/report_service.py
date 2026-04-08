import json
from sqlalchemy import func
from App.Cache.redis_client import redis_client
from App.db.database import SessionLocal
from App.Models.report import Report

CACHE_TTL = 60   # segundos — táctica: caché en memoria
DASHBOARD_TTL = 30  # TTL agresivo para dashboard


def get_report(company_id: int):
    cache_key = f"report:{company_id}"

    # 1. Buscar en caché (táctica: caché en memoria)
    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "data": json.loads(cached)}

    # 2. Si no está en caché → consultar DB (limitado a últimos 50 registros)
    db = SessionLocal()
    try:
        rows = (
            db.query(Report)
            .filter(Report.company_id == company_id)
            .order_by(Report.timestamp.desc())
            .limit(50)
            .all()
        )

        data = [
            {
                "id": r.id,
                "company_id": r.company_id,
                "project_id": r.project_id,
                "service_name": r.service_name,
                "provider": r.provider or "aws",
                "cost": r.cost,
                "usage": r.usage,
                "currency": r.currency,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]

        # 3. Guardar en caché para próximas peticiones
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))

        return {"source": "db", "data": data}
    finally:
        db.close()


def get_dashboard_summary(company_id: int):
    """
    Retorna métricas agregadas del dashboard.
    Táctica: Caché agresiva (TTL 30s) + Agregación SQL para minimizar latencia bajo carga.
    ASR Latencia: debe responder en < 3s bajo 5000 usuarios concurrentes.
    """
    cache_key = f"dashboard:{company_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "summary": json.loads(cached)}

    db = SessionLocal()
    try:
        # Totales en una sola query SQL (más eficiente que Python-side aggregation)
        totals = db.query(
            func.coalesce(func.sum(Report.cost), 0).label("total_cost"),
            func.coalesce(func.sum(Report.usage), 0).label("total_usage"),
            func.count(Report.id).label("record_count"),
            func.count(func.distinct(Report.project_id)).label("project_count"),
        ).filter(Report.company_id == company_id).one()

        # Breakdown por servicio — SQL GROUP BY (no Python loop)
        service_rows = (
            db.query(
                Report.service_name,
                func.sum(Report.cost).label("total_cost"),
            )
            .filter(Report.company_id == company_id)
            .group_by(Report.service_name)
            .all()
        )
        service_breakdown = {
            row.service_name: round(float(row.total_cost), 2)
            for row in service_rows
            if row.service_name
        }

        # Breakdown por proveedor — SQL GROUP BY
        provider_rows = (
            db.query(
                Report.provider,
                func.sum(Report.cost).label("total_cost"),
            )
            .filter(Report.company_id == company_id)
            .group_by(Report.provider)
            .all()
        )
        provider_breakdown = {
            (row.provider or "aws"): round(float(row.total_cost), 2)
            for row in provider_rows
        }

        summary = {
            "company_id": company_id,
            "total_cost": round(float(totals.total_cost), 2),
            "total_usage": round(float(totals.total_usage), 2),
            "record_count": totals.record_count,
            "project_count": totals.project_count,
            "service_breakdown": service_breakdown,
            "provider_breakdown": provider_breakdown,
        }

        # Guardar en caché (TTL 30s para dashboard)
        redis_client.setex(cache_key, DASHBOARD_TTL, json.dumps(summary))

        return {"source": "db", "summary": summary}
    finally:
        db.close()
