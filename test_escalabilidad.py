"""
test_escalabilidad.py
Script de prueba para el ASR de Escalabilidad del agente extractor.

ASR: Yo como cliente empresarial, dado que se encuentra en un ambiente
sobrecargado, cuando se realiza una solicitud de métricas cloud quiero
que el agente extractor externo capture los datos de forma agnóstica.
Se debe garantizar un 100% de éxito en las peticiones realizadas.

Cómo ejecutar:
    pip install requests
    python test_escalabilidad.py

    # Para apuntar a otro host:
    EXTRACTOR_HOST=http://localhost:8001 python test_escalabilidad.py

Qué mide:
    - Tasa de éxito final (debe ser 100%)
    - Número de tareas que necesitaron reintentos
    - Tiempo total de procesamiento
    - Distribución de éxito por proveedor (AWS vs Azure)
"""

import os
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List

# ── Configuración ────────────────────────────────────────────
HOST          = os.getenv("EXTRACTOR_HOST", "http://localhost:8001")
TOTAL_TASKS   = 200        # Total de solicitudes a enviar
CONCURRENCY   = 50         # Solicitudes simultáneas
POLL_INTERVAL = 1.0        # Segundos entre polls de estado
POLL_TIMEOUT  = 120        # Máximo tiempo de espera por tarea (segundos)
PROVIDERS     = ["aws", "azure"]
COMPANY_IDS   = list(range(1, 11))
PROJECT_IDS   = list(range(1, 6))


@dataclass
class TaskResult:
    task_id: str
    provider: str
    company_id: int
    project_id: int
    status: str = "PENDING"
    retries: int = 0
    elapsed_s: float = 0.0
    metrics_count: int = 0
    error: str = ""


def submit_task(company_id: int, project_id: int, provider: str) -> dict:
    """Envía una solicitud de extracción al Extractor API."""
    resp = requests.post(
        f"{HOST}/api/v1/extractor/extract",
        json={"company_id": company_id, "project_id": project_id, "provider": provider},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def poll_task(task_id: str) -> dict:
    """Consulta el estado de una tarea hasta que termine o se agote el tiempo."""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        resp = requests.get(f"{HOST}/api/v1/extractor/status/{task_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("SUCCESS", "FAILURE"):
            return data
        time.sleep(POLL_INTERVAL)
    return {"status": "TIMEOUT", "task_id": task_id}


def run_single_task(params: dict) -> TaskResult:
    """Ejecuta una tarea completa: submit → poll → resultado."""
    company_id = params["company_id"]
    project_id = params["project_id"]
    provider   = params["provider"]

    result = TaskResult(
        task_id="",
        provider=provider,
        company_id=company_id,
        project_id=project_id,
    )

    start = time.time()
    try:
        # 1. Encolar la tarea
        submit_resp = submit_task(company_id, project_id, provider)
        result.task_id = submit_resp.get("task_id", "")

        # 2. Esperar resultado
        poll_resp = poll_task(result.task_id)
        result.status = poll_resp.get("status", "UNKNOWN")

        if result.status == "SUCCESS":
            task_result = poll_resp.get("result", {})
            result.metrics_count = task_result.get("metrics_count", 0)
        elif result.status == "FAILURE":
            result.error = str(poll_resp.get("error", ""))
        elif result.status == "TIMEOUT":
            result.error = "Tarea no terminó en el tiempo límite"

    except Exception as exc:
        result.status = "ERROR"
        result.error = str(exc)

    result.elapsed_s = round(time.time() - start, 2)
    return result


def build_tasks() -> List[dict]:
    """Genera los parámetros de cada solicitud alternando proveedores."""
    tasks = []
    for i in range(TOTAL_TASKS):
        tasks.append({
            "company_id": random.choice(COMPANY_IDS),
            "project_id": random.choice(PROJECT_IDS),
            "provider":   PROVIDERS[i % len(PROVIDERS)],  # Alterna AWS / Azure
        })
    return tasks


def print_results(results: List[TaskResult], total_elapsed: float):
    successful = [r for r in results if r.status == "SUCCESS"]
    failed     = [r for r in results if r.status != "SUCCESS"]

    success_rate = len(successful) / len(results) * 100

    by_provider = {}
    for r in results:
        by_provider.setdefault(r.provider, {"ok": 0, "fail": 0})
        if r.status == "SUCCESS":
            by_provider[r.provider]["ok"] += 1
        else:
            by_provider[r.provider]["fail"] += 1

    avg_time = sum(r.elapsed_s for r in results) / len(results)
    max_time = max(r.elapsed_s for r in results)

    print("\n" + "=" * 65)
    print("RESULTADOS — ASR ESCALABILIDAD")
    print("=" * 65)
    print(f"  Total solicitudes  : {len(results)}")
    print(f"  Exitosas           : {len(successful)}")
    print(f"  Fallidas           : {len(failed)}")
    print(f"  Tasa de éxito      : {success_rate:.1f}%")
    print(f"  Tiempo total       : {total_elapsed:.1f}s")
    print(f"  Tiempo promedio    : {avg_time:.2f}s por tarea")
    print(f"  Tiempo máximo      : {max_time:.2f}s")
    print()
    print("  Por proveedor:")
    for provider, counts in by_provider.items():
        total_p = counts["ok"] + counts["fail"]
        rate_p  = counts["ok"] / total_p * 100
        print(f"    {provider.upper():8s} — éxito: {counts['ok']}/{total_p} ({rate_p:.1f}%)")

    print()
    if failed:
        print("  Tareas fallidas:")
        for r in failed[:10]:  # Mostrar máximo 10
            print(f"    task_id={r.task_id[:8]}... provider={r.provider} error={r.error}")
        if len(failed) > 10:
            print(f"    ... y {len(failed) - 10} más")

    print("-" * 65)
    if success_rate == 100.0:
        print("  ✅ ASR CUMPLIDO: 100% de éxito en las peticiones realizadas")
    else:
        print(f"  ❌ ASR NO CUMPLIDO: tasa de éxito = {success_rate:.1f}% (se requiere 100%)")
        print()
        print("  Posibles causas:")
        print("    - max_retries insuficiente para la tasa de fallo del proveedor")
        print("    - POLL_TIMEOUT muy bajo: la tarea siguió en cola tras el tiempo límite")
        print("    - Worker de Celery no levantado o desconectado del broker Redis")
        print()
        print("  Cambios arquitecturales para lograr el cumplimiento:")
        print("    1. Aumentar max_retries en el worker (ej: 10 en lugar de 5)")
        print("    2. Aumentar el número de workers de Celery (más concurrencia)")
        print("    3. Usar ElastiCache con replicación para evitar pérdida del broker")
        print("    4. Implementar Dead Letter Queue para reprocesar tareas fallidas")
    print("=" * 65)


def main():
    print(f"Iniciando prueba de escalabilidad contra {HOST}")
    print(f"Configuración: {TOTAL_TASKS} tareas | concurrencia={CONCURRENCY} | "
          f"proveedores={PROVIDERS}")
    print(f"Tasa de fallo simulada por proveedor: ~10%")
    print("-" * 65)

    tasks = build_tasks()
    results: List[TaskResult] = []
    start_total = time.time()

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(run_single_task, t): t for t in tasks}
        done_count = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done_count += 1
            status_icon = "✅" if result.status == "SUCCESS" else "❌"
            print(
                f"  [{done_count:3d}/{TOTAL_TASKS}] {status_icon} "
                f"provider={result.provider:5s} "
                f"company={result.company_id} "
                f"time={result.elapsed_s:.1f}s "
                f"status={result.status}"
            )

    total_elapsed = round(time.time() - start_total, 1)
    print_results(results, total_elapsed)


if __name__ == "__main__":
    main()
