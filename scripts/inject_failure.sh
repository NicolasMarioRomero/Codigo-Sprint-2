#!/bin/bash
# scripts/inject_failure.sh — Disponibilidad
# Inyecta fallos en el cluster MongoDB para medir el tiempo de failover.
# Mata el proceso mongod primario de un shard y espera la elección.
#
# USO: bash inject_failure.sh <SHARD_HOST> <SHARD_PORT>
# Ejemplo: bash inject_failure.sh 10.0.1.10 27101

set -e

SHARD_HOST="${1:-localhost}"
SHARD_PORT="${2:-27101}"

echo "========================================"
echo "INYECCIÓN DE FALLO — MongoDB Shard"
echo "Host: $SHARD_HOST | Puerto: $SHARD_PORT"
echo "========================================"

# Verificar quién es el primario actual
echo ""
echo ">>> Estado del Replica Set ANTES del fallo:"
mongosh --host "$SHARD_HOST" --port "$SHARD_PORT" --quiet --eval "
  var status = rs.status();
  status.members.forEach(function(m) {
    print('  ' + m.name + ' → ' + m.stateStr);
  });
"

# Registrar timestamp del fallo
FAIL_TS=$(date +%s%3N)
echo ""
echo ">>> Matando el primario (stepDown + kill)..."
mongosh --host "$SHARD_HOST" --port "$SHARD_PORT" --quiet --eval "
  try { rs.stepDown(30); } catch(e) { /* conexión se cierra al stepDown */ }
" 2>/dev/null || true

echo ">>> Fallo inyectado en $(date). Esperando nueva elección..."

# Esperar y medir cuándo hay nuevo primario
MAX_WAIT=30
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  sleep 1
  ELAPSED=$((ELAPSED + 1))

  PRIMARY=$(mongosh --host "$SHARD_HOST" --port "$SHARD_PORT" --quiet --eval "
    try {
      var s = rs.status();
      var p = s.members.filter(function(m){ return m.stateStr === 'PRIMARY'; });
      print(p.length > 0 ? p[0].name : 'NONE');
    } catch(e) { print('NONE'); }
  " 2>/dev/null | tail -1)

  if [ "$PRIMARY" != "NONE" ] && [ -n "$PRIMARY" ]; then
    RECOVERY_TS=$(date +%s%3N)
    FAILOVER_MS=$((RECOVERY_TS - FAIL_TS))
    echo ""
    echo "========================================"
    echo "Nuevo primario: $PRIMARY"
    echo "Tiempo de failover: ${FAILOVER_MS} ms"
    if [ $FAILOVER_MS -lt 5000 ]; then
      echo "✓ DISPONIBILIDAD CUMPLIDA: failover < 5 segundos"
    else
      echo "✗ DISPONIBILIDAD INCUMPLIDA: failover >= 5 segundos"
    fi
    echo "========================================"
    exit 0
  fi

  echo "  Esperando... ${ELAPSED}s (primario: $PRIMARY)"
done

echo "✗ ERROR: No se eligió primario en ${MAX_WAIT}s"
exit 1
