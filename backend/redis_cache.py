import redis
import os

class RedisCache:
    def __init__(self, host=None, port=None):
        host = host or os.environ.get('REDIS_HOST', 'redis')
        port = port or int(os.environ.get('REDIS_PORT', 6379))
        self.r = redis.Redis(host=host, port=port)

    def get_path(self, key):
        return self.r.get(key)
    
    def set_path(self, key, path):
        self.r.set(key, path)

    def delete_path(self, key):
        self.r.delete(key)

    def path_exists(self, key):
        return self.r.exists(key)
