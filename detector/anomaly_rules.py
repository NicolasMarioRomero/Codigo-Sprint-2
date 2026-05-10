"""
detector/anomaly_rules.py — ASR29
Tres reglas de detección de anomalías sobre el uso de credenciales.

Las reglas reciben un evento como dict (con los campos del uso) y el objeto
CredentialUsageHistory ya cargado, en lugar de objetos Django ORM directamente.
Esto permite evaluar eventos provenientes de RabbitMQ sin re-consultar la BD.

Regla 1 – GeoIP:     país del request no está en los típicos del cliente.
Regla 2 – Volumen:   requests/min supera media + 3*stddev en ventana de 5 min.
Regla 3 – Horario:   uso fuera del rango horario típico del cliente.
"""
from datetime import timedelta
from django.utils import timezone
from credentials.models import CredentialUsage, CredentialUsageHistory


# ── Regla 1: País no permitido ────────────────────────────────────────────────

def rule_geo(event, history):
    """
    Dispara si el país del evento no está en los países típicos del cliente.
    Retorna (True, detalle) si hay anomalía, (False, None) si es normal.
    """
    country = event.get('geo_country', '')
    if country not in history.typical_countries:
        return True, {
            'rule': 'GEO',
            'country_detected': country,
            'allowed_countries': history.typical_countries,
            'source_ip': event.get('source_ip'),
        }
    return False, None


# ── Regla 2: Volumen de requests ─────────────────────────────────────────────

def rule_volume(event, history):
    """
    Dispara si la tasa de uso en los últimos 5 min supera mean + 3*stddev.
    """
    if history.stddev_requests == 0:
        return False, None

    window_start = timezone.now() - timedelta(minutes=5)
    count_5min = CredentialUsage.objects.filter(
        credential__client_id=event['client_id'],
        timestamp__gte=window_start,
    ).count()

    rpm = count_5min / 5.0
    threshold = history.avg_requests_per_min + 3 * history.stddev_requests

    if rpm > threshold:
        return True, {
            'rule': 'VOLUME',
            'rpm_detected': round(rpm, 2),
            'threshold': round(threshold, 2),
            'mean': round(history.avg_requests_per_min, 2),
            'stddev': round(history.stddev_requests, 2),
        }
    return False, None


# ── Regla 3: Horario fuera de rango ─────────────────────────────────────────

def rule_time(event, history):
    """
    Dispara si la hora UTC actual está fuera del rango típico del cliente.
    """
    current_hour = timezone.now().hour
    start = history.typical_hour_start
    end = history.typical_hour_end

    # Rango puede cruzar medianoche (ej: 22 → 6)
    if start <= end:
        in_range = start <= current_hour < end
    else:
        in_range = current_hour >= start or current_hour < end

    if not in_range:
        return True, {
            'rule': 'TIME',
            'hour_detected': current_hour,
            'typical_range': f"{start:02d}:00 – {end:02d}:00 UTC",
        }
    return False, None


# ── Evaluador de todas las reglas ────────────────────────────────────────────

ALL_RULES = [rule_geo, rule_volume, rule_time]


def evaluate(event):
    """
    Evalúa todas las reglas para un evento de uso (dict).
    Retorna lista de detalles de anomalías encontradas.
    Lista vacía = uso legítimo.

    event debe contener al menos:
      - client_id, credential_id, ambiente, provider
      - geo_country, source_ip, endpoint
    """
    try:
        history = CredentialUsageHistory.objects.get(client_id=event['client_id'])
    except CredentialUsageHistory.DoesNotExist:
        # Sin historial no se puede evaluar → no anomalía
        return []

    anomalies = []
    for rule in ALL_RULES:
        triggered, detail = rule(event, history)
        if triggered:
            anomalies.append(detail)
    return anomalies
