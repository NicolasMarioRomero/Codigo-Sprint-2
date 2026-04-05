import redis

redis_client = redis.Redis(
    host="redis-endpoint",
    port=6379,
    decode_responses=True
)