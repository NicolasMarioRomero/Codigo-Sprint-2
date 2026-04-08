"""
seed_data.py
Pobla la base de datos con datos de prueba para el experimento.
Ejecutar desde el host: python seed_data.py
O desde Docker:        docker compose exec backend python seed_data.py

Genera ~60.000 registros (10 empresas x 5 proyectos x 6 servicios x 200 meses)
para simular un entorno real bajo carga.
"""
import os
import random
import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/cloudcosts"
)

# Servicios y providers agnósticos (ASR Escalabilidad)
AWS_SERVICES  = ["EC2", "S3", "Lambda", "RDS", "CloudFront", "EKS"]
GCP_SERVICES  = ["Compute Engine", "Cloud Storage", "Cloud Functions",
                  "Cloud SQL", "Google Kubernetes Engine", "Cloud CDN"]

COMPANIES            = list(range(1, 11))   # 10 empresas
PROJECTS_PER_COMPANY = 5
RECORDS_PER_SERVICE  = 200                  # 200 por servicio → ~60.000 total

engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def create_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reports (
                id           SERIAL PRIMARY KEY,
                company_id   INTEGER NOT NULL,
                project_id   INTEGER NOT NULL,
                service_name VARCHAR(100),
                provider     VARCHAR(50) DEFAULT 'aws',
                cost         FLOAT,
                usage        FLOAT,
                currency     VARCHAR(10) DEFAULT 'USD',
                timestamp    TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_company ON reports(company_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_company_provider "
            "ON reports(company_id, provider)"
        ))
        conn.commit()


def seed():
    print("Creando tabla si no existe...")
    create_table()

    session   = Session()
    records   = []
    base_date = datetime.datetime(2023, 1, 1)

    print("Generando registros de prueba...")
    for company_id in COMPANIES:
        # Empresas impares → AWS; pares → mix AWS + GCP
        if company_id % 2 == 1:
            provider_map = [("aws", AWS_SERVICES)]
        else:
            provider_map = [("aws", AWS_SERVICES), ("gcp", GCP_SERVICES)]

        for project_id in range(1, PROJECTS_PER_COMPANY + 1):
            for provider_name, services in provider_map:
                for service in services:
                    for i in range(RECORDS_PER_SERVICE):
                        records.append({
                            "company_id":  company_id,
                            "project_id":  project_id,
                            "service_name": service,
                            "provider":    provider_name,
                            "cost":        round(random.uniform(5, 800), 2),
                            "usage":       round(random.uniform(1, 5000), 2),
                            "currency":    "USD",
                            "timestamp":   base_date + datetime.timedelta(days=i),
                        })

    # Insertar en batches para mayor velocidad
    batch_size = 5000
    total      = len(records)
    print(f"Insertando {total} registros en batches de {batch_size}...")

    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        session.execute(
            text("""
                INSERT INTO reports
                    (company_id, project_id, service_name, provider,
                     cost, usage, currency, timestamp)
                VALUES
                    (:company_id, :project_id, :service_name, :provider,
                     :cost, :usage, :currency, :timestamp)
            """),
            batch,
        )
        session.commit()
        print(f"  ✓ {min(i + batch_size, total)}/{total} registros insertados")

    session.close()
    print(f"\n✅ Seed completado: {total} registros insertados.")


if __name__ == "__main__":
    seed()
