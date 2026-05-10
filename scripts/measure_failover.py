"""
scripts/measure_failover.py — Disponibilidad
Mide el tiempo de failover del cluster MongoDB sharded con carga continua.
Envía requests a /places/ mientras mata el primario de un shard y registra:
  - Cuántos requests fallaron
  - Duración exacta de la interrupción (ms)
  - ¿Se cumple el SLA de < 5 segundos?

USO:
  python3 measure_failover.py --mongos <host>:<port> \\
                               --app <base_url> \\
                               --shard-host <host> --shard-port <port>
"""
import argparse
import subprocess
import threading
import time
import requests
import sys


def _continuous_requests(base_url, results, stop_event):
    """Envía GETs a /places/ continuamente y registra latencias y errores."""
    while not stop_event.is_set():
        ts = time.time() * 1000
        try:
            r = requests.get(f'{base_url}/places/', timeout=3)
            latency = time.time() * 1000 - ts
            results.append({'ok': r.status_code < 400, 'latency_ms': latency, 'ts': ts})
        except Exception as exc:
            latency = time.time() * 1000 - ts
            results.append({'ok': False, 'latency_ms': latency, 'ts': ts, 'error': str(exc)})
        time.sleep(0.2)


def _kill_primary(shard_host, shard_port):
    """Fuerza un stepDown en el primario del shard."""
    cmd = [
        'mongosh',
        '--host', shard_host,
        '--port', str(shard_port),
        '--quiet', '--eval',
        'try { rs.stepDown(30); } catch(e) {}'
    ]
    subprocess.run(cmd, capture_output=True, timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', default='http://localhost:8000', help='URL base de la app Django')
    parser.add_argument('--shard-host', default='localhost')
    parser.add_argument('--shard-port', type=int, default=27101)
    parser.add_argument('--warmup', type=int, default=5, help='Segundos de calentamiento')
    parser.add_argument('--cooldown', type=int, default=15, help='Segundos post-fallo')
    args = parser.parse_args()

    print('=' * 50)
    print('MEDICIÓN DE FAILOVER — MongoDB Sharded Cluster')
    print(f'  App URL:    {args.app}')
    print(f'  Shard:      {args.shard_host}:{args.shard_port}')
    print('=' * 50)

    results = []
    stop_event = threading.Event()

    # Iniciar carga continua
    t = threading.Thread(target=_continuous_requests, args=(args.app, results, stop_event))
    t.start()

    print(f'\n[1] Calentamiento ({args.warmup}s)...')
    time.sleep(args.warmup)

    # Inyectar fallo
    fail_ts = time.time() * 1000
    print(f'\n[2] Inyectando fallo en {args.shard_host}:{args.shard_port}...')
    try:
        _kill_primary(args.shard_host, args.shard_port)
    except Exception as e:
        print(f'    Advertencia: {e}')

    # Esperar recuperación
    print(f'\n[3] Cooldown ({args.cooldown}s)...')
    time.sleep(args.cooldown)

    stop_event.set()
    t.join()

    # Analizar resultados
    failed = [r for r in results if not r['ok'] and r['ts'] >= fail_ts]
    ok     = [r for r in results if r['ok']]

    if failed:
        first_fail = min(r['ts'] for r in failed)
        last_fail  = max(r['ts'] for r in failed)
        outage_ms  = last_fail - first_fail
        first_ok_after = min(
            (r['ts'] for r in results if r['ok'] and r['ts'] > first_fail),
            default=None,
        )
        actual_outage_ms = (first_ok_after - first_fail) if first_ok_after else outage_ms
    else:
        actual_outage_ms = 0

    print('\n' + '=' * 50)
    print('RESULTADOS')
    print(f'  Total requests:   {len(results)}')
    print(f'  Exitosos:         {len(ok)}')
    print(f'  Fallidos:         {len(failed)}')
    print(f'  Duración outage:  {actual_outage_ms:.0f} ms')

    if actual_outage_ms < 5000:
        print(f'\n✓ DISPONIBILIDAD CUMPLIDA: outage = {actual_outage_ms:.0f}ms < 5000ms')
        sys.exit(0)
    else:
        print(f'\n✗ DISPONIBILIDAD INCUMPLIDA: outage = {actual_outage_ms:.0f}ms >= 5000ms')
        sys.exit(1)


if __name__ == '__main__':
    main()
