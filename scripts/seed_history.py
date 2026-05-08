"""
scripts/seed_history.py
Siembra datos de historial de uso (CredentialUsageHistory) para que las
reglas del detector funcionen sin necesitar 30 días de datos reales.

USO: python scripts/seed_history.py
"""
import os
import django
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

from credentials.models import Credential, CredentialUsageHistory

HISTORIES = [
    {
        'client_id': 'client-test-001',
        'typical_countries': ['CO', 'US', 'MX'],
        'typical_hour_start': 8,
        'typical_hour_end': 20,
        'avg_requests_per_min': 2.5,
        'stddev_requests': 1.0,
    },
    {
        'client_id': 'client-test-exfil',
        'typical_countries': ['CO', 'US'],
        'typical_hour_start': 9,
        'typical_hour_end': 18,
        'avg_requests_per_min': 1.0,
        'stddev_requests': 0.5,
    },
    {
        'client_id': 'client-demo',
        'typical_countries': ['CO'],
        'typical_hour_start': 7,
        'typical_hour_end': 22,
        'avg_requests_per_min': 5.0,
        'stddev_requests': 2.0,
    },
]

CREDENTIALS = [
    {'credential_id': 'cred-test-001', 'client_id': 'client-test-001',
     'ambiente': 'prod', 'provider': 'aws', 'raw_key': 'AKIAFAKEKEY0000000001'},
    {'credential_id': 'cred-test-002', 'client_id': 'client-test-001',
     'ambiente': 'dev',  'provider': 'gcp', 'raw_key': 'gcpfakeserviceaccountkey002'},
    {'credential_id': 'cred-demo-001', 'client_id': 'client-demo',
     'ambiente': 'prod', 'provider': 'aws', 'raw_key': 'AKIAFAKEKEY0000000003'},
]

print("Sembrando CredentialUsageHistory...")
for h in HISTORIES:
    obj, created = CredentialUsageHistory.objects.update_or_create(
        client_id=h['client_id'],
        defaults={k: v for k, v in h.items() if k != 'client_id'},
    )
    action = 'creado' if created else 'actualizado'
    print(f"  {obj.client_id} → {action}")

print("\nSembrando Credentials de prueba...")
for c in CREDENTIALS:
    if not Credential.objects.filter(credential_id=c['credential_id']).exists():
        cred = Credential(
            credential_id=c['credential_id'],
            client_id=c['client_id'],
            ambiente=c['ambiente'],
            provider=c['provider'],
        )
        cred.set_key(c['raw_key'])
        cred.save()
        print(f"  {cred.credential_id} → creada")
    else:
        print(f"  {c['credential_id']} → ya existe")

print("\nDatos de prueba listos.")
