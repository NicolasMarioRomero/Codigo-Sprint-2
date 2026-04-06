from fastapi import APIRouter, HTTPException
from App.Services.report_service import get_report, get_dashboard_summary

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/report/{company_id}")
def get_company_report(company_id: int):
    """Retorna los reportes de consumo cloud de una empresa."""
    try:
        return get_report(company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/{company_id}")
def get_company_dashboard(company_id: int):
    """
    Dashboard de reportes con métricas agregadas.
    ASR Latencia: debe responder en < 3s bajo 5000 usuarios concurrentes.
    """
    try:
        return get_dashboard_summary(company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
