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

| Label | # Samples | Promedio | Mediana | P90 | P95 | P99 | Error % |
|-------|-----------|----------|---------|-----|-----|-----|---------|
| POST Extraer métricas AWS | 8558 | 4 ms | 4 ms | 6 ms | 7 ms | 11 ms | 10.14% |
| POST Extraer métricas GCP | 8543 | 4 ms | 4 ms | 6 ms | 7 ms | 11 ms | 10.36% |
| **TOTAL** | **17.101** | **4 ms** | **4 ms** | **6 ms** | **7 ms** | **11 ms** | **10.25%** |

---

## Análisis de resultados

### ¿Se cumplió el ASR?

**No.** La tasa de errores fue de **10.25%**, muy por encima del 0% requerido para garantizar el 100% de éxito en las peticiones realizadas.

Sin embargo, hay dos aspectos positivos destacables que sí se cumplieron:

1. **Agnósticismo:** AWS y GCP produjeron resultados prácticamente idénticos (4 ms de promedio, P95 de 7 ms), lo que confirma que el patrón Strategy funciona correctamente y el agente extractor es completamente agnóstico al proveedor cloud.

2. **Latencia de extracción:** el tiempo de respuesta fue muy bajo (promedio 4 ms, P95 de 7 ms), lo que indica que el servicio procesa las solicitudes de forma eficiente bajo carga concurrente.

### ¿Por qué no se cumple?

El 10.25% de errores corresponde exactamente a la tasa de fallo aleatorio del 10% programada en los proveedores simulados (`if random.random() < 0.10: raise ConnectionError`). El ASR no se cumple porque el endpoint utilizado en el experimento (`/extract/sync`) ejecuta la extracción de forma **síncrona y sin reintentos**. Al fallar el proveedor en esa llamada directa, el error se propaga inmediatamente al cliente sin oportunidad de reintento.

El mecanismo de reintentos con backoff exponencial está implementado en las tareas de Celery, que son invocadas por el endpoint asíncrono `/extract`. Sin embargo, el plan de prueba de JMeter utilizó el endpoint `/extract/sync` para poder medir el resultado directamente, lo que dejó los reintentos fuera del flujo de prueba.

### ¿Qué cambios arquitecturales permitirían cumplir el ASR?

Para garantizar el 100% de éxito en producción se requiere:

1. **Usar el endpoint asíncrono `/extract` con polling de estado:** el cliente encola la tarea, Celery la reintenta automáticamente ante fallos, y el cliente consulta el estado final. Esto garantiza el 100% de éxito absorbiendo los fallos del proveedor con backoff exponencial.

2. **Aumentar `max_retries` en el worker** de 5 a 10 para cubrir escenarios de alta tasa de fallos en ambientes sobrecargados.

3. **Implementar Dead Letter Queue:** las tareas que agoten todos los reintentos pasan a una cola de reintentos diferida, garantizando que ninguna petición se pierda definitivamente.

4. **Desplegar múltiples workers de Celery** en instancias EC2 dedicadas para procesar la cola más rápido bajo alta concurrencia, reduciendo el tiempo de espera de las tareas en cola.
