"""
extractor/providers/aws_provider.py
Implementación concreta para Amazon Web Services.
Simula llamadas a la AWS Cost Explorer API.
"""
import random
from typing import List, Dict, Any
from .base_provider import CloudProvider

AWS_SERVICES = ['EC2', 'S3', 'Lambda', 'RDS', 'CloudFront', 'EKS']


class AWSProvider(CloudProvider):

    @property
    def name(self) -> str:
        return 'aws'

    def fetch_metrics(self, company_id: int, project_id: int) -> List[Dict[str, Any]]:
        """
        Simula la respuesta de AWS Cost Explorer.
        En producción: boto3.client('ce').get_cost_and_usage(...)
        """
        # 10% de probabilidad de fallo para probar reintentos
        if random.random() < 0.10:
            raise ConnectionError('AWS Cost Explorer API timeout')

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
            for service in AWS_SERVICES
        ]
