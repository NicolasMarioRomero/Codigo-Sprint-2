# BITE — Sprint 3: Experimentos de Arquitectura

**ASR Latencia**: Dashboard de reportes en < 3 segundos bajo 5000 usuarios concurrentes.  
**ASR Escalabilidad**: Extractor cloud agnóstico con 100% de éxito en ambientes sobrecargados.

---

## Estructura del proyecto

```
Codigo-Sprint-2/
├── Backend/                      # Report Service (ASR Latencia)
│   ├── App/
│   │   ├── Cache/redis_client.py      # Táctica: caché en memoria (Redis)
│   │   ├── db/database.py             # Pool de conexiones PostgreSQL
│   │   ├── Models/report.py           # Modelo ORM - tabla reports
│   │   ├── Routes/reports.py          # GET /api/v1/dashboard/{id}
│   │   └── Services/report_service.py # Lógica: cache → DB (agregación SQL)
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── Extractor/                    # Agente Extractor (ASR Escalabilidad)
│   ├── app/
│   │   ├── providers/
│   │   │   ├── base_provider.py       # Interfaz agnóstica (Strategy Pattern)
│   │   │   ├── aws_provider.py        # Implementación AWS
│   │   │   ├── gcp_provider.py        # Implementación GCP
│   │   │   └── __init__.py            # Registro de proveedores
│   │   ├── tasks/
│   │   │   └── extract_task.py        # Celery + reintentos + backoff exponencial
│   │   └── routes/
│   │       └── extractor_routes.py    # POST /api/v1/extractor/extract/sync
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   └── index.html                # Dashboard UI (HTML+JS puro)
├── nginx/
│   └── nginx.conf                # Load balancer least_conn (2 instancias backend)
├── terraform/
│   ├── main.tf                   # EC2 + Security Group (Ubuntu 24.04 via data source)
│   ├── variables.tf              # Variables: region, instance_type, key_name
│   ├── outputs.tf                # IPs, URLs, comandos SSH
│   └── user_data.sh              # Bootstrap: instala Docker al iniciar la instancia
├── docs/
│   ├── ASR-Latencia.md
│   └── ASR-Escalabilidad.md
├── install_terraform.sh          # Instala Terraform en AWS CloudShell (igual que Lab 7)
├── deploy.sh                     # Despliegue completo: Terraform + rsync + Docker Compose
├── docker-compose.yml            # Orquestación de todos los servicios
├── seed_data.py                  # Genera ~60.000 registros de prueba en PostgreSQL
├── jmeter_latencia.jmx           # Plan JMeter — ASR Latencia (HOST=IP, PORT=80)
└── jmeter_escalabilidad.jmx      # Plan JMeter — ASR Escalabilidad (HOST=IP, PORT=8001)
```

---

## Despliegue en AWS (igual que Laboratorio 7 - Circuit Breaker)

### Paso 1 — Clonar el repositorio en AWS CloudShell

```bash
git clone <URL-del-repo>
cd Codigo-Sprint-2
```

### Paso 2 — Instalar Terraform

```bash
sh ./install_terraform.sh
```

### Paso 3 — Despliegue completo con deploy.sh

```bash
chmod +x deploy.sh
./deploy.sh ~/.ssh/labsuser.pem
```

Este script hace automáticamente:
1. `terraform init + apply` → crea la instancia EC2 en AWS
2. Espera que SSH y Docker estén disponibles en la instancia
3. `rsync` → copia el código al servidor
4. `docker compose build && docker compose up -d` → levanta todos los servicios
5. Espera que PostgreSQL esté listo
6. `python3 seed_data.py` → carga ~60.000 registros de prueba
7. Verifica health checks

Al finalizar muestra:
```
══════════════════════════════════════════════════
  ✅ DESPLIEGUE COMPLETADO
══════════════════════════════════════════════════

  Frontend:         http://<IP>
  API Backend:      http://<IP>/api/v1/
  Extractor (docs): http://<IP>:8001/docs
  Health check:     http://<IP>/health

  ┌─ JMeter — Actualizar HOST en ambos archivos ────┐
  │  jmeter_latencia.jmx      → HOST = <IP>  PORT = 80
  │  jmeter_escalabilidad.jmx → HOST = <IP>  PORT = 8001
  └──────────────────────────────────────────────────┘
```

### Paso 4 — Ejecutar experimentos con JMeter

**ASR Latencia** (`jmeter_latencia.jmx`):
- Cambiar `HOST` a la IP pública, `PORT = 80`
- 5000 threads, ramp-up 120s, duración 600s
- Assertion: respuesta < 3000ms, HTTP 200

**ASR Escalabilidad** (`jmeter_escalabilidad.jmx`):
- Cambiar `HOST` a la IP pública, `PORT = 8001`
- 50 threads AWS + 50 threads GCP simultáneos
- Assertion: HTTP 200 en todos los requests

### Paso 5 — Destruir infraestructura

```bash
cd terraform
terraform destroy
```

---

## Desarrollo local (sin AWS)

```bash
docker compose up --build -d
python3 seed_data.py  # Cargar datos (PostgreSQL en localhost:5432)
# Abrir: http://localhost
```

---

## Arquitectura del experimento

```
Internet / JMeter
      │
      ▼
  Nginx :80          ← Load Balancer (least_conn)
  ├── /api/          → report_service_1:8000  ┐ 2 instancias
  ├── /health        → report_service_2:8000  ┘ (ASR Latencia)
  └── /extractor/    → extractor:8001

  Extractor :8001    ← Agente agnóstico (ASR Escalabilidad)
  └── POST /api/v1/extractor/extract/sync
       ├── AWSProvider.fetch_metrics()   \
       └── GCPProvider.fetch_metrics()    } Strategy Pattern
                                         /
  Redis              ← Cache + Broker Celery
  PostgreSQL         ← Base de datos
```

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
