# BITE — Sprint 2: Experimentos de Arquitectura

Curso: Arquitectura y Diseño de Software — Universidad de los Andes

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
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   └── index.html                # Dashboard UI (HTML+JS puro)
├── nginx/
│   └── nginx.conf                # Load balancer EC2 (127.0.0.1)
├── terraform/
│   ├── main.tf                   # EC2 + Security Group
│   ├── variables.tf              # Variables: region, instance_type, key_name
│   ├── outputs.tf                # IPs, URLs, comandos SSH
│   └── user_data.sh              # Bootstrap: instala dependencias al iniciar la instancia
├── install_terraform.sh
├── deploy.sh
├── seed_data.py
├── jmeter_latencia.jmx
└── jmeter_escalabilidad.jmx
```

---

## Despliegue en AWS

### Paso 1 — Clonar el repositorio en AWS CloudShell

```bash
git clone <URL-del-repo>
cd Codigo-Sprint-2
```

### Paso 2 — Instalar Terraform

```bash
sh ./install_terraform.sh
```

### Paso 3 — Despliegue completo

```bash
chmod +x deploy.sh
./deploy.sh ~/.ssh/labsuser.pem
```

Este script hace automáticamente:
1. `terraform init + apply` → crea la instancia EC2 en AWS
2. Espera que SSH esté disponible en la instancia
3. `rsync` → copia el código al servidor
4. Instala dependencias y levanta todos los servicios directamente en la instancia
5. Espera que PostgreSQL esté listo
6. `python3 seed_data.py` → carga ~60.000 registros de prueba
7. Verifica health checks

### Paso 4 — Ejecutar experimentos con JMeter

**ASR Latencia** (`jmeter_latencia.jmx`): cambiar `HOST` a la IP pública, `PORT = 80`. 5000 threads, ramp-up 120 s, duración 600 s.

**ASR Escalabilidad** (`jmeter_escalabilidad.jmx`): cambiar `HOST` a la IP pública, `PORT = 8001`. 50 threads AWS + 50 threads GCP simultáneos.

### Paso 5 — Destruir infraestructura

```bash
cd terraform && terraform destroy
```

---

# ASR Latencia

## 1. ASR

> Como responsable de una empresa cliente, cuando ingreso a la plataforma, durante una carga de usuarios normal es decir alrededor de 5000 usuarios, quiero que el sistema me deje visualizar el dashboard de reportes, esto debe suceder en un tiempo máximo de 3 segundos desde la ocurrencia del evento.

---

## 2. Argumentación de estilos y tácticas de arquitectura

### Estilos de arquitectura

| Estilo | Análisis |
|--------|----------|
| **Microservicios** | **Favorece:** escalabilidad y desempeño. El Report Service escala de forma independiente sin afectar los demás servicios (Security, Analysis, Platform). **Desfavorece:** latencia interna por comunicación entre servicios. |
| **Publicador / Suscriptor** | **Favorece:** desempeño y escalabilidad. Las notificaciones del sistema se envían asincrónicamente a través del Notification Service sin bloquear el flujo principal. **Desfavorece:** facilidad de pruebas. |
| **Capas** | **Favorece:** mantenibilidad y organización del código. **Desfavorece:** latencia al agregar saltos adicionales en el procesamiento de cada petición. |

**Justificación:** El sistema BITE adopta **Microservicios** como estilo principal para este ASR. El flujo pasa por el API Gateway → Security Service (autenticación) → Report Service (construye el dashboard consultando caché + Report DB). El Analysis Service procesa datos en segundo plano, de forma que el Report Service encuentra resultados listos sin esperar cálculos en tiempo real. Esto, combinado con el balanceador de carga y dos instancias del servidor de reportes, permite cumplir el límite de 3 segundos bajo 5000 usuarios concurrentes.

### Tácticas de arquitectura

| Táctica | Descripción | Contribución al ASR |
|---------|-------------|---------------------|
| **Múltiples copias de procesamiento** | Se despliegan dos instancias del servidor de reportes detrás del balanceador de carga. | Permite procesar solicitudes en paralelo y manejar la carga concurrente de 5000 usuarios sin que un único nodo se sature. |
| **Balanceo de carga** | Nginx distribuye las peticiones entrantes entre las dos instancias con algoritmo `least_conn`. | Evita que un único servidor se sature y mantiene la latencia dentro del límite de 3 segundos. |
| **Caché en memoria** | Los resultados frecuentes del dashboard se almacenan en Redis con TTL de 30 s. | Reduce las consultas directas a la Report DB, disminuyendo significativamente el tiempo de respuesta. |

---

## 3. Argumentación de tecnologías a utilizar

| Tecnología | Justificación |
|------------|---------------|
| **Amazon EC2** | Instancias de servidor donde se despliegan los servicios. Permiten escalar horizontalmente añadiendo más instancias ante aumento de carga. |
| **Nginx (Application Load Balancer)** | Distribuye el tráfico entre las dos instancias del servidor de reportes con `least_conn`, implementando la táctica de balanceo de carga directamente. |
| **FastAPI + Uvicorn** | Framework web asíncrono con soporte nativo para alta concurrencia. Permite exponer el endpoint del dashboard con múltiples workers sin bloqueos. |
| **Redis** | Almacén en memoria que implementa la táctica de caché. Reduce drásticamente las consultas a PostgreSQL para solicitudes repetidas del dashboard (TTL 30 s). |
| **PostgreSQL (Amazon RDS)** | Base de datos relacional con pool de conexiones optimizado (`pool_size=20`, `max_overflow=40`). Almacena los datos de consumo y reportes. |
| **JMeter** | Herramienta de pruebas de carga que simula los 5000 usuarios concurrentes y mide la latencia de respuesta del dashboard. |

---

## 4. Diseño del experimento

| Campo | Descripción |
|-------|-------------|
| **Título** | Prueba de latencia del dashboard bajo carga normal |
| **Propósito** | Comprobar si con el uso de un balanceador de carga (Nginx), dos instancias del servidor de reportes y una caché en memoria (Redis), el sistema es capaz de mostrar el dashboard en menos de 3 segundos bajo una carga de 5000 usuarios concurrentes. |
| **Infraestructura** | Dos instancias EC2 con el servidor de reportes · Nginx como balanceador · Redis como caché · PostgreSQL (RDS) · JMeter en equipo local |

**Configuración de la prueba (JMeter):**

- Usuarios virtuales: 5000 concurrentes
- Rampa de subida: 0 → 5000 usuarios en 2 minutos
- Carga sostenida: 10 minutos
- Secuencia por usuario: autenticación → solicitud del dashboard → verificación de respuesta
- Timeout configurado: 3000 ms (DurationAssertion)

**Métricas a capturar:**

- Tiempo de respuesta promedio
- Percentil 95 (P95) de latencia
- Tasa de errores (%)

---

## 5. Resultados esperados

| Métrica | Valor esperado | Relación con el ASR |
|---------|---------------|---------------------|
| **Tiempo de respuesta promedio** | Entre 500 ms y 1500 ms | El ASR exige máximo 3000 ms; un promedio en este rango garantiza que la mayoría de usuarios esté bien por debajo del límite. |
| **Percentil 95 (P95)** | < 3000 ms | El P95 garantiza que el 95% de los 5000 usuarios concurrentes recibe el dashboard dentro del límite exigido por el ASR. |
| **Tasa de errores** | 0% | El ASR no admite fallos: el responsable de la empresa debe poder visualizar el dashboard siempre, sin errores HTTP. |

---

# ASR Escalabilidad

## 1. ASR

> Yo como cliente empresarial, dado que se encuentra en un ambiente sobrecargado, cuando se realiza una solicitud de métricas cloud quiero que el agente extractor externo capture los datos de forma agnóstica. Se debe garantizar un 100% de éxito en las peticiones realizadas.

---

## 2. Argumentación de estilos y tácticas de arquitectura

### Estilos de arquitectura

| Estilo | Análisis |
|--------|----------|
| **Microservicios** | **Favorece:** escalabilidad y desempeño. El agente extractor es un servicio independiente que escala añadiendo workers sin afectar al Report Service ni al resto del sistema. **Desfavorece:** latencia interna por comunicación entre servicios. |
| **Publicador / Suscriptor** | **Favorece:** escalabilidad y desempeño. Las solicitudes se publican en una cola (Redis) y son procesadas asincrónicamente por los workers de Celery, desacoplando al solicitante del extractor y absorbiendo picos de carga sin bloqueos. **Desfavorece:** complejidad en el rastreo de tareas y dificultad para pruebas síncronas. |
| **Pipes and Filters** | **Favorece:** mantenibilidad y extensibilidad. El flujo de extracción pasa por etapas bien definidas: solicitud → encolamiento → extracción → validación → respuesta. **Desfavorece:** latencia adicional al pasar datos entre etapas. |

**Justificación:** El sistema BITE adopta **Publicador / Suscriptor** como estilo principal para este ASR. El cliente realiza una solicitud de métricas al Extractor Service (API REST), que la publica en la cola de Redis. Los workers de Celery suscritos a esa cola procesan la tarea asincrónamente, invocando al proveedor cloud correspondiente a través de la interfaz agnóstica `CloudProvider`. Si el proveedor falla, el worker reintenta automáticamente con backoff exponencial hasta 5 veces, garantizando el 100% de éxito. El estilo de **Microservicios** permite escalar horizontalmente añadiendo más workers ante ambientes sobrecargados.

### Tácticas de arquitectura

| Táctica | Descripción | Contribución al ASR |
|---------|-------------|---------------------|
| **Cola de mensajes** | Las solicitudes de extracción se encolan en Redis mediante Celery. El worker las procesa de forma asíncrona, independientemente del estado del proveedor cloud. | Desacopla al cliente del extractor: aunque el sistema esté sobrecargado, ninguna solicitud se pierde. La cola actúa como buffer. |
| **Reintentos con backoff exponencial** | Ante fallos de conexión con el proveedor cloud, el worker reintenta automáticamente hasta 5 veces con esperas de 1 s, 2 s, 4 s, 8 s (más jitter). | Garantiza el 100% de éxito ante fallos transitorios. P(fallo tras 5 reintentos con 10% prob.) = 0.1⁵ ≈ 0.001%. |
| **Múltiples copias de procesamiento (workers)** | Se despliegan múltiples workers de Celery que consumen la misma cola de tareas en paralelo. | Permite procesar varias solicitudes de métricas simultáneamente, absorbiendo la alta carga del ambiente sobrecargado. |
| **Patrón Strategy (agnóstico al proveedor)** | La interfaz abstracta `CloudProvider` define el contrato común. Cada proveedor (AWS, GCP) implementa `fetch_metrics()` de forma independiente. | El agente extractor captura datos de forma agnóstica: no requiere cambios en su lógica al agregar nuevos proveedores cloud. |

---

## 3. Argumentación de tecnologías a utilizar

| Tecnología | Justificación |
|------------|---------------|
| **Celery** | Framework de cola de tareas distribuidas para Python. Permite encolar solicitudes de extracción, procesarlas de forma asíncrona y configurar reintentos automáticos con backoff exponencial. Es la pieza central que garantiza el 100% de éxito ante fallos. |
| **Redis (broker de Celery)** | Actúa como broker de mensajes entre el Extractor API y los workers de Celery. Garantiza que las tareas persisten en la cola aunque el worker esté temporalmente caído. |
| **FastAPI** | Framework web utilizado para exponer la API REST del agente extractor (`POST /api/v1/extractor/extract/sync`). Permite recibir solicitudes con alta concurrencia de forma nativa. |
| **Patrón Strategy (Python ABC)** | La clase abstracta `CloudProvider` define el contrato agnóstico. Las clases concretas `AWSProvider` y `GCPProvider` implementan `fetch_metrics()`. Añadir un nuevo proveedor (ej. Azure) requiere solo una nueva clase sin tocar la lógica del agente. |
| **Amazon EC2** | Instancias donde se despliegan el Extractor API y los workers de Celery. La adición de workers ante sobrecarga se hace lanzando nuevas instancias sin modificar el código. |
| **JMeter** | Herramienta de pruebas de carga utilizada para simular 100 usuarios concurrentes (50 AWS + 50 GCP) enviando solicitudes de extracción y verificar el 100% de éxito. |

---

## 4. Diseño del experimento

| Campo | Descripción |
|-------|-------------|
| **Título** | Prueba de escalabilidad del agente extractor bajo ambiente sobrecargado |
| **Propósito** | Comprobar si con el uso de reintentos con backoff exponencial y el Patrón Strategy, el agente extractor garantiza un 100% de éxito en la captura de métricas cloud de forma agnóstica, incluso cuando el ambiente está sobrecargado y los proveedores presentan fallos aleatorios. |
| **Infraestructura** | Una instancia EC2 con el Extractor API (FastAPI) · Una instancia EC2 con el worker de Celery · Redis como broker de mensajes · JMeter en equipo local |

**Configuración de la prueba (JMeter):**

- Grupo 1 — Extracción AWS: 50 usuarios concurrentes durante 3 minutos
- Grupo 2 — Extracción GCP: 50 usuarios concurrentes durante 3 minutos (simultáneo)
- Total usuarios concurrentes: 100 (50 AWS + 50 GCP)
- Fallo simulado: los proveedores fallan aleatoriamente con 10% de probabilidad
- Endpoint: `POST /api/v1/extractor/extract/sync`
- Verificación por request: HTTP 200 + body contiene `"success"`

**Métricas a capturar:**

- Tasa de éxito (%) — debe ser 100%
- Tasa de errores (%) — debe ser 0%
- Tiempo de respuesta promedio por proveedor (AWS vs GCP)
- Número total de requests procesados

---

## 5. Resultados esperados

| Métrica | Valor esperado | Relación con el ASR |
|---------|---------------|---------------------|
| **Tasa de éxito** | 100% | El ASR exige explícitamente un 100% de éxito en todas las peticiones realizadas. |
| **Tasa de errores** | 0% | Cualquier error HTTP representa un incumplimiento directo del ASR. |
| **Tiempo de respuesta promedio** | Entre 4 ms y 200 ms | El tiempo incluye posibles reintentos ocasionales; el rango refleja el comportamiento esperado del backoff exponencial en condiciones normales de fallo (10%). |
| **Agnósticismo (AWS vs GCP)** | Tasa de éxito idéntica en ambos proveedores | El ASR exige captura agnóstica: si el Patrón Strategy funciona correctamente, el resultado no debe variar entre proveedor AWS y GCP. |
