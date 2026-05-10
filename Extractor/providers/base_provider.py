"""
extractor/providers/base_provider.py
Clase base para proveedores cloud — migrada de FastAPI a Django.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

REQUIRED_FIELDS = {'service_name', 'cost', 'usage', 'currency', 'provider', 'company_id', 'project_id'}


class CloudProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador del proveedor: 'aws', 'gcp', etc."""

    @abstractmethod
    def fetch_metrics(self, company_id: int, project_id: int) -> List[Dict[str, Any]]:
        """Extrae métricas del proveedor para una empresa/proyecto."""

    def validate(self, metric: Dict[str, Any]) -> bool:
        """Valida que un registro tenga todos los campos requeridos."""
        return REQUIRED_FIELDS.issubset(metric.keys())
