import time
from typing import Dict, Tuple


class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = rate_per_sec
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.updated_at = time.monotonic()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.updated_at = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class RateLimiter:
    def __init__(self, rate_per_sec: float = 5.0, burst: int = 15):
        self.rate = rate_per_sec
        self.burst = burst
        self.buckets: Dict[str, TokenBucket] = {}

    def allow(self, key: str, cost: float = 1.0) -> bool:
        bucket = self.buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.rate, self.burst)
            self.buckets[key] = bucket
        return bucket.allow(cost)


