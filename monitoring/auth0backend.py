"""
monitoring/auth0backend.py
Backend de autenticación Auth0 + JWT — reutilizado del Lab 8.
Valida el token JWT del header Authorization: Bearer <token>
"""
import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def _get_auth0_public_key():
    """Obtiene la clave pública de Auth0 para verificar el JWT."""
    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    jwks = requests.get(jwks_url).json()
    return jwks


class Auth0Backend:
    """
    Backend que valida JWTs emitidos por Auth0.
    Se usa en las vistas protegidas del Vault (ASR29).
    """

    def authenticate(self, request, token=None):
        if token is None:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return None
            token = auth_header.split(' ')[1]

        try:
            jwks = _get_auth0_public_key()
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = {}
            for key in jwks['keys']:
                if key['kid'] == unverified_header['kid']:
                    rsa_key = {
                        'kty': key['kty'],
                        'kid': key['kid'],
                        'use': key['use'],
                        'n':   key['n'],
                        'e':   key['e'],
                    }

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=['RS256'],
                audience=settings.AUTH0_CLIENT_ID,
                issuer=f"https://{settings.AUTH0_DOMAIN}/",
            )
            sub = payload.get('sub', '')
            user, _ = User.objects.get_or_create(username=sub)
            return user

        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
