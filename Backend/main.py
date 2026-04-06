from fastapi import FastAPI
from App.Routes import reports
from App.Models.report import create_tables

app = FastAPI(title="BITE - Report Service", version="1.0.0")

# Crear tablas al arrancar
@app.on_event("startup")
def startup():
    create_tables()

app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
