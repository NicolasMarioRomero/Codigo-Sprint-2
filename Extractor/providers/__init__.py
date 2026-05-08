from .aws_provider import AWSProvider
from .gcp_provider import GCPProvider

_REGISTRY = {
    'aws': AWSProvider,
    'gcp': GCPProvider,
}


def get_provider(name: str):
    """Devuelve una instancia del proveedor por nombre. Lanza ValueError si no existe."""
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        raise ValueError(f"Proveedor '{name}' no soportado. Opciones: {list(_REGISTRY)}")
    return cls()
