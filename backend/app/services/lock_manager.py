from contextlib import contextmanager
import os
import time
import threading
import uuid
from typing import Generator, List, Optional
import redis
from backend.app.core.config import get_settings


class LockContentionError(Exception):
    """Raised when an atomic lock cannot be acquired due to concurrent contention."""
    pass


LUA_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class InMemoryLockRegistry:
    """
    Thread-safe in-memory fallback lock registry used when Redis service is not active.
    Provides identical SET NX PX semantics with monotonic expiration and token validation.
    """
    def __init__(self):
        self._mutex = threading.Lock()
        self._locks = {}  # key -> (token, expire_at)

    def set_nx_px(self, key: str, token: str, px: int) -> bool:
        now = time.monotonic()
        with self._mutex:
            # Clean expired lock if present
            if key in self._locks:
                existing_token, expire_at = self._locks[key]
                if now >= expire_at:
                    del self._locks[key]
                else:
                    return False
            self._locks[key] = (token, now + (px / 1000.0))
            return True

    def release(self, key: str, token: str) -> bool:
        with self._mutex:
            if key in self._locks:
                existing_token, _ = self._locks[key]
                if existing_token == token:
                    del self._locks[key]
                    return True
            return False


_in_memory_registry = InMemoryLockRegistry()


class LockManager:
    """
    Unified atomic locking coordinator.
    Attempts Redis-based SET NX PX locking first, seamlessly falling back to the
    thread-safe in-memory coordinator if Redis is unavailable.
    """
    def __init__(self):
        self.settings = get_settings()
        self._redis_client = None
        self._redis_checked = False
        self._redis_available = False

    def _get_redis(self) -> Optional[redis.Redis]:
        if not self._redis_checked:
            try:
                client = redis.from_url(
                    self.settings.REDIS_URL,
                    socket_timeout=0.5,
                    socket_connect_timeout=0.5,
                    decode_responses=True
                )
                client.ping()
                self._redis_client = client
                self._redis_available = True
            except Exception:
                self._redis_client = None
                self._redis_available = False
            finally:
                self._redis_checked = True
        return self._redis_client if self._redis_available else None

    def acquire_single(self, key: str, token: str, ttl_ms: int) -> bool:
        r = self._get_redis()
        if r is not None:
            try:
                result = r.set(key, token, px=ttl_ms, nx=True)
                return bool(result)
            except Exception:
                # Fall back to in-memory if Redis connection drops
                pass
        return _in_memory_registry.set_nx_px(key, token, ttl_ms)

    def release_single(self, key: str, token: str) -> bool:
        r = self._get_redis()
        if r is not None:
            try:
                r.eval(LUA_RELEASE_SCRIPT, 1, key, token)
                return True
            except Exception:
                pass
        return _in_memory_registry.release(key, token)

    @contextmanager
    def acquire_lock(
        self,
        key: str,
        ttl_ms: int = 1500,
        retry_count: int = 15,
        retry_delay_ms: int = 40
    ) -> Generator[str, None, None]:
        """
        Acquires an atomic distributed lock over a single key with automatic fallback to in-memory coordinator.
        Retries up to retry_count times with retry_delay_ms before raising LockContentionError.
        """
        token = str(uuid.uuid4())
        start_time = time.monotonic()
        max_duration = (retry_count * retry_delay_ms) / 1000.0
        acquired = False

        for _ in range(retry_count):
            if self.acquire_single(key, token, ttl_ms):
                acquired = True
                break
            if (time.monotonic() - start_time) > max_duration:
                break
            time.sleep(retry_delay_ms / 1000.0)

        if not acquired:
            raise LockContentionError(f"Concurrent lock contention: unable to acquire lock for '{key}'")

        try:
            yield token
        finally:
            self.release_single(key, token)

    @contextmanager
    def acquire_reservation_lock(
        self,
        mandi_id: int,
        slot_id: int,
        farmer_id: int,
        ttl_ms: int = 1500,
        retry_count: int = 15,
        retry_delay_ms: int = 40
    ) -> Generator[str, None, None]:
        """
        Acquires atomic locks over both the hourly slot and the farmer yield boundary.
        Sorts lock keys lexicographically to prevent deadlocks under concurrent access.
        Retries up to retry_count times with retry_delay_ms before raising LockContentionError.
        """
        token = str(uuid.uuid4())
        keys: List[str] = sorted([
            f"lock:slot:{mandi_id}:{slot_id}",
            f"lock:farmer:{farmer_id}"
        ])
        acquired_keys: List[str] = []

        start_time = time.monotonic()
        max_duration = (retry_count * retry_delay_ms) / 1000.0

        for attempt in range(retry_count):
            acquired_keys.clear()
            all_acquired = True

            for key in keys:
                if self.acquire_single(key, token, ttl_ms):
                    acquired_keys.append(key)
                else:
                    all_acquired = False
                    break

            if all_acquired:
                break

            # Release partially acquired keys before backing off
            for key in acquired_keys:
                self.release_single(key, token)
            acquired_keys.clear()

            if (time.monotonic() - start_time) > max_duration:
                break
            time.sleep(retry_delay_ms / 1000.0)

        if len(acquired_keys) != len(keys):
            for key in acquired_keys:
                self.release_single(key, token)
            raise LockContentionError(
                f"Concurrent lock contention: unable to acquire locks for mandi={mandi_id}, slot={slot_id}, farmer={farmer_id}"
            )

        try:
            yield token
        finally:
            for key in keys:
                self.release_single(key, token)


lock_manager = LockManager()
