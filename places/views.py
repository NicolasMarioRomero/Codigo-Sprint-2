"""
places/views.py — Disponibilidad
Endpoints REST para el CRUD de lugares almacenados en MongoDB sharded.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from . import models as place_db

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def places(request):
    if request.method == 'GET':
        category = request.GET.get('category')
        try:
            docs = place_db.list_places(category=category)
            return JsonResponse({'places': docs})
        except Exception as e:
            logger.error("Error listando lugares: %s", e)
            return JsonResponse({'error': str(e)}, status=500)

    # POST
    try:
        data = json.loads(request.body)
        pid = place_db.create_place(
            name=data['name'],
            category=data['category'],
            lat=float(data['lat']),
            lon=float(data['lon']),
            description=data.get('description', ''),
        )
        logger.info("Lugar creado: %s", pid)
        return JsonResponse({'place_id': pid}, status=201)
    except KeyError as e:
        return JsonResponse({'error': f'Campo requerido: {e}'}, status=400)
    except Exception as e:
        logger.error("Error creando lugar: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['GET', 'DELETE'])
def place_detail(request, place_id):
    if request.method == 'GET':
        try:
            doc = place_db.get_place(place_id)
            if doc is None:
                return JsonResponse({'error': 'Lugar no encontrado'}, status=404)
            return JsonResponse(doc)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # DELETE
    try:
        deleted = place_db.delete_place(place_id)
        if not deleted:
            return JsonResponse({'error': 'Lugar no encontrado'}, status=404)
        return JsonResponse({'status': 'deleted'})
    except Exception as e:
        logger.error("Error eliminando lugar %s: %s", place_id, e)
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(['GET'])
def health(request):
    """Verifica conectividad con el cluster MongoDB."""
    try:
        from django.conf import settings
        import pymongo
        client = pymongo.MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        return JsonResponse({'status': 'ok', 'mongo': 'reachable'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'mongo': str(e)}, status=503)
