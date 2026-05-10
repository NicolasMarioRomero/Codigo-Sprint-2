"""
places/models.py — Disponibilidad
Modelo de lugar almacenado en MongoDB a través de PyMongo.
No hereda de models.Model (MongoDB no usa ORM de Django).
Este módulo define el schema y las operaciones CRUD del cluster sharded.
"""
from django.conf import settings
import pymongo

_client = None
_db     = None
_col    = None


def _get_collection():
    """Conexión lazy al cluster MongoDB (mongos). Reconecta si pierde conexión."""
    global _client, _db, _col
    if _client is None:
        _client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=5000,
        )
        _db  = _client['bite_db']
        _col = _db['places']
        # Índice geoespacial y shard key
        _col.create_index([('location', pymongo.GEOSPHERE)])
        _col.create_index('category')
    return _col


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def create_place(name: str, category: str, lat: float, lon: float, description: str = '') -> str:
    col = _get_collection()
    doc = {
        'name': name,
        'category': category,
        'description': description,
        'location': {'type': 'Point', 'coordinates': [lon, lat]},
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def list_places(category: str = None, limit: int = 50) -> list:
    col = _get_collection()
    query = {'category': category} if category else {}
    docs = list(col.find(query, {'_id': 1, 'name': 1, 'category': 1,
                                  'description': 1, 'location': 1}).limit(limit))
    for d in docs:
        d['_id'] = str(d['_id'])
    return docs


def get_place(place_id: str):
    from bson import ObjectId
    col = _get_collection()
    doc = col.find_one({'_id': ObjectId(place_id)})
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc


def delete_place(place_id: str) -> bool:
    from bson import ObjectId
    col = _get_collection()
    result = col.delete_one({'_id': ObjectId(place_id)})
    return result.deleted_count > 0
