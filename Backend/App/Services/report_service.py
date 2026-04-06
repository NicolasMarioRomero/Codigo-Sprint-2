import json
from App.Cache.redis_client import redis_client
from App.db.database import SessionLocal
from App.Models.report import Report

CACHE_TTL = 60  # segundos — táctica: caché en memoria


def get_report(company_id: int):
    cache_key = f"report:{company_id}"

    # 1. Buscar en caché (táctica: caché en memoria)
    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "data": json.loads(cached)}

    # 2. Si no está en caché → consultar DB
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
    Usa caché agresiva (TTL 30s) para minimizar latencia bajo carga.
    """
    cache_key = f"dashboard:{company_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "summary": json.loads(cached)}

    db = SessionLocal()
    try:
        rows = (
            db.query(Report)
            .filter(Report.company_id == company_id)
            .all()
        )

        total_cost = sum(r.cost for r in rows)
        total_usage = sum(r.usage for r in rows)
        services = list({r.service_name for r in rows})
        project_count = len({r.project_id for r in rows})

        summary = {
            "company_id": company_id,
            "total_cost": round(total_cost, 2),
            "total_usage": round(total_usage, 2),
            "services": services,
            "project_count": project_count,
            "record_count": len(rows),
        }

        redis_client.setex(cache_key, 30, json.dumps(summary))

        return {"source": "db", "summary": summary}
    finally:
        db.close()
