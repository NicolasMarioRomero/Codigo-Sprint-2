"""
monitoring/log_filters.py — ASR30
Filtro de logging que enmascara datos sensibles antes de que
cualquier handler escriba el registro.

Patrones detectados:
  - AWS Access Keys (AKIA...)
  - JWTs (eyJ...eyJ...firma)
  - AWS Account IDs (12 dígitos)
  - URIs con credenciales (postgres://user:pass@host)
"""
import re
import logging

PATTERNS = [
    # AWS Access Key
    (re.compile(r'AKIA[0-9A-Z]{16}'), 'AWS_KEY'),
    # JWT (3 segmentos base64 separados por puntos)
    (re.compile(r'eyJ[\w-]+\.[\w-]+\.[\w-]+'), 'JWT'),
    # AWS Account ID (12 dígitos, no parte de un número más largo)
    (re.compile(r'(?<![\d-])\d{12}(?![\d-])'), 'AWS_ACCOUNT'),
    # URI con credenciales: postgres://user:pass@host o mongodb://user:pass@host
    (re.compile(r'(postgres|mongodb)://[^:\s]+:[^@\s]+@'), 'DB_URI'),
]

MASK = '****'


def _sanitize(text):
    """Aplica todos los patrones de enmascaramiento sobre un texto."""
    if not isinstance(text, str):
        return text
    for pattern, _ in PATTERNS:
        text = pattern.sub(MASK, text)
    return text


class SensitiveDataFilter(logging.Filter):
    """
    Filtro que enmascara secretos antes de que cualquier handler escriba.
    Se aplica tanto a record.msg como a record.args (formato printf).

    Registrar en settings.py LOGGING → filters → sanitize:
        'sanitize': {'()': 'monitoring.log_filters.SensitiveDataFilter'}
    """

    def filter(self, record):
        # 1. Mensaje principal
        record.msg = _sanitize(str(record.msg))

        # 2. Args (cuando se usa logger.info("X = %s", val))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _sanitize(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(_sanitize(str(a)) for a in record.args)

        return True  # nunca descartar, solo modificar
