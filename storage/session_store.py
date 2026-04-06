# storage/session_store.py
# Uses Redis for live session state, falls back to in-memory dict if Redis unavailable

import json
import uuid
from datetime import datetime
import redis
from config import get_settings


class SessionStore:
    def __init__(self):
        settings = get_settings()
        try:
            self._redis = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self._redis.ping()
            self._use_redis = True
            print("✅ Session store: Redis connected")
        except Exception:
            self._use_redis = False
            self._memory: dict = {}
            print("⚠️  Session store: Redis unavailable, using in-memory fallback")

    # ── Internal get/set ───────────────────────────────────────────────────
    def _get(self, key: str):
        if self._use_redis:
            val = self._redis.get(key)
            return json.loads(val) if val else None
        return self._memory.get(key)

    def _set(self, key: str, value, ttl: int = 3600):
        if self._use_redis:
            self._redis.setex(key, ttl, json.dumps(value))
        else:
            self._memory[key] = value

    # ── Session Management ──────────────────────────────────────────────────
    def new_session(self) -> str:
        session_id = str(uuid.uuid4())[:8]
        self._set(f"session:{session_id}", {
            "id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "price_history": {},
            "cart_snapshots": [],
            "popup_counts": {},
            "detections": []
        })
        return session_id

    def get_session(self, session_id: str) -> dict:
        return self._get(f"session:{session_id}") or {}

    def update_session(self, session_id: str, updates: dict):
        session = self.get_session(session_id)
        session.update(updates)
        self._set(f"session:{session_id}", session)

    # ── Price Tracking ──────────────────────────────────────────────────────
    def store_price(self, session_id: str, stage: str, price_data: dict):
        session = self.get_session(session_id)
        if "price_history" not in session:
            session["price_history"] = {}
        session["price_history"][stage] = price_data
        self._set(f"session:{session_id}", session)

    def get_price_history(self, session_id: str) -> dict:
        return self.get_session(session_id).get("price_history", {})

    # ── Cart Tracking ───────────────────────────────────────────────────────
    def save_cart_snapshot(self, session_id: str, cart: list, user_action: bool = False):
        session = self.get_session(session_id)
        snapshots = session.get("cart_snapshots", [])
        snapshots.append({
            "cart": cart,
            "user_action": user_action,
            "timestamp": datetime.utcnow().isoformat()
        })
        session["cart_snapshots"] = snapshots[-10:]  # keep last 10
        self._set(f"session:{session_id}", session)

    def check_cart_sneaking(self, session_id: str, cart_before: list,
                             cart_after: list, user_clicked_add: bool) -> dict:
        before = set(cart_before)
        after  = set(cart_after)
        new_items = after - before
        if new_items and not user_clicked_add:
            return {
                "detected": True,
                "pattern_id": "DP02",
                "sneaked_items": list(new_items),
                "confidence": 0.92
            }
        return {"detected": False}

    # ── Popup / Nagging Tracking ────────────────────────────────────────────
    def increment_popup(self, session_id: str, popup_id: str) -> int:
        key = f"popup:{session_id}:{popup_id}"
        if self._use_redis:
            count = self._redis.incr(key)
            self._redis.expire(key, 3600)
        else:
            self._memory[key] = self._memory.get(key, 0) + 1
            count = self._memory[key]
        return count

    def check_nagging(self, session_id: str, popup_id: str) -> dict:
        count = self.increment_popup(session_id, popup_id)
        if count >= 3:
            return {
                "detected": True,
                "pattern_id": "DP10",
                "popup_count": count,
                "confidence": min(0.70 + (count * 0.05), 0.99)
            }
        return {"detected": False, "popup_count": count}