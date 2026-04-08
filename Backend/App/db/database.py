from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/cloudcosts"
)

# Pool de conexiones optimizado para alta concurrencia
# Táctica: Múltiples copias de procesamiento (pool de conexiones)
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Conexiones permanentes en el pool
    max_overflow=40,       # Conexiones adicionales bajo carga pico
    pool_pre_ping=True,    # Verifica conexiones antes de usarlas
    pool_recycle=300,      # Recicla conexiones cada 5 minutos
    pool_timeout=10,       # Timeout para obtener conexión del pool
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
