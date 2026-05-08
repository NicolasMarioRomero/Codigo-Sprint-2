# ASR — Escalabilidad

## Definición del ASR

> **Yo como cliente empresarial, dado que se encuentra en un ambiente sobrecargado, cuando se realiza una solicitud de métricas cloud quiero que el agente extractor externo capture los datos de forma agnóstica. Se debe garantizar un 100% de éxito en las peticiones realizadas.**

---

## Argumentación estilos y tácticas de arquitectura

### Estilos de Arquitectura

| Estilo | Análisis |
|--------|----------|
| **Microservicios** | Favorece: escalabilidad y desempeño. El agente extractor es un servicio independiente que escala sin afectar al Report Service ni al resto del sistema. Desfavorece: latencia interna por comunicación entre servicios. |
| **Publicador / Suscriptor** | Favorece: escalabilidad y desempeño. Las solicitudes de extracción se publican en una cola (Redis) y son procesadas asincrónicamente por los workers de Celery, desacoplando completamente al solicitante del extractor. Esto permite absorber picos de carga sin bloquear el flujo principal. Desfavorece: complejidad en el rastreo de tareas y dificultad para pruebas síncronas. |
| **Pipes and Filters** | Favorece: mantenibilidad y extensibilidad. El flujo de extracción pasa por etapas bien definidas: solicitud → encolamiento → extracción → validación → respuesta. Cada etapa puede modificarse de forma independiente. Desfavorece: latencia adicional al pasar datos entre etapas. |

### Justificación

El sistema BITE adopta **Publicador / Suscriptor** como estilo principal para este ASR. El flujo es el siguiente: el cliente empresarial realiza una solicitud de métricas al Extractor Service (API REST), que la publica inmediatamente en la cola de Redis. Los workers de Celery suscritos a esa cola procesan la tarea de forma asíncrona, invocando al proveedor cloud correspondiente (AWS, GCP, etc.) a través de la interfaz agnóstica `CloudProvider`. Si el proveedor falla, el worker reintenta automáticamente con backoff exponencial hasta 5 veces, garantizando el 100% de éxito. El estilo de **Microservicios** permite que el Extractor Service escale horizontalmente añadiendo más workers ante ambientes sobrecargados, sin afectar a los demás servicios del sistema.

---

### Tácticas de Arquitectura

| Táctica | Descripción | Contribución al ASR |
|---------|-------------|---------------------|
| **Cola de mensajes** | Las solicitudes de extracción se encolan en Redis mediante Celery. El worker las procesa de forma asíncrona, independientemente del estado del proveedor cloud. | Desacopla al cliente del extractor: aunque el sistema esté sobrecargado, ninguna solicitud se pierde. La cola actúa como buffer. |
| **Reintentos con backoff exponencial** | Ante fallos de conexión con el proveedor cloud, el worker reintenta automáticamente hasta 5 veces con esperas de 2s, 4s, 8s, 16s y 32s (con jitter). | Garantiza el 100% de éxito ante fallos transitorios en ambientes sobrecargados, sin saturar al proveedor con reintentos inmediatos. |
| **Múltiples copias de procesamiento (workers)** | Se despliegan múltiples workers de Celery que consumen la misma cola de tareas en paralelo. | Permite procesar varias solicitudes de métricas simultáneamente, cumpliendo el requisito de escalabilidad ante alta carga. |
| **Patrón Strategy (agnóstico al proveedor)** | La interfaz abstracta `CloudProvider` define el contrato común. Cada proveedor (AWS, GCP) implementa `fetch_metrics()` de forma independiente. | El agente extractor captura datos de forma agnóstica: no requiere cambios en su lógica al agregar nuevos proveedores cloud. |

---

## Argumentación de tecnologías a utilizar

| Tecnología | Selección y Justificación |
|------------|--------------------------|
| **Celery** | Framework de cola de tareas distribuidas para Python. Permite encolar solicitudes de extracción, procesarlas de forma asíncrona y configurar reintentos automáticos con backoff exponencial. Es la pieza central que garantiza el 100% de éxito ante fallos. |
| **Redis (como broker de Celery)** | Actúa como broker de mensajes entre el Extractor API y los workers de Celery. Redis garantiza que las tareas persisten en cola aunque el worker esté temporalmente caído. En AWS se reemplaza por Amazon ElastiCache. |
| **FastAPI** | Framework web usado para exponer la API REST del agente extractor (`POST /api/v1/extractor/extract/sync`). Permite recibir solicitudes de extracción y procesarlas de forma inmediata. |
| **Patrón Strategy (Python ABC)** | La clase abstracta `CloudProvider` define el contrato agnóstico. Las clases concretas `AWSProvider` y `GCPProvider` implementan `fetch_metrics()`. Añadir un nuevo proveedor (ej. Oracle Cloud) requiere solo una nueva clase, sin tocar la lógica del agente. |
| **Amazon EC2** | Instancias donde se despliegan el Extractor API y los workers de Celery. La adición de workers ante sobrecarga se hace lanzando nuevas instancias EC2 sin modificar el código. |
| **Amazon ElastiCache (Redis)** | Broker de mensajes administrado en AWS. Reemplaza al Redis local en producción, ofreciendo mayor disponibilidad y throughput para la cola de tareas. |
| **JMeter** | Herramienta de pruebas de carga utilizada para simular 100 usuarios concurrentes enviando solicitudes de extracción a AWS y GCP simultáneamente, y verificar el 100% de éxito. |

---

## Diseño del experimento

| Campo | Descripción |
|-------|-------------|
| **Título** | Prueba de escalabilidad del agente extractor bajo ambiente sobrecargado |
| **Propósito** | Comprobar si con el uso de una cola de mensajes (Celery + Redis), reintentos con backoff exponencial y el patrón Strategy, el agente extractor garantiza un 100% de éxito en la captura de métricas cloud de forma agnóstica, incluso cuando el ambiente está sobrecargado y los proveedores presentan fallos. |
| **ASR involucrado** | Yo como cliente empresarial, dado que se encuentra en un ambiente sobrecargado, cuando se realiza una solicitud de métricas cloud quiero que el agente extractor externo capture los datos de forma agnóstica. Se debe garantizar un 100% de éxito en las peticiones realizadas. |
| **Infraestructura requerida** | - Una instancia EC2 con el Extractor API (FastAPI) desplegado<br>- Una instancia EC2 con el worker de Celery<br>- Redis (ElastiCache o local) como broker de mensajes<br>- Computador personal con JMeter para ejecutar las pruebas de carga |

### Estilos de Arquitectura asociados

| Estilo | Análisis |
|--------|----------|
| **Publicador / Suscriptor** | Favorece: desempeño y escalabilidad. Las solicitudes se publican en la cola sin esperar al extractor, y los workers procesan asíncronamente. Desfavorece: complejidad en el seguimiento de resultados. |
| **Microservicios** | Favorece: escalabilidad. El Extractor Service escala de forma independiente añadiendo workers. Desfavorece: latencia por comunicación entre servicios. |

### Tácticas aplicadas

| Táctica | Descripción |
|---------|-------------|
| **Cola de mensajes** | Celery + Redis encola las solicitudes de extracción. Ninguna petición se pierde aunque el sistema esté saturado. |
| **Reintentos con backoff exponencial** | Ante fallos del proveedor cloud, el worker reintenta hasta 5 veces con esperas crecientes (2s, 4s, 8s, 16s, 32s) y jitter aleatorio. |
| **Múltiples workers** | Varios workers consumen la cola en paralelo para procesar solicitudes concurrentes. |
| **Patrón Strategy** | Interfaz `CloudProvider` agnóstica que permite cambiar de proveedor sin modificar la lógica del agente. |

### Configuración de la prueba

- **Herramienta:** JMeter
- **Grupo 1 — Extracción AWS:** 50 usuarios concurrentes durante 3 minutos
- **Grupo 2 — Extracción GCP:** 50 usuarios concurrentes durante 3 minutos (simultáneo)
- **Total usuarios concurrentes:** 100 (50 AWS + 50 GCP)
- **Fallo simulado:** los proveedores fallan aleatoriamente con 10% de probabilidad
- **Endpoint:** `POST /api/v1/extractor/extract/sync`
- **Verificación por request:** HTTP 200 + body contiene `"success"`

### Métricas a capturar

- Tasa de éxito (%) — debe ser 100%
- Tasa de errores (%) — debe ser 0%
- Tiempo de respuesta promedio por proveedor (AWS vs GCP)
- Número total de requests procesados

### Resultados esperados

| Métrica | Valor esperado |
|---------|---------------|
| Tasa de éxito | 100% |
| Tasa de errores | 0% |
| Tiempo de respuesta promedio | Entre 1s y 10s (incluye reintentos) |
| Agnósticismo | Éxito tanto en AWS como en GCP |

### Análisis esperado

Con la cola de mensajes actuando como buffer ante sobrecarga, y el mecanismo de reintentos absorbiendo los fallos aleatorios del proveedor (10% de probabilidad), se espera que todas las solicitudes terminen exitosamente. Los workers de Celery procesan las tareas en paralelo desde la cola, evitando que la saturación del sistema impida la captura de métricas. El backoff exponencial protege a los proveedores cloud de una avalancha de reintentos simultáneos ante una falla masiva.

---

## Resultados obtenidos

> **Nota sobre el experimento:** el primer experimento (Sprint 2 intermedio) utilizó
> el endpoint `/extract/sync` **sin reintentos**, lo que expuso directamente el 10% de
> fallo aleatorio de los proveedores. Tras corregir el endpoint para incluir reintentos
> con backoff exponencial (ver `extractor_routes.py`), se re-ejecutó el experimento
> con el mismo plan JMeter. Los resultados a continuación corresponden a la versión
> corregida del código.

### Experimento corregido — con reintentos en `/extract/sync`

| Label | # Samples | Promedio | Mediana | P90 | P95 | P99 | Error % |
|-------|-----------|----------|---------|-----|-----|-----|---------|
| POST Extraer métricas AWS | 8.558 | 130 ms | 4 ms | 4 ms | 1.008 ms | 3.012 ms | 0,00% |
| POST Extraer métricas GCP | 8.543 | 128 ms | 4 ms | 4 ms | 1.011 ms | 3.008 ms | 0,00% |
| **TOTAL** | **17.101** | **129 ms** | **4 ms** | **4 ms** | **1.009 ms** | **3.010 ms** | **0,00%** |

**Distribución de reintentos (sobre 10.000 requests simulados):**

| Intentos necesarios | Requests | Porcentaje |
|--------------------|----------|------------|
| 1 (sin reintento) | ~9.016 | 90,16% |
| 2 (1 reintento) | ~877 | 8,77% |
| 3 (2 reintentos) | ~94 | 0,94% |
| 4 (3 reintentos) | ~13 | 0,13% |
| 5 (4 reintentos) | ~0 | 0,00% |
| Fallidos (5 reintentos agotados) | 0 | 0,00% |

---

## Análisis de resultados

### ¿Se cumplió el ASR?

**Sí.** Con el endpoint `/extract/sync` corregido para incluir reintentos con backoff
exponencial, la tasa de errores fue de **0,00%** en 17.101 requests, cumpliendo el
requisito de 100% de éxito en las peticiones realizadas.

Los dos aspectos del ASR fueron satisfechos:

1. **100% de éxito:** la probabilidad de fallar tras 5 reintentos con una tasa de
   fallo del 10% por proveedor es de `0.1^5 = 0.00001%`, lo que en la práctica
   garantiza cero errores. La simulación (N=10.000) confirmó 0 fallos.

2. **Agnósticismo:** AWS y GCP produjeron resultados prácticamente idénticos
   (4 ms de mediana, 0% de errores), confirmando que el patrón Strategy funciona
   correctamente y el agente extractor es completamente agnóstico al proveedor cloud.

### Impacto en latencia de los reintentos

El 90% de los requests se resuelve en 4 ms (sin reintento). El 10% que falla en el
primer intento agrega ~1.000 ms de backoff, y el 1% restante puede tardar hasta
~3.000 ms. El P95 de 1.009 ms y P99 de 3.010 ms son aceptables dado que el ASR
no establece restricciones de tiempo, solo de éxito.

### Diferencia respecto al primer experimento

En el primer experimento (Sprint 2 intermedio), el endpoint `/extract/sync` no tenía
lógica de reintentos: ante un fallo del proveedor, el error se propagaba directamente
al cliente. Esto producía una tasa de error del 10,25%, equivalente a la tasa de
fallo aleatoria de los proveedores. La corrección consistió en agregar un bucle de
hasta 5 reintentos con backoff exponencial (`2^n + jitter`) directamente en el
endpoint síncrono, lo que garantiza el cumplimiento del ASR sin necesidad de usar
el flujo asíncrono de Celery.
