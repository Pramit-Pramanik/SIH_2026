import threading
import time
from typing import Dict, List, Optional, Tuple
import redis
from backend.app.core.config import get_settings


class InMemoryQueueRegistry:
    """
    Thread-safe in-memory fallback Sorted Set (ZSET) implementation.
    Used when a live Redis server is not reachable during local execution or tests,
    guaranteeing identical ZSET mechanics, O(N log N) sorting, and deterministic tie-breaking.
    """
    def __init__(self):
        self._mutex = threading.RLock()
        # key -> dict(member -> score)
        self._sets: Dict[str, Dict[str, float]] = {}
        # key -> dict(member -> arrival_ts)
        self._metadata: Dict[str, Dict[str, float]] = {}

    def zadd(self, key: str, member: str, score: float, arrival_ts: float) -> int:
        with self._mutex:
            if key not in self._sets:
                self._sets[key] = {}
                self._metadata[key] = {}
            is_new = member not in self._sets[key]
            self._sets[key][member] = float(score)
            self._metadata[key][member] = float(arrival_ts)
            return 1 if is_new else 0

    def zrem(self, key: str, member: str) -> int:
        with self._mutex:
            if key in self._sets and member in self._sets[key]:
                del self._sets[key][member]
                if key in self._metadata and member in self._metadata[key]:
                    del self._metadata[key][member]
                return 1
            return 0

    def zscore(self, key: str, member: str) -> Optional[float]:
        with self._mutex:
            if key in self._sets:
                return self._sets[key].get(member)
            return None

    def zcard(self, key: str) -> int:
        with self._mutex:
            return len(self._sets.get(key, {}))

    def get_sorted_items(self, key: str) -> List[Tuple[str, float]]:
        """
        Returns all members ordered descending by score with deterministic tie-breaking:
        1. Higher score first (-score)
        2. Earlier arrival timestamp first (arrival_ts)
        3. Deterministic alphabetical transaction_id
        """
        with self._mutex:
            if key not in self._sets:
                return []
            items = self._sets[key]
            meta = self._metadata.get(key, {})

            sorted_members = sorted(
                items.keys(),
                key=lambda m: (-items[m], meta.get(m, 0.0), m)
            )
            return [(m, items[m]) for m in sorted_members]

    def zpopmax(self, key: str) -> Optional[Tuple[str, float]]:
        """
        Pops the highest-priority member using deterministic tie-breaking.
        """
        with self._mutex:
            sorted_items = self.get_sorted_items(key)
            if not sorted_items:
                return None
            winner_member, winner_score = sorted_items[0]
            del self._sets[key][winner_member]
            if key in self._metadata and winner_member in self._metadata[key]:
                del self._metadata[key][winner_member]
            return winner_member, winner_score

    def clear(self, key: Optional[str] = None) -> None:
        with self._mutex:
            if key:
                self._sets.pop(key, None)
                self._metadata.pop(key, None)
            else:
                self._sets.clear()
                self._metadata.clear()


_in_memory_queue = InMemoryQueueRegistry()


class QueueManager:
    """
    Manages active vehicle queues in Redis Sorted Sets (mandi:queue:{mandi_id}) per AC-006.
    Ensures that higher priority scores yield higher queue placement (via ZREVRANGE),
    applies deterministic tie-breaking under equal scores, and provides seamless
    in-memory fallback when Redis is offline.
    """
    def __init__(self):
        self.settings = get_settings()
        self._redis_client: Optional[redis.Redis] = None
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

    @staticmethod
    def get_queue_key(mandi_id: int) -> str:
        return f"mandi:queue:{mandi_id}"

    @staticmethod
    def get_meta_key(mandi_id: int) -> str:
        return f"mandi:queue:meta:{mandi_id}"

    def enqueue(
        self,
        mandi_id: int,
        transaction_id: str,
        priority_score: float,
        arrival_ts: Optional[float] = None
    ) -> int:
        """
        Enqueues or updates a vehicle in the mandi's active priority queue (Redis ZSET).
        """
        if arrival_ts is None:
            arrival_ts = time.time()

        queue_key = self.get_queue_key(mandi_id)
        meta_key = self.get_meta_key(mandi_id)
        r = self._get_redis()

        if r is not None:
            try:
                # Store pure float priority score in Redis ZSET
                res = r.zadd(queue_key, {transaction_id: float(priority_score)})
                # Store arrival metadata for deterministic tie-breaking
                r.hset(meta_key, transaction_id, str(arrival_ts))
                return int(res)
            except Exception:
                pass

        return _in_memory_queue.zadd(queue_key, transaction_id, priority_score, arrival_ts)

    def update_score(self, mandi_id: int, transaction_id: str, new_score: float) -> bool:
        """
        Re-indexes the vehicle with an updated priority score (e.g. after wait time elapses).
        """
        queue_key = self.get_queue_key(mandi_id)
        r = self._get_redis()
        if r is not None:
            try:
                if r.zscore(queue_key, transaction_id) is not None:
                    r.zadd(queue_key, {transaction_id: float(new_score)}, xx=True)
                    return True
                return False
            except Exception:
                pass

        current = _in_memory_queue.zscore(queue_key, transaction_id)
        if current is not None:
            # Preserve existing arrival timestamp
            meta = _in_memory_queue._metadata.get(queue_key, {})
            arrival_ts = meta.get(transaction_id, time.time())
            _in_memory_queue.zadd(queue_key, transaction_id, new_score, arrival_ts)
            return True
        return False

    def remove(self, mandi_id: int, transaction_id: str) -> bool:
        """
        Removes a vehicle from the active queue (e.g. upon quality rejection or cancellation).
        """
        queue_key = self.get_queue_key(mandi_id)
        meta_key = self.get_meta_key(mandi_id)
        r = self._get_redis()
        if r is not None:
            try:
                rem = r.zrem(queue_key, transaction_id)
                r.hdel(meta_key, transaction_id)
                return bool(rem > 0)
            except Exception:
                pass

        return bool(_in_memory_queue.zrem(queue_key, transaction_id) > 0)

    def get_score(self, mandi_id: int, transaction_id: str) -> Optional[float]:
        """
        Fetches the current DCDQ priority score for a transaction.
        """
        queue_key = self.get_queue_key(mandi_id)
        r = self._get_redis()
        if r is not None:
            try:
                score = r.zscore(queue_key, transaction_id)
                return float(score) if score is not None else None
            except Exception:
                pass

        return _in_memory_queue.zscore(queue_key, transaction_id)

    def get_arrival_timestamp(self, mandi_id: int, transaction_id: str) -> Optional[float]:
        """
        Retrieves recorded arrival timestamp for a queued transaction.
        """
        queue_key = self.get_queue_key(mandi_id)
        meta_key = self.get_meta_key(mandi_id)
        r = self._get_redis()
        if r is not None:
            try:
                val = r.hget(meta_key, transaction_id)
                return float(val) if val is not None else None
            except Exception:
                pass

        meta = _in_memory_queue._metadata.get(queue_key, {})
        return meta.get(transaction_id)

    def queue_length(self, mandi_id: int) -> int:
        """
        Returns the count of active vehicles in the queue (ZCARD).
        """
        queue_key = self.get_queue_key(mandi_id)
        r = self._get_redis()
        if r is not None:
            try:
                return int(r.zcard(queue_key))
            except Exception:
                pass

        return _in_memory_queue.zcard(queue_key)

    def get_queue(
        self,
        mandi_id: int,
        start: int = 0,
        stop: int = -1
    ) -> List[Tuple[str, float]]:
        """
        Retrieves active vehicles ordered descending by priority score (ZREVRANGE),
        applying deterministic tie-breaking (earlier arrival time, then transaction_id)
        when scores are identical.
        """
        queue_key = self.get_queue_key(mandi_id)
        meta_key = self.get_meta_key(mandi_id)
        r = self._get_redis()

        if r is not None:
            try:
                # Retrieve all members with scores in descending order
                raw_items = r.zrevrange(queue_key, 0, -1, withscores=True)
                if not raw_items:
                    return []

                # Fetch arrival timestamps for tie-breaking
                all_meta = r.hgetall(meta_key) or {}
                
                # Apply deterministic sorting: (-score, arrival_ts, member)
                sorted_items = sorted(
                    raw_items,
                    key=lambda item: (
                        -float(item[1]),
                        float(all_meta.get(item[0], 0.0)),
                        item[0]
                    )
                )

                if stop == -1:
                    return sorted_items[start:]
                return sorted_items[start : stop + 1]
            except Exception:
                pass

        all_items = _in_memory_queue.get_sorted_items(queue_key)
        if stop == -1:
            return all_items[start:]
        return all_items[start : stop + 1]

    def dispatch_pop(self, mandi_id: int) -> Optional[Tuple[str, float]]:
        """
        Pops and dispatches the highest-priority vehicle from the queue (ZPOPMAX with deterministic tie-breaking).
        Guarantees atomic pop via Redis Lua script so concurrent dispatchers cannot double-consume a vehicle.
        Returns (transaction_id, priority_score) or None if the queue is empty or already consumed.
        """
        queue_key = self.get_queue_key(mandi_id)
        meta_key = self.get_meta_key(mandi_id)
        r = self._get_redis()

        if r is not None:
            lua_script = """
            local queue_key = KEYS[1]
            local meta_key = KEYS[2]

            local raw_members = redis.call('ZREVRANGE', queue_key, 0, -1, 'WITHSCORES')
            if not raw_members or #raw_members == 0 then
                return nil
            end

            local best_member = nil
            local best_score = -1e18
            local best_arrival = 1e18

            for i = 1, #raw_members, 2 do
                local member = raw_members[i]
                local score = tonumber(raw_members[i+1])
                local arrival_raw = redis.call('HGET', meta_key, member)
                local arrival = arrival_raw and tonumber(arrival_raw) or 0.0

                if best_member == nil then
                    best_member = member
                    best_score = score
                    best_arrival = arrival
                else
                    if score > best_score then
                        best_member = member
                        best_score = score
                        best_arrival = arrival
                    elseif score == best_score then
                        if arrival < best_arrival then
                            best_member = member
                            best_score = score
                            best_arrival = arrival
                        elseif arrival == best_arrival then
                            if member < best_member then
                                best_member = member
                                best_score = score
                                best_arrival = arrival
                            end
                        end
                    end
                end
            end

            if best_member ~= nil then
                local rem = redis.call('ZREM', queue_key, best_member)
                if rem > 0 then
                    redis.call('HDEL', meta_key, best_member)
                    return {best_member, tostring(best_score)}
                end
            end

            return nil
            """
            try:
                result = r.eval(lua_script, 2, queue_key, meta_key)
                if result and len(result) >= 2:
                    return str(result[0]), float(result[1])
                return None
            except Exception:
                pass

        return _in_memory_queue.zpopmax(queue_key)

    def get_rank(self, mandi_id: int, transaction_id: str) -> Optional[int]:
        """
        Returns 1-indexed position in the active queue (1 = highest priority).
        """
        ordered = self.get_queue(mandi_id)
        for idx, (m, _) in enumerate(ordered, start=1):
            if m == transaction_id:
                return idx
        return None

    def clear(self, mandi_id: Optional[int] = None) -> None:
        """
        Clears queue state (used for test isolation).
        """
        if mandi_id is not None:
            q_key = self.get_queue_key(mandi_id)
            m_key = self.get_meta_key(mandi_id)
            r = self._get_redis()
            if r is not None:
                try:
                    r.delete(q_key, m_key)
                except Exception:
                    pass
            _in_memory_queue.clear(q_key)
        else:
            _in_memory_queue.clear()


queue_manager = QueueManager()
