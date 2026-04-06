"""
seed_data.py
Pobla la base de datos con datos de prueba para el experimento.
Ejecutar: python seed_data.py

Genera 50.000 registros (10 empresas x 5 proyectos x 6 servicios x ~167 meses)
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

SERVICES = ["EC2", "S3", "Lambda", "RDS", "CloudFront", "EKS"]
COMPANIES = list(range(1, 11))      # 10 empresas
PROJECTS_PER_COMPANY = 5
RECORDS_PER_SERVICE = 200           # 200 registros por servicio → ~60.000 total

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def create_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reports (
                id          SERIAL PRIMARY KEY,
                company_id  INTEGER NOT NULL,
                project_id  INTEGER NOT NULL,
                service_name VARCHAR(100),
                cost        FLOAT,
                usage       FLOAT,
                currency    VARCHAR(10) DEFAULT 'USD',
                timestamp   TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_company ON reports(company_id)"))
        conn.commit()


def seed():
    print("Creando tabla...")
    create_table()

    session = Session()
    records = []
    base_date = datetime.datetime(2023, 1, 1)

    print("Generando datos...")
    for company_id in COMPANIES:
        for project_id in range(1, PROJECTS_PER_COMPANY + 1):
            for service in SERVICES:
                for i in range(RECORDS_PER_SERVICE):
                    records.append({
                        "company_id": company_id,
                        "project_id": project_id,
                        "service_name": service,
                        "cost": round(random.uniform(5, 800), 2),
                        "usage": round(random.uniform(1, 5000), 2),
                        "currency": "USD",
                        "timestamp": base_date + datetime.timedelta(days=i),
                    })

    # Insertar en batches para mayor velocidad
    batch_size = 5000
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        session.execute(
            text("""
                INSERT INTO reports (company_id, project_id, service_name, cost, usage, currency, timestamp)
                VALUES (:company_id, :project_id, :service_name, :cost, :usage, :currency, :timestamp)
            """),
            batch,
        )
        session.commit()
        print(f"  Insertados {min(i + batch_size, total)}/{total} registros...")

    session.close()
    print(f"\nSeed completado: {total} registros insertados.")


if __name__ == "__main__":
    seed()
