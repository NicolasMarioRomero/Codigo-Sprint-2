"""
seed_data.py
Pobla la base de datos con datos de prueba para el experimento.
Migrado de SQLAlchemy a Django ORM.

Ejecutar: python seed_data.py
Genera ~60.000 registros (10 empresas × 5 proyectos × 6 servicios × 200 fechas)
para simular un entorno real bajo carga.
"""
import os
import sys
import django
import random
import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

from reports.models import Report
from django.utils import timezone

AWS_SERVICES = ['EC2', 'S3', 'Lambda', 'RDS', 'CloudFront', 'EKS']
GCP_SERVICES = ['Compute Engine', 'Cloud Storage', 'Cloud Functions',
                'Cloud SQL', 'Google Kubernetes Engine', 'Cloud CDN']

COMPANIES            = list(range(1, 11))   # 10 empresas
PROJECTS_PER_COMPANY = 5
RECORDS_PER_SERVICE  = 200                  # ~60.000 registros total
BATCH_SIZE           = 5000


def seed():
    base_date = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
    records = []

    print("Generando registros de prueba...")
    for company_id in COMPANIES:
        # Empresas impares → solo AWS; pares → AWS + GCP
        provider_map = (
            [('aws', AWS_SERVICES)]
            if company_id % 2 == 1
            else [('aws', AWS_SERVICES), ('gcp', GCP_SERVICES)]
        )
        for project_id in range(1, PROJECTS_PER_COMPANY + 1):
            for provider_name, services in provider_map:
                for service in services:
                    for i in range(RECORDS_PER_SERVICE):
                        records.append(Report(
                            company_id=company_id,
                            project_id=project_id,
                            service_name=service,
                            provider=provider_name,
                            cost=round(random.uniform(5, 800), 2),
                            usage=round(random.uniform(1, 5000), 2),
                            currency='USD',
                            timestamp=base_date + datetime.timedelta(days=i),
                        ))

    total = len(records)
    print(f"Insertando {total} registros en batches de {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        Report.objects.bulk_create(batch, ignore_conflicts=True)
        print(f"  ✓ {min(i + BATCH_SIZE, total)}/{total} registros insertados")

    print(f"\n✅ Seed completado: {total} registros insertados.")


if __name__ == '__main__':
    seed()
