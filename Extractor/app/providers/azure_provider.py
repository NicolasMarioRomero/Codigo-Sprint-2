"""
azure_provider.py
Implementación concreta para Microsoft Azure.
Simula llamadas a la Azure Cost Management API.
"""
import random
from typing import List, Dict, Any
from .base_provider import CloudProvider

AZURE_SERVICES = ["Virtual Machines", "Blob Storage", "Azure Functions",
                  "Azure SQL", "Azure Kubernetes Service", "CDN"]


class AzureProvider(CloudProvider):

    @property
    def name(self) -> str:
        return "azure"

    def fetch_metrics(self, company_id: int, project_id: int) -> List[Dict[str, Any]]:
        """
        Simula la respuesta de Azure Cost Management.
        En producción: azure.mgmt.costmanagement.CostManagementClient
        """
        # Simular falla aleatoria para probar resiliencia (10% de probabilidad)
        if random.random() < 0.10:
            raise ConnectionError("Azure Cost Management API timeout")

        return [
            {
                "service_name": service,
                "cost": round(random.uniform(10, 500), 2),
                "usage": round(random.uniform(1, 1000), 2),
                "currency": "USD",
                "provider": self.name,
                "company_id": company_id,
                "project_id": project_id,
            }
            for service in AZURE_SERVICES
        ]
