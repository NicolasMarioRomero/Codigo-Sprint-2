"""
base_provider.py
Interfaz abstracta del extractor agnóstico.
ASR Escalabilidad: el agente captura datos de forma agnóstica al proveedor cloud.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class CloudProvider(ABC):
    """
    Contrato que todo proveedor cloud debe implementar.
    Permite al agente extractor funcionar de forma agnóstica:
    no importa si el proveedor es AWS, Azure, GCP u otro.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del proveedor (ej: 'aws', 'azure', 'gcp')."""
        ...

    @abstractmethod
    def fetch_metrics(self, company_id: int, project_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene las métricas de consumo cloud para una empresa/proyecto.
        Retorna lista de dicts con estructura común:
            {
                "service_name": str,
                "cost": float,
                "usage": float,
                "currency": str,
                "provider": str,
            }
        """
        ...

    def validate(self, record: Dict[str, Any]) -> bool:
        """Valida que el registro tenga los campos mínimos requeridos."""
        required = {"service_name", "cost", "usage", "currency"}
        return required.issubset(record.keys())
