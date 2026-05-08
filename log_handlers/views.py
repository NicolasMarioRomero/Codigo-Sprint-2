"""
log_handlers/views.py — ASR30
Endpoints de prueba para verificar que SensitiveDataFilter enmascara datos
sensibles ANTES de que el handler los escriba o publique.

Los endpoints loguean intencionalmente secretos en distintos formatos;
los logs resultantes deben contener solo '****'.
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@require_http_methods(['GET'])
def leak_aws_key(request):
    """Loguea una AWS Access Key falsa — debe quedar enmascarada como ****."""
    fake_key = 'AKIAIOSFODNN7EXAMPLE'
    logger.warning("Procesando request con key=%s", fake_key)
    logger.info("Token de acceso: AKIAIOSFODNN7EXAMPLE para cliente test")
    return JsonResponse({
        'status': 'logged',
        'note': 'El log debe mostrar **** en lugar de la clave',
        'leaked_value': fake_key,
    })


@require_http_methods(['GET'])
def leak_jwt(request):
    """Loguea un JWT falso — debe quedar enmascarado."""
    fake_jwt = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
    logger.error("JWT en payload: %s", fake_jwt)
    return JsonResponse({
        'status': 'logged',
        'note': 'El log debe mostrar **** en lugar del JWT',
    })


@require_http_methods(['GET'])
def leak_account(request):
    """Loguea un AWS Account ID de 12 dígitos — debe quedar enmascarado."""
    fake_account = '123456789012'
    logger.info("Cuenta AWS: %s accedió al recurso", fake_account)
    return JsonResponse({
        'status': 'logged',
        'note': 'El log debe mostrar **** en lugar del account ID',
    })


@require_http_methods(['GET'])
def leak_db_uri(request):
    """Loguea una URI de BD con credenciales — debe quedar enmascarada."""
    fake_uri = 'postgres://admin:supersecret@db.prod.internal:5432/mydb'
    logger.critical("Conectando a: %s", fake_uri)
    return JsonResponse({
        'status': 'logged',
        'note': 'El log debe mostrar **** en lugar de las credenciales de BD',
    })
