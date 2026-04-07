from .aws_provider import AWSProvider
from .gcp_provider import GCPProvider
from .base_provider import CloudProvider

# Registro de proveedores disponibles — agnóstico al proveedor
PROVIDER_REGISTRY: dict[str, CloudProvider] = {
    "aws": AWSProvider(),
    "gcp": GCPProvider(),
}


def get_provider(name: str) -> CloudProvider:
    provider = PROVIDER_REGISTRY.get(name.lower())
    if not provider:
        raise ValueError(f"Proveedor no soportado: '{name}'. Disponibles: {list(PROVIDER_REGISTRY.keys())}")
    return provider
