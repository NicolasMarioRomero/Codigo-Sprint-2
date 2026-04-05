from App.Cache.redis_client import redis_client
from App.db.database import SessionLocal

def get_report(company_id: int):
    cache_key = f"report:{company_id}"

    # 1. Buscar en cache
    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "data": cached}

    # 2. Si no está en cache → consultar DB
    db = SessionLocal()
    
    result = db.execute(
        f"SELECT * FROM reports WHERE company_id = {company_id}"
    ).fetchall()