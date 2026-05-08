from django.contrib import admin
from .models import Credential, CredentialUsage, CredentialUsageHistory, AuditLog

admin.site.register(Credential)
admin.site.register(CredentialUsage)
admin.site.register(CredentialUsageHistory)
admin.site.register(AuditLog)
