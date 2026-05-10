"""
credentials/models.py — ASR29
Vault de credenciales cifradas en PostgreSQL.
Cifrado AES-256 con Fernet a nivel de columna.
"""
from django.db import models
from cryptography.fernet import Fernet
from django.conf import settings


class Credential(models.Model):
    AMBIENTES = [('dev', 'Desarrollo'), ('test', 'Pruebas'), ('prod', 'Producción')]
    PROVIDERS = [('aws', 'AWS'), ('gcp', 'GCP')]

    credential_id = models.CharField(max_length=64, unique=True)
    client_id     = models.CharField(max_length=64, db_index=True)
    ambiente      = models.CharField(max_length=10, choices=AMBIENTES, db_index=True)
    provider      = models.CharField(max_length=10, choices=PROVIDERS)
    encrypted_key = models.BinaryField()          # cifrado AES-256 con Fernet
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    rotated_at    = models.DateTimeField(null=True, blank=True)
    revoked_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'credentials'

    def get_key(self):
        f = Fernet(settings.VAULT_KEY)
        return f.decrypt(bytes(self.encrypted_key)).decode()

    def set_key(self, raw: str):
        f = Fernet(settings.VAULT_KEY)
        self.encrypted_key = f.encrypt(raw.encode())

    def __str__(self):
        return f"{self.credential_id} ({self.ambiente}/{self.provider})"


class CredentialUsage(models.Model):
    """Cada llamada exitosa o intento de uso registrado aquí."""
    credential  = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name='usages')
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)
    source_ip   = models.GenericIPAddressField()
    geo_country = models.CharField(max_length=2)   # código ISO-3166 (ej: 'CO')
    endpoint    = models.CharField(max_length=128)
    success     = models.BooleanField()

    class Meta:
        db_table = 'credential_usages'


class CredentialUsageHistory(models.Model):
    """Estadísticas precomputadas de los últimos 30 días por cliente."""
    client_id            = models.CharField(max_length=64, primary_key=True)
    typical_countries    = models.JSONField()       # ["CO", "US"]
    typical_hour_start   = models.IntegerField()    # ej: 9
    typical_hour_end     = models.IntegerField()    # ej: 18
    avg_requests_per_min = models.FloatField()
    stddev_requests      = models.FloatField()

    class Meta:
        db_table = 'credential_usage_history'


class AuditLog(models.Model):
    """Log inmutable de eventos de seguridad."""
    EVENT_TYPES = [
        ('ANOMALY', 'Anomalía detectada'),
        ('REVOCATION', 'Credencial revocada'),
        ('NOTIFICATION', 'Notificación enviada'),
    ]
    timestamp     = models.DateTimeField(auto_now_add=True)
    event_type    = models.CharField(max_length=32, choices=EVENT_TYPES)
    credential_id = models.CharField(max_length=64)
    details       = models.JSONField()

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
