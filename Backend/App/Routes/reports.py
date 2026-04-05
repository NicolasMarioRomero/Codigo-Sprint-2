from fastapi import APIRouter
from App.Services.report_service import get_report

router = APIRouter()

@router.get("/report/{company_id}")
def get_company_report(company_id: int):
    return get_report(company_id)