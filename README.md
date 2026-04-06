# BITE — Sprint 3: Experimentos de Arquitectura

## Estructura del proyecto

```
Codigo-Sprint-2/
├── Backend/                      # Report Service (ASR Latencia)
│   ├── App/
│   │   ├── Cache/redis_client.py      # Táctica: caché en memoria (Redis)
│   │   ├── db/database.py             # Conexión PostgreSQL (env vars)
│   │   ├── Models/report.py           # Modelo ORM - tabla reports
│   │   ├── Routes/reports.py          # GET /api/v1/dashboard/{id}
│   │   ├── Services/report_service.py # Lógica: cache → DB
│   │   └── workers/tasks.py           # Celery para análisis asíncrono
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── Extractor/                    # Agente Extractor (ASR Escalabilidad)
│   ├── app/
│   │   ├── providers/
│   │   │   ├── base_provider.py       # Interfaz agnóstica (Strategy)
│   │   │   ├── aws_provider.py        # Implementación AWS
│   │   │   ├── azure_provider.py      # Implementación Azure
│   │   │   └── __init__.py            # Registro de proveedores
│   │   ├── tasks/
│   │   │   └── extract_task.py        # Celery + reintentos + backoff exponencial
│   │   └── routes/
│   │       └── extractor_routes.py    # POST /api/v1/extractor/extract
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── nginx/
│   └── nginx.conf                # Load balancer (least_conn entre 2 instancias)
├── docker-compose.yml            # Orquestación local (simula infra AWS)
├── seed_data.py                  # Poblar BD con ~60.000 registros
├── locustfile.py                 # Prueba de carga Locust (5000 usuarios)
└── README.md
```

---

## Cómo ejecutar el experimento

### Opción A — Local con Docker Compose (simula la arquitectura)

```bash
# 1. Levantar todos los servicios
docker-compose up --build -d

# 2. Poblar la base de datos
pip install sqlalchemy psycopg2-binary
python seed_data.py

# 3. Verificar que el sistema responde
curl http://localhost/health
curl http://localhost/api/v1/dashboard/1

# 4. Ejecutar prueba de carga (ASR Latencia)
pip install locust
locust -f locustfile.py --host=http://localhost --headless \
       -u 5000 -r 100 --run-time 5m \
       --csv=resultados_latencia

# 5. Probar el extractor agnóstico (ASR Escalabilidad)
curl -X POST http://localhost:8001/api/v1/extractor/extract \
     -H "Content-Type: application/json" \
     -d '{"company_id": 1, "project_id": 1, "provider": "aws"}'

# Consultar estado de la tarea
curl http://localhost:8001/api/v1/extractor/status/{task_id}
```

### Opción B — AWS EC2 (infraestructura del diseño)

En la implementación sobre AWS, los servicios del `docker-compose.yml`
se reemplazan por servicios administrados:

| Docker Compose        | AWS equivalente               |
|-----------------------|-------------------------------|
| `db` (PostgreSQL)     | Amazon RDS (PostgreSQL)       |
| `redis`               | Amazon ElastiCache (Redis)    |
| `report_service_1/2`  | 2 instancias EC2 (t3.medium)  |
| `nginx`               | Application Load Balancer     |
| `extractor`           | EC2 (t3.small)                |
| `extractor_worker`    | EC2 (t3.small) con Celery     |

Variables de entorno en EC2:
```bash
export DATABASE_URL="postgresql://user:pass@rds-endpoint:5432/cloudcosts"
export REDIS_HOST="elasticache-endpoint"
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Criterios de éxito (ASRs)

| ASR           | Métrica        | Umbral      |
|---------------|----------------|-------------|
| Latencia      | P95 dashboard  | < 3000 ms   |
| Latencia      | Tasa de errores| 0%          |
| Escalabilidad | Éxito extracciones | 100%    |
| Escalabilidad | Agnóstico      | AWS ✅ Azure ✅ |

---

## Análisis esperado de resultados

### ASR Latencia — Por qué puede NO cumplirse localmente

Al ejecutar la prueba con 5000 usuarios concurrentes en un entorno local
con Docker Compose, **es probable que el P95 supere los 3 segundos** por:

1. **Recursos compartidos**: las 2 instancias del Report Service comparten
   CPU y RAM del mismo equipo físico. En AWS, cada EC2 tiene recursos dedicados.

2. **Red local vs red de datacenter**: la latencia entre contenedores en
   Docker es mayor a la latencia entre instancias EC2 en la misma VPC.

3. **PostgreSQL local no optimizado**: sin RDS, el motor de base de datos
   compite por recursos con el resto de servicios.

4. **Redis local sin cluster**: ElastiCache ofrece mayor throughput que
   un Redis en contenedor compartido.

**Cambios para cumplir el ASR en producción:**
- Desplegar en 2 instancias EC2 t3.medium dedicadas
- Usar Amazon RDS con read replicas
- Usar Amazon ElastiCache con cluster mode
- Ajustar el pool de conexiones SQLAlchemy (`pool_size=20, max_overflow=40`)
- Aumentar `worker_connections` en nginx a 8192

### ASR Escalabilidad — Por qué se cumple (100% de éxito)

El agente extractor garantiza el 100% de éxito gracias a:

1. **Cola de mensajes (Celery + Redis)**: ninguna petición se procesa de
   forma síncrona. Si el sistema está sobrecargado, la tarea espera en cola.

2. **Reintentos con backoff exponencial** (2s → 4s → 8s → 16s → 32s):
   ante fallos de conexión con el proveedor cloud, la tarea se reintenta
   automáticamente hasta 5 veces.

3. **`task_acks_late=True`**: el mensaje sólo se elimina de la cola cuando
   la tarea termina exitosamente. Si el worker cae, la tarea vuelve a la cola.

4. **Agnóstico al proveedor**: el patrón Strategy (`CloudProvider` abstracto)
   permite añadir nuevos proveedores (GCP, Oracle) sin modificar la lógica
   del agente.

Los proveedores simulan un 10% de fallo aleatorio para demostrar que,
aun con fallos, el sistema garantiza el éxito final mediante reintentos.
