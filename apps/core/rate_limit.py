import hashlib

from django.core.cache import cache


class RateLimiter:
    def __init__(self, scope, limit, window_seconds):
        self.scope = scope
        self.limit = limit
        self.window_seconds = window_seconds

    def is_limited(self, request):
        key = self._cache_key(request)
        if cache.add(key, 1, timeout=self.window_seconds):
            return False
        try:
            count = cache.incr(key)
        except ValueError:
            if cache.add(key, 1, timeout=self.window_seconds):
                return False
            count = cache.get(key, self.limit + 1)
        return count > self.limit

    def _cache_key(self, request):
        client_address = request.META.get("REMOTE_ADDR", "")
        digest = hashlib.sha256(client_address.encode("utf-8")).hexdigest()[:24]
        return "arms:%s:%s" % (self.scope, digest)
