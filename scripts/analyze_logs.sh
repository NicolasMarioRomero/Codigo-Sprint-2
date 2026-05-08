#!/bin/bash
# scripts/analyze_logs.sh — ASR30
# Analiza los archivos de log generados por log_store_consumer.py
# y verifica que ninguna entrada contiene datos sensibles sin enmascarar.
#
# USO: bash analyze_logs.sh [LOG_DIR]
# Ejemplo: bash analyze_logs.sh /var/log/bite/logs

LOG_DIR="${1:-/var/log/bite/logs}"

echo "========================================"
echo "ANÁLISIS DE ENMASCARAMIENTO EN LOGS"
echo "Directorio: $LOG_DIR"
echo "========================================"

PASS=0
FAIL=0

check_pattern() {
  local name="$1"
  local pattern="$2"
  local files="$3"

  COUNT=$(grep -rE "$pattern" $files 2>/dev/null | grep -v '\*\*\*\*' | wc -l)
  if [ "$COUNT" -gt 0 ]; then
    echo "✗ FALLA [$name]: $COUNT ocurrencia(s) sin enmascarar encontradas"
    grep -rE "$pattern" $files 2>/dev/null | grep -v '\*\*\*\*' | head -3
    FAIL=$((FAIL + 1))
  else
    echo "✓ OK    [$name]: sin datos sensibles en texto plano"
    PASS=$((PASS + 1))
  fi
}

# Verificar que los logs existen
if [ ! -d "$LOG_DIR" ]; then
  echo "ERROR: directorio $LOG_DIR no existe. Correr log_store_consumer primero."
  exit 1
fi

LOG_FILES="$LOG_DIR/*.log"

echo ""
echo "--- Patrones verificados ---"
check_pattern "AWS Access Key"   'AKIA[0-9A-Z]{16}'          "$LOG_FILES"
check_pattern "JWT Token"        'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' "$LOG_FILES"
check_pattern "AWS Account ID"   '[^0-9][0-9]{12}[^0-9]'    "$LOG_FILES"
check_pattern "DB URI con pass"  '(postgres|mongodb)://[^:]+:[^@]+@' "$LOG_FILES"

echo ""
echo "========================================"
echo "RESUMEN: $PASS OK  |  $FAIL FALLOS"

if [ "$FAIL" -eq 0 ]; then
  echo "✓ ASR30 CUMPLIDO: todos los datos sensibles están enmascarados"
  exit 0
else
  echo "✗ ASR30 FALLA: hay $FAIL tipo(s) de datos sensibles sin enmascarar"
  exit 1
fi
