"""
producers/producer_usage.py — ASR29
Simula tráfico de uso de credenciales publicando en RabbitMQ.
También llama directamente al endpoint /credentials/use/ para registrar
el uso en PostgreSQL (CredentialUsage) y que el detector lo evalúe.

Modos de tráfico:
  --mode normal    → países CO/US, hora 09-18, tasa baja
  --mode attack    → país aleatorio, hora 02-04, tasa alta (simula exfiltración)
"""
import argparse
import json
import random
import time
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitoring.settings')
django.setup()

import pika
import requests
from django.conf import settings

BASE_URL  = os.getenv('BASE_URL', 'http://localhost:8000')
ENDPOINTS = ['/api/data', '/api/report', '/api/export', '/billing']

NORMAL_COUNTRIES = ['CO', 'US', 'MX']
ATTACK_COUNTRIES = ['RU', 'CN', 'KP', 'IR', 'VN']


def _get_rabbitmq_channel():
    rb = settings.RABBITMQ
    creds = pika.PlainCredentials(rb['USER'], rb['PASSWORD'])
    params = pika.ConnectionParameters(
        host=rb['HOST'], port=rb.get('PORT', 5672), credentials=creds,
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(
        exchange=rb['EXCHANGE_SECURITY'], exchange_type='topic', durable=True,
    )
    return conn, ch


def simulate_usage(credential_id, mode='normal', count=10, delay=1.0):
    for i in range(count):
        if mode == 'attack':
            country  = random.choice(ATTACK_COUNTRIES)
            endpoint = '/admin/export_all'
        else:
            country  = random.choice(NORMAL_COUNTRIES)
            endpoint = random.choice(ENDPOINTS)

        payload = {
            'credential_id': credential_id,
            'geo_country': country,
            'endpoint': endpoint,
        }

        try:
            resp = requests.post(
                f'{BASE_URL}/credentials/use/',
                json=payload,
                timeout=5,
            )
            data = resp.json()
            usage_id = data.get('usage_id')

            if usage_id:
                # Publicar evento en RabbitMQ para que el detector lo procese
                conn, ch = _get_rabbitmq_channel()
                rb = settings.RABBITMQ
                ch.basic_publish(
                    exchange=rb['EXCHANGE_SECURITY'],
                    routing_key=f'credential.usage.{credential_id}',
                    body=json.dumps({
                        'credential_id': credential_id,
                        'usage_id': usage_id,
                    }),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                conn.close()

            print(f"[{i+1}/{count}] {mode.upper()} | {country} | {endpoint} | status={resp.status_code}")
        except Exception as exc:
            print(f"[{i+1}/{count}] ERROR: {exc}")

        time.sleep(delay)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulador de uso de credenciales')
    parser.add_argument('--credential', required=True, help='credential_id a simular')
    parser.add_argument('--mode', choices=['normal', 'attack'], default='normal')
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--delay', type=float, default=1.0, help='segundos entre requests')
    args = parser.parse_args()

    simulate_usage(args.credential, args.mode, args.count, args.delay)
