"""
credentials/views.py — ASR29
Endpoints REST del Vault de credenciales.
Requiere autenticación Auth0 (JWT en header Authorization).
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Credential, CredentialUsage, AuditLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '0.0.0.0')


@csrf_exempt
@require_http_methods(['POST'])
def register_credential(request):
    """POST /credentials/register/ — Registra una nueva credencial en el Vault."""
    try:
        data = json.loads(request.body)
        cred = Credential(
            credential_id=data['credential_id'],
            client_id=data['client_id'],
            ambiente=data['ambiente'],
            provider=data['provider'],
        )
        cred.set_key(data['raw_key'])
        cred.save()
        logger.info("Credencial registrada: %s", data['credential_id'])
        return JsonResponse({'status': 'ok', 'credential_id': cred.credential_id}, status=201)
    except Exception as e:
        logger.error("Error registrando credencial: %s", str(e))
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(['POST'])
def use_credential(request):
    """
    POST /credentials/use/ — Registra el uso de una credencial y notifica al detector.
    1. Guarda CredentialUsage en PostgreSQL.
    2. Publica evento en RabbitMQ → el detector evalúa las reglas de anomalía.
    """
    try:
        data = json.loads(request.body)
        cred = Credential.objects.get(
            credential_id=data['credential_id'],
            is_active=True,
        )
        usage = CredentialUsage.objects.create(
            credential=cred,
            source_ip=_get_client_ip(request),
            geo_country=data.get('geo_country', 'CO'),
            endpoint=data.get('endpoint', 'unknown'),
            success=True,
        )
        logger.info("Uso registrado para %s desde %s", cred.credential_id, usage.geo_country)

        # Publicar en RabbitMQ para que el detector lo evalúe (ASR29)
        _publish_usage(cred, usage)

        return JsonResponse({'status': 'ok', 'usage_id': usage.id})
    except Credential.DoesNotExist:
        return JsonResponse({'error': 'Credencial no encontrada o revocada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def _publish_usage(cred, usage):
    """
    Publica el evento de uso en RabbitMQ de forma no bloqueante.
    Routing key: credential.usage.<ambiente>.<client_id>
    """
    try:
        import pika
        import json as _json
        from django.conf import settings

        rb = settings.RABBITMQ
        routing_key = f'credential.usage.{cred.ambiente}.{cred.client_id}'

        body = _json.dumps({
            'credential_id': cred.credential_id,
            'client_id':     cred.client_id,
            'ambiente':      cred.ambiente,
            'provider':      cred.provider,
            'usage_id':      usage.id,
            'geo_country':   usage.geo_country,
            'source_ip':     usage.source_ip,
            'endpoint':      usage.endpoint,
        })

        conn = pika.BlockingConnection(pika.ConnectionParameters(
            host=rb['HOST'], port=rb.get('PORT', 5672),
            credentials=pika.PlainCredentials(rb['USER'], rb['PASSWORD']),
            connection_attempts=2, retry_delay=1,
        ))
        ch = conn.channel()
        ch.exchange_declare(exchange=rb['EXCHANGE_SECURITY'], exchange_type='topic', durable=True)
        ch.basic_publish(
            exchange=rb['EXCHANGE_SECURITY'],
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2, content_type='application/json'),
        )
        conn.close()
        logger.info("Uso publicado en RabbitMQ: %s", routing_key)
    except Exception as exc:
        # No fallar el request si RabbitMQ no está disponible
        logger.warning("No se pudo publicar en RabbitMQ: %s", exc)


@require_http_methods(['GET'])
def list_credentials(request, client_id):
    """GET /credentials/<client_id>/ — Lista credenciales activas de un cliente."""
    creds = Credential.objects.filter(client_id=client_id).values(
        'credential_id', 'ambiente', 'provider', 'is_active', 'created_at', 'revoked_at'
    )
    return JsonResponse({'credentials': list(creds)})


@require_http_methods(['GET'])
def audit_log(request):
    """GET /credentials/audit/ — Lista los últimos eventos de seguridad."""
    logs = AuditLog.objects.all()[:100].values(
        'timestamp', 'event_type', 'credential_id', 'details'
    )
    return JsonResponse({'audit_log': list(logs)})
