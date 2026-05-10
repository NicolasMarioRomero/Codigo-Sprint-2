"""monitoring/urls.py — URLs raíz del proyecto."""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'bite-monitoring'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health),
    # Sprint 2 (migrado de FastAPI)
    path('api/v1/', include('reports.urls')),            # Reportes + Dashboard
    path('api/v1/', include('Extractor.urls')),          # Extractor cloud
    # Sprint 3
    path('credentials/', include('credentials.urls')),   # ASR29
    path('test/', include('log_handlers.urls')),         # ASR30
    path('places/', include('places.urls')),             # Disponibilidad
]
