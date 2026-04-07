# ASR — Latencia

## Definición del ASR

> **Como responsable de una empresa cliente, cuando ingreso a la plataforma, durante una carga de usuarios normal es decir alrededor de 5000 usuarios, quiero que el sistema me deje visualizar el dashboard de reportes, esto debe suceder en un tiempo máximo de 3 segundos desde la ocurrencia del evento.**

---

## Argumentación estilos y tácticas de arquitectura

### Estilos de Arquitectura

| Estilo | Análisis |
|--------|----------|
| **Microservicios** | Favorece: escalabilidad y desempeño. Cada servicio (Security, Report, Analysis, Platform) escala de forma independiente sin afectar los demás. Desfavorece: latencia interna por comunicación entre servicios. |
| **Publicador / Suscriptor** | Favorece: desempeño y escalabilidad. Las notificaciones del sistema se envían asincrónicamente a través del Notification Service sin bloquear el flujo principal. Desfavorece: facilidad de pruebas. |
| **Capas** | Favorece: mantenibilidad y organización del código. Desfavorece: latencia al agregar saltos adicionales en el procesamiento de cada petición. |

### Justificación

El sistema BITE adopta Microservicios como estilo principal. El flujo del ASR pasa por el API Gateway, que enruta la petición al Security Service para validar la autenticación, y luego al Report Service, que construye el dashboard consultando la caché en memoria y la Report DB. El Analysis Service procesa datos en segundo plano, de forma que el Report Service encuentra los resultados listos sin esperar cálculos en tiempo real. Esto, combinado con el balanceador de carga y dos instancias del servidor de reportes, permite cumplir el límite de 3 segundos bajo 5000 usuarios concurrentes.

---

### Tácticas de Arquitectura

| Táctica | Descripción | Contribución al ASR |
|---------|-------------|---------------------|
| **Múltiples copias de procesamiento** | Se despliegan dos instancias del servidor de reportes detrás del balanceador de carga. | Permite procesar solicitudes en paralelo y manejar mejor la carga concurrente de 5000 usuarios. |
| **Balanceo de carga** | El balanceador distribuye las peticiones entrantes entre las dos instancias del servidor de reportes. | Evita que un único servidor se sature y mantiene la latencia dentro del límite de 3 segundos. |
| **Caché en memoria** | Se almacenan temporalmente los resultados frecuentes del dashboard entre el servidor de reportes y la base de datos. | Reduce las consultas directas a la Report DB, disminuyendo el tiempo de respuesta del sistema. |

---

## Argumentación de tecnologías a utilizar

| Tecnología | Selección y Justificación |
|------------|--------------------------|
| **Amazon EC2** | Instancias de servidor donde se despliegan los servicios del sistema (Security, Report, Analysis, Platform). Permiten escalar horizontalmente agregando más instancias ante aumento de carga. |
| **Application Load Balancer (ALB)** | Distribuye el tráfico entre las dos instancias del servidor de reportes. Implementa la táctica de balanceo de carga e impide que un único servidor se sature bajo los 5000 usuarios concurrentes. |
| **Django** | Framework web usado como entorno de ejecución en cada servidor. Permite desarrollar y exponer los servicios de forma rápida y estructurada. |
| **Caché en memoria (Redis)** | Almacena temporalmente los resultados frecuentes del dashboard entre el servidor de reportes y la base de datos. Reduce consultas directas a la Report DB y disminuye el tiempo de respuesta. |
| **Amazon RDS (PostgreSQL)** | Base de datos relacional para cada servicio (Security DB, Report DB, Analysis DB, Platform DB). Almacena los datos de consumo, reportes y seguridad del sistema. |
| **JMeter** | Herramienta de pruebas de carga utilizada para simular 5000 usuarios concurrentes accediendo al dashboard y medir la latencia de respuesta. |

---

## Diseño del experimento

| Campo | Descripción |
|-------|-------------|
| **Título** | Prueba de latencia del dashboard bajo carga normal |
| **Propósito** | Comprobar si con el uso de un balanceador de carga, dos instancias del servidor de reportes y una caché en memoria, el sistema es capaz de mostrar el dashboard de reportes en menos de 3 segundos bajo una carga de 5000 usuarios concurrentes. |
| **ASR involucrado** | Como responsable de una empresa cliente, cuando ingreso a la plataforma durante una carga normal de ~5000 usuarios, quiero visualizar el dashboard de reportes en máximo 3 segundos desde la ocurrencia del evento. |
| **Infraestructura requerida** | - Dos instancias EC2 con el servidor de reportes desplegado (simuladas con Docker)<br>- Nginx como Application Load Balancer<br>- Redis como caché en memoria<br>- PostgreSQL (Amazon RDS)<br>- Computador personal con JMeter para ejecutar las pruebas de carga |

### Estilos de Arquitectura asociados

| Estilo | Análisis |
|--------|----------|
| **Microservicios** | Favorece: escalabilidad y desempeño. El servidor de reportes escala de forma independiente sin afectar los demás servicios. Desfavorece: latencia interna por comunicación entre servicios. |
| **Capas** | Favorece: mantenibilidad. Desfavorece: latencia por saltos adicionales. |

### Tácticas aplicadas

| Táctica | Descripción |
|---------|-------------|
| **Balanceo de carga** | Nginx distribuye las peticiones entre las dos instancias del servidor de reportes con algoritmo `least_conn`. |
| **Múltiples copias de procesamiento** | Dos instancias del servidor de reportes atienden las peticiones concurrentes en paralelo. |
| **Caché en memoria** | Redis almacena temporalmente los resultados frecuentes del dashboard (TTL 30s), reduciendo consultas directas a PostgreSQL. |

### Configuración de la prueba

- **Herramienta:** JMeter 5.6.3
- **Usuarios virtuales:** 5000 concurrentes
- **Rampa de subida:** 0 → 5000 usuarios en 120 segundos
- **Carga sostenida:** 600 segundos (10 minutos) a 5000 usuarios
- **Secuencia por usuario:** GET Dashboard → GET Reporte detallado → GET Health
- **Timeout de respuesta configurado:** 3000 ms

### Métricas a capturar

- Tiempo de respuesta promedio
- Percentil 95 (P95) de latencia
- Tasa de errores (%)

### Resultados esperados

| Métrica | Valor esperado |
|---------|---------------|
| Tiempo de respuesta promedio | Entre 500 ms y 1.5 s |
| Percentil 95 (P95) | Menor a 3000 ms |
| Tasa de errores | 0% |

---

## Resultados obtenidos

| Label | # Samples | Promedio | Mediana | P90 | P95 | P99 | Error % |
|-------|-----------|----------|---------|-----|-----|-----|---------|
| GET Dashboard | 206.658 | 1877 ms | 1288 ms | 4546 ms | 5248 ms | 6657 ms | 99.05% |
| GET Reporte detallado | 205.128 | 1886 ms | 1281 ms | 4580 ms | 5260 ms | 6689 ms | 99.02% |
| GET Health | 203.368 | 1869 ms | 1291 ms | 4531 ms | 5209 ms | 6611 ms | 98.94% |
| **TOTAL** | **615.154** | **1877 ms** | **1287 ms** | **4551 ms** | **5241 ms** | **6653 ms** | **99.00%** |

---

## Análisis de resultados

### ¿Se cumplió el ASR?

**No.** El P95 del endpoint del dashboard fue de **5248 ms**, superando el umbral de 3000 ms requerido. La tasa de errores fue de **99.05%**, muy por encima del 0% esperado.

Es importante aclarar que el alto porcentaje de errores no significa que el sistema esté caído ni que los requests fallen a nivel HTTP. El sistema respondió correctamente en todos los casos con HTTP 200. Los "errores" registrados por JMeter provienen de la `DurationAssertion` configurada en el plan de prueba, que marca como fallido todo request cuya respuesta supere los 3000 ms. Dado que el P95 fue de 5248 ms, la gran mayoría de requests superó ese umbral, lo que explica el 99% de errores reportado.

### ¿Por qué no se cumple?

El experimento se ejecutó en un entorno local usando Docker Compose en un único computador, lo cual difiere significativamente de la infraestructura de producción diseñada en AWS. Las razones concretas son:

1. **Recursos compartidos en el mismo host:** las dos instancias del Report Service, Redis, PostgreSQL y Nginx comparten la CPU y la RAM del mismo equipo físico. En AWS, cada EC2 tendría recursos dedicados y aislados.

2. **Red local vs red de datacenter:** la latencia entre contenedores Docker en un mismo equipo es mayor a la latencia entre instancias EC2 dentro de la misma VPC de AWS, que suele ser inferior a 1 ms.

3. **PostgreSQL sin optimización:** el contenedor de PostgreSQL compite por CPU con el resto de servicios. Amazon RDS con read replicas y conexiones optimizadas reduciría significativamente los tiempos de consulta.

4. **Redis local sin cluster:** Amazon ElastiCache ofrece mayor throughput y menor latencia que un Redis en contenedor compartido bajo alta concurrencia.

5. **Saturación del host:** con 5000 usuarios concurrentes generando más de 1000 requests por segundo, el sistema operativo del equipo personal llega a sus límites de capacidad de red y procesamiento.

### ¿Qué cambios arquitecturales permitirían cumplir el ASR?

Para cumplir el límite de 3 segundos bajo 5000 usuarios concurrentes en producción se requiere:

1. **Desplegar en instancias EC2 dedicadas** (mínimo t3.medium por instancia del Report Service) con recursos aislados.
2. **Usar Amazon RDS** con al menos una read replica para distribuir la carga de lectura del dashboard.
3. **Usar Amazon ElastiCache** en modo cluster para mayor throughput en la caché.
4. **Aumentar el pool de conexiones** de SQLAlchemy (`pool_size=20, max_overflow=40`) para manejar la concurrencia sin colas de espera.
5. **Aumentar `worker_connections`** de Nginx a 8192 para soportar más conexiones simultáneas.
6. **Agregar una tercera instancia EC2** del Report Service si el P95 sigue superando los 3 segundos con las optimizaciones anteriores.
