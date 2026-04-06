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

El sistema BITE adopta **Publicador / Suscriptor** como estilo principal para este ASR. El flujo es el siguiente: el cliente empresarial realiza una solicitud de métricas al Extractor Service (API REST), que la publica inmediatamente en la cola de Redis. Los workers de Celery suscritos a esa cola procesan la tarea de forma asíncrona, invocando al proveedor cloud correspondiente (AWS, Azure, etc.) a través de la interfaz agnóstica `CloudProvider`. Si el proveedor falla, el worker reintenta automáticamente con backoff exponencial hasta 5 veces, garantizando el 100% de éxito. El estilo de **Microservicios** permite que el Extractor Service escale horizontalmente añadiendo más workers ante ambientes sobrecargados, sin afectar a los demás servicios del sistema.

---

### Tácticas de Arquitectura

| Táctica | Descripción | Contribución al ASR |
|---------|-------------|---------------------|
| **Cola de mensajes** | Las solicitudes de extracción se encolan en Redis mediante Celery. El worker las procesa de forma asíncrona, independientemente del estado del proveedor cloud. | Desacopla al cliente del extractor: aunque el sistema esté sobrecargado, ninguna solicitud se pierde. La cola actúa como buffer. |
| **Reintentos con backoff exponencial** | Ante fallos de conexión con el proveedor cloud, el worker reintenta automáticamente hasta 5 veces con esperas de 2s, 4s, 8s, 16s y 32s (con jitter). | Garantiza el 100% de éxito ante fallos transitorios en ambientes sobrecargados, sin saturar al proveedor con reintentos inmediatos. |
| **Múltiples copias de procesamiento (workers)** | Se despliegan múltiples workers de Celery que consumen la misma cola de tareas en paralelo. | Permite procesar varias solicitudes de métricas simultáneamente, cumpliendo el requisito de escalabilidad ante alta carga. |
| **Patrón Strategy (agnóstico al proveedor)** | La interfaz abstracta `CloudProvider` define el contrato común. Cada proveedor (AWS, Azure) implementa `fetch_metrics()` de forma independiente. | El agente extractor captura datos de forma agnóstica: no requiere cambios en su lógica al agregar nuevos proveedores cloud. |

---

## Argumentación de tecnologías a utilizar

| Tecnología | Selección y Justificación |
|------------|--------------------------|
| **Celery** | Framework de cola de tareas distribuidas para Python. Permite encolar solicitudes de extracción, procesarlas de forma asíncrona y configurar reintentos automáticos con backoff exponencial. Es la pieza central que garantiza el 100% de éxito ante fallos. |
| **Redis (como broker de Celery)** | Actúa como broker de mensajes entre el Extractor API y los workers de Celery. Redis garantiza que las tareas persisten en cola aunque el worker esté temporalmente caído. En AWS se reemplaza por Amazon ElastiCache. |
| **FastAPI** | Framework web usado para exponer la API REST del agente extractor (`POST /api/v1/extractor/extract`). Permite recibir solicitudes de extracción y encolarlas de forma inmediata. |
| **Patrón Strategy (Python ABC)** | La clase abstracta `CloudProvider` define el contrato agnóstico. Las clases concretas `AWSProvider` y `AzureProvider` implementan `fetch_metrics()`. Añadir GCP requiere solo una nueva clase, sin tocar la lógica del agente. |
| **Amazon EC2** | Instancias donde se despliegan el Extractor API y los workers de Celery. La adición de workers ante sobrecarga se hace lanzando nuevas instancias EC2 sin modificar el código. |
| **Amazon ElastiCache (Redis)** | Broker de mensajes administrado en AWS. Reemplaza al Redis local en producción, ofreciendo mayor disponibilidad y throughput para la cola de tareas. |

---

## Diseño del experimento

| Campo | Descripción |
|-------|-------------|
| **Título** | Prueba de escalabilidad del agente extractor bajo ambiente sobrecargado |
| **Propósito** | Comprobar si con el uso de una cola de mensajes (Celery + Redis), reintentos con backoff exponencial y el patrón Strategy, el agente extractor garantiza un 100% de éxito en la captura de métricas cloud de forma agnóstica, incluso cuando el ambiente está sobrecargado y los proveedores presentan fallos. |
| **ASR involucrado** | Yo como cliente empresarial, dado que se encuentra en un ambiente sobrecargado, cuando se realiza una solicitud de métricas cloud quiero que el agente extractor externo capture los datos de forma agnóstica. Se debe garantizar un 100% de éxito en las peticiones realizadas. |
| **Infraestructura requerida** | - Una instancia EC2 con el Extractor API (FastAPI) desplegado<br>- Una instancia EC2 con el worker de Celery<br>- Redis (ElastiCache o local) como broker de mensajes<br>- Computador personal para ejecutar el script de prueba |

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

- **Herramienta:** Script Python (`test_escalabilidad.py`) con `concurrent.futures`
- **Solicitudes totales:** 200 solicitudes de extracción
- **Concurrencia:** 50 solicitudes simultáneas
- **Proveedores:** alternados entre `aws` y `azure` (prueba de agnósticismo)
- **Fallo simulado:** los proveedores fallan aleatoriamente con 10% de probabilidad
- **Secuencia por solicitud:** POST /extractor/extract → polling /extractor/status → verificar `"status": "success"`

### Métricas a capturar

- Tasa de éxito final (%) — debe ser 100%
- Número de reintentos realizados por tarea
- Tiempo total de procesamiento de las 200 solicitudes
- Distribución de éxito por proveedor (AWS vs Azure)
- Número de tareas que requirieron al menos 1 reintento

### Resultados esperados

| Métrica | Valor esperado |
|---------|---------------|
| Tasa de éxito | 100% |
| Tareas con reintentos | ~10% del total (≈20 tareas) |
| Tiempo promedio por tarea | Entre 2s y 10s (incluye reintentos) |
| Agnósticismo | Éxito tanto en `aws` como en `azure` |

### Análisis

Con la cola de mensajes actuando como buffer ante sobrecarga, y el mecanismo de reintentos absorbiendo los fallos aleatorios del proveedor (10% de probabilidad), se espera que todas las solicitudes terminen exitosamente. Los workers de Celery procesan las tareas en paralelo desde la cola, evitando que la saturación del sistema impida la captura de métricas. El backoff exponencial protege a los proveedores cloud de una avalancha de reintentos simultáneos ante una falla masiva.

### Conclusión esperada

El sistema cumple el ASR de escalabilidad gracias a la combinación de cola de mensajes (Celery + Redis), reintentos con backoff exponencial y el patrón Strategy. Si la tasa de éxito es inferior al 100% durante la prueba, se deberá revisar la configuración de `max_retries` en el worker o aumentar el número de workers para reducir el tiempo de espera en cola ante alta concurrencia.
