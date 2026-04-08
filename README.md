### Tácticas implementadas

**ASR Latencia (< 3s bajo 5000 usuarios):**
- Load Balancer + Múltiples copias de procesamiento (Nginx + 2 instancias FastAPI)
- Caché en memoria (Redis, TTL 30s para dashboard)
- Pool de conexiones SQL (SQLAlchemy pool_size=20, max_overflow=40)
- Agregación SQL (GROUP BY en DB, no en Python)
- Compresión gzip en Nginx

**ASR Escalabilidad (100% éxito bajo sobrecarga):**
- Patrón Strategy (CloudProvider abstracto → agnóstico al proveedor)
- Cola de mensajes (Celery + Redis)
- Reintentos con backoff exponencial (2^n + jitter, máx 5 reintentos)
- task_acks_late=True (mensaje confirmado solo si la tarea termina)
