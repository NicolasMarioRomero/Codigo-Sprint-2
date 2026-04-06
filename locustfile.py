"""
locustfile.py
Prueba de carga para el ASR de Latencia.

ASR: Como responsable de una empresa cliente, cuando ingreso a la plataforma
durante una carga normal de ~5000 usuarios, quiero visualizar el dashboard de
reportes en máximo 3 segundos desde la ocurrencia del evento.

Cómo ejecutar:
    pip install locust
    locust -f locustfile.py --host=http://localhost --headless \
           -u 5000 -r 100 --run-time 10m \
           --csv=resultados_latencia

Parámetros:
    -u 5000   → 5000 usuarios concurrentes
    -r 100    → rampa: 100 usuarios/segundo hasta llegar a 5000
    --run-time 10m → duración de la prueba sostenida

Criterio de éxito (ASR):
    - Percentil 95 (P95) < 3000 ms
    - Tasa de errores = 0%
"""
import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


COMPANY_IDS = list(range(1, 11))   # 10 empresas de prueba


class ReportUser(HttpUser):
    """
    Simula el comportamiento de un responsable de empresa:
    1. Verifica salud del servicio
    2. Solicita el dashboard de reportes (endpoint crítico del ASR)
    3. Opcionalmente solicita el detalle del reporte
    """
    wait_time = between(0.5, 2)    # Tiempo de espera entre acciones (simula usuario real)

    def on_start(self):
        """Selecciona una empresa aleatoria para este usuario."""
        self.company_id = random.choice(COMPANY_IDS)

    @task(5)
    def get_dashboard(self):
        """
        Tarea principal del ASR: cargar el dashboard de reportes.
        Peso 5: es la acción más frecuente.
        """
        with self.client.get(
            f"/api/v1/dashboard/{self.company_id}",
            name="/api/v1/dashboard/[company_id]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                elapsed_ms = response.elapsed.total_seconds() * 1000
                if elapsed_ms > 3000:
                    response.failure(
                        f"ASR VIOLADO: latencia {elapsed_ms:.0f}ms > 3000ms"
                    )
                else:
                    response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def get_report_detail(self):
        """
        Tarea secundaria: cargar el detalle de reportes.
        Peso 2: menos frecuente que el dashboard.
        """
        with self.client.get(
            f"/api/v1/report/{self.company_id}",
            name="/api/v1/report/[company_id]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check del servicio."""
        self.client.get("/health", name="/health")


# ── Hook para imprimir resumen del ASR al finalizar ────────

@events.quitting.add_listener
def print_asr_summary(environment, **kwargs):
    stats = environment.runner.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    error_rate = (stats.num_failures / stats.num_requests * 100) if stats.num_requests > 0 else 0

    print("\n" + "=" * 60)
    print("RESUMEN ASR — LATENCIA DASHBOARD")
    print("=" * 60)
    print(f"  Total peticiones  : {stats.num_requests}")
    print(f"  Errores           : {stats.num_failures} ({error_rate:.2f}%)")
    print(f"  Tiempo promedio   : {stats.avg_response_time:.0f} ms")
    print(f"  Percentil 95 (P95): {p95:.0f} ms")
    print(f"  Tiempo máximo     : {stats.max_response_time:.0f} ms")
    print("-" * 60)

    if p95 <= 3000 and error_rate == 0:
        print("  ✅ ASR CUMPLIDO: P95 <= 3s y tasa de errores = 0%")
    else:
        if p95 > 3000:
            print(f"  ❌ ASR VIOLADO: P95 ({p95:.0f}ms) supera los 3000ms")
        if error_rate > 0:
            print(f"  ❌ ASR VIOLADO: tasa de errores = {error_rate:.2f}%")
    print("=" * 60)
