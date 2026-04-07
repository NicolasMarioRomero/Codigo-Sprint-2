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
│   │       └── extractor_routes.py    # POST /api/v1/extractor/extract/sync
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── nginx/
│   └── nginx.conf                # Load balancer (least_conn entre 2 instancias)
├── docs/
│   └── ASR-Escalabilidad.md      # Documentación wiki del ASR de Escalabilidad
├── docker-compose.yml            # Orquestación completa
├── seed_data.py                  # Script de seed (referencia)
├── jmeter_latencia.jmx           # Plan JMeter — ASR Latencia (puerto 80)
└── jmeter_escalabilidad.jmx      # Plan JMeter — ASR Escalabilidad (puerto 8001)
```

---

## Cómo ejecutar el experimento

### Paso 1 — Levantar la infraestructura
```bash
docker-compose up --build -d
```

### Paso 2 — Poblar la base de datos (solo una vez)
```bash
docker exec -it codigo-sprint-2-db-1 psql -U postgres -d cloudcosts -c "
INSERT INTO reports (company_id, project_id, service_name, cost, usage)
SELECT
    (random()*9+1)::int,
    (random()*4+1)::int,
    (ARRAY['EC2','S3','Lambda','RDS','CloudFront','EKS'])[floor(random()*6+1)::int],
    round((random()*800+5)::numeric, 2),
    round((random()*5000+1)::numeric, 2)
FROM generate_series(1, 60000);"
```

### Paso 3 — ASR Latencia con JMeter
1. Abrir JMeter → **File → Open** → seleccionar `jmeter_latencia.jmx`
2. Ajustar usuarios si la máquina no aguanta: clic en "5000 Usuarios Concurrentes" → bajar `Number of Threads` a 500
3. Dar play ▶
4. Ver resultados en **Aggregate Report** (P95, promedio, errores)
5. Resultados guardados en `resultados_latencia.csv`

### Paso 4 — ASR Escalabilidad con JMeter
1. Abrir JMeter → **File → Open** → seleccionar `jmeter_escalabilidad.jmx`
2. Dar play ▶ (corre 100 usuarios: 50 AWS + 50 Azure simultáneos durante 3 min)
3. Ver resultados en **Aggregate Report** (tasa de éxito, errores por proveedor)
4. Resultados guardados en `resultados_escalabilidad.csv`

---

## Criterios de éxito

| ASR | Métrica | Umbral |
|-----|---------|--------|
| Latencia | P95 dashboard | < 3000 ms |
| Latencia | Tasa de errores | 0% |
| Escalabilidad | Tasa de errores | 0% |
| Escalabilidad | Agnóstico | AWS ✅ GCP ✅ |
