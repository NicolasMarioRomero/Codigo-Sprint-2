"""
extractor/providers/gcp_provider.py
Implementación concreta para Google Cloud Platform.
Simula llamadas a la GCP Cloud Billing API.
"""
import random
from typing import List, Dict, Any
from .base_provider import CloudProvider

GCP_SERVICES = [
    'Compute Engine', 'Cloud Storage', 'Cloud Functions',
    'Cloud SQL', 'Google Kubernetes Engine', 'Cloud CDN',
]


class GCPProvider(CloudProvider):

    @property
    def name(self) -> str:
        return 'gcp'

    def fetch_metrics(self, company_id: int, project_id: int) -> List[Dict[str, Any]]:
        """
        Simula la respuesta de GCP Cloud Billing API.
        En producción: google.cloud.billing.budgets_v1.BudgetServiceClient
        """
        if random.random() < 0.10:
            raise ConnectionError('GCP Cloud Billing API timeout')

        return [
            {
                'service_name': service,
                'cost':         round(random.uniform(10, 500), 2),
                'usage':        round(random.uniform(1, 1000), 2),
                'currency':     'USD',
                'provider':     self.name,
                'company_id':   company_id,
                'project_id':   project_id,
            }
            for service in GCP_SERVICES
        ]
