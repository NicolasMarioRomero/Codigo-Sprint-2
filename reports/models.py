"""
reports/models.py
Modelo de reporte de consumo cloud — migrado de FastAPI + SQLAlchemy a Django ORM.
"""
from django.db import models
from django.utils import timezone


class Report(models.Model):
    PROVIDERS = [('aws', 'AWS'), ('gcp', 'GCP'), ('azure', 'Azure')]

    company_id   = models.IntegerField(db_index=True)
    project_id   = models.IntegerField(db_index=True)
    service_name = models.CharField(max_length=64)   # EC2, S3, Lambda, etc.
    provider     = models.CharField(max_length=16, choices=PROVIDERS, default='aws')
    cost         = models.FloatField()
    usage        = models.FloatField()
    currency     = models.CharField(max_length=8, default='USD')
    timestamp    = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'reports'
        ordering = ['-timestamp']

    def to_dict(self):
        return {
            'id':           self.id,
            'company_id':   self.company_id,
            'project_id':   self.project_id,
            'service_name': self.service_name,
            'provider':     self.provider,
            'cost':         self.cost,
            'usage':        self.usage,
            'currency':     self.currency,
            'timestamp':    self.timestamp.isoformat(),
        }

    def __str__(self):
        return f"Report({self.company_id}/{self.project_id} — {self.service_name})"
