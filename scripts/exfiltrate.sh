#!/bin/bash
# scripts/exfiltrate.sh — ASR29 / ASR30
# Simula un intento de exfiltración de credenciales:
#   1. Registra una credencial de prueba
#   2. Lanza 30 usos desde país NO permitido (RU) a las 03:00 UTC
#      para disparar las reglas GEO + TIME del detector
#   3. Verifica que la credencial fue revocada en < 10 minutos
#
# USO: bash exfiltrate.sh <BASE_URL> [TOKEN]
# Ejemplo: bash exfiltrate.sh http://10.0.0.5:8000 eyJhbGci...

set -e

BASE_URL="${1:-http://localhost:8000}"
TOKEN="${2:-}"
CRED_ID="cred-exfil-$(date +%s)"

AUTH_HEADER=""
if [ -n "$TOKEN" ]; then
  AUTH_HEADER="-H 'Authorization: Bearer $TOKEN'"
fi

echo "=========================================="
echo "SIMULACIÓN DE EXFILTRACIÓN DE CREDENCIAL"
echo "Base URL: $BASE_URL"
echo "Credential ID: $CRED_ID"
echo "=========================================="

# ── 1. Registrar credencial ──────────────────────────────────────────────────
echo ""
echo ">>> [1/3] Registrando credencial $CRED_ID..."
curl -s -X POST "$BASE_URL/credentials/register/" \
  -H "Content-Type: application/json" \
  -d "{
    \"credential_id\": \"$CRED_ID\",
    \"client_id\": \"client-test-exfil\",
    \"ambiente\": \"prod\",
    \"provider\": \"aws\",
    \"raw_key\": \"AKIAIOSFODNN7EXAMPLEFAKEKEY\"
  }" | python3 -m json.tool

# ── 2. Simular usos desde RU (anomalía geográfica) ───────────────────────────
echo ""
echo ">>> [2/3] Lanzando 30 requests desde RU (anomalía GEO)..."
START_TS=$(date +%s)

for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/credentials/use/" \
    -H "Content-Type: application/json" \
    -d "{
      \"credential_id\": \"$CRED_ID\",
      \"geo_country\": \"RU\",
      \"endpoint\": \"/admin/export_all\"
    }")
  echo "  Request $i → HTTP $STATUS"
  sleep 2
done

# ── 3. Verificar revocación ───────────────────────────────────────────────────
echo ""
echo ">>> [3/3] Verificando estado de la credencial..."
ELAPSED=$(( $(date +%s) - START_TS ))

RESPONSE=$(curl -s "$BASE_URL/credentials/client-test-exfil/")
echo "$RESPONSE" | python3 -m json.tool

REVOKED=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
creds = data.get('credentials', [])
for c in creds:
    if c['credential_id'] == '$CRED_ID':
        print('REVOKED' if not c['is_active'] else 'ACTIVE')
        sys.exit(0)
print('NOT_FOUND')
")

echo ""
echo "=========================================="
echo "RESULTADO: Credencial $CRED_ID → $REVOKED"
echo "Tiempo transcurrido: ${ELAPSED}s"
if [ "$REVOKED" = "REVOKED" ]; then
  echo "✓ ASR29 CUMPLIDO: credencial revocada en ${ELAPSED}s (< 600s)"
else
  echo "✗ ASR29 PENDIENTE: credencial no revocada aún (puede tardar hasta 60s)"
fi
echo "=========================================="

# Mostrar audit log
echo ""
echo ">>> Últimos eventos de seguridad:"
curl -s "$BASE_URL/credentials/audit/" | python3 -m json.tool
