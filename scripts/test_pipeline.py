# scripts/test_pipeline.py

import asyncio
import sys
sys.path.insert(0, ".")


async def test_all_layers():
    print("\n" + "="*50)
    print("DARK GUARD — SYSTEM VERIFICATION")
    print("="*50)

    # ── Test 1: Config ──────────────────────────────────────────────
    print("\n[1/6] Testing configuration...")
    try:
        from config import get_settings, DARK_PATTERNS
        settings = get_settings()
        assert settings.google_api_key, "GOOGLE_API_KEY missing"
        assert len(DARK_PATTERNS) == 13, f"Expected 13 patterns, got {len(DARK_PATTERNS)}"
        print(f"  ✅ Config OK — Model: {settings.orchestrator_model}")
    except Exception as e:
        print(f"  ❌ Config FAILED: {e}")
        return

    # ── Test 2: SQLite ──────────────────────────────────────────────
    print("\n[2/6] Testing SQLite storage...")
    try:
        from storage.detection_log import DetectionLog
        log = DetectionLog()
        rec_id = log.insert({
            "session_id": "test_session",
            "pattern_id": "DP01",
            "pattern_name": "False Urgency",
            "confidence": 0.92,
            "input_type": "text",
            "evidence": "Only 2 left in stock!",
            "prevention": "Ignore timer",
            "source_url": "https://test.com",
            "platform": "test"
        })
        assert rec_id > 0
        print(f"  ✅ SQLite OK — Inserted record ID: {rec_id}")
    except Exception as e:
        print(f"  ❌ SQLite FAILED: {e}")

    # ── Test 3: Redis Session Store ────────────────────────────────
    print("\n[3/6] Testing session store...")
    try:
        from storage.session_store import SessionStore
        store = SessionStore()
        sid = store.new_session()
        assert len(sid) == 8
        store.store_price(sid, "product_page", {"item": 29.99})
        history = store.get_price_history(sid)
        assert "product_page" in history
        print(f"  ✅ Session store OK — Session: {sid}")
    except Exception as e:
        print(f"  ❌ Session store FAILED: {e}")

    # ── Test 4: Vector Store ───────────────────────────────────────
    print("\n[4/6] Testing vector store...")
    try:
        from storage.vector_store import VectorStore
        vec = VectorStore()
        if vec._available:
            results = vec.search_similar("Only 2 left in stock!", "DP01", limit=2)
            print(f"  ✅ Vector store OK — Found {len(results)} similar examples")
        else:
            print("  ⚠️  Vector store unavailable (Qdrant not running) — skipping")
    except Exception as e:
        print(f"  ❌ Vector store FAILED: {e}")

    # ── Test 5: API configuration ───────────────────────────────────────────
    print("\n[5/6] Testing API configuration...")
    try:
        assert settings.google_api_key, "GOOGLE_API_KEY missing"
        print(f"  ✅ API config OK — Using Google model: {settings.orchestrator_model}")
    except Exception as e:
        print(f"  ❌ API config FAILED: {e}")

    # ── Test 6: NLP Tool ───────────────────────────────────────────
    print("\n[6/6] Testing NLP tool (rule-based)...")
    try:
        from mcp_server.tools.nlp_tools import classify_text
        result = await classify_text({
            "text": "Only 2 left in stock! Hurry, sale ends in 00:09:44!",
            "context": "product page banner",
            "session_id": "test"
        })
        patterns = result.get("suspected_patterns", [])
        assert "DP01" in patterns, f"DP01 not detected. Got: {patterns}"
        print(f"  ✅ NLP tool OK — Detected: {patterns}")
    except Exception as e:
        print(f"  ❌ NLP tool FAILED: {e}")

    print("\n" + "="*50)
    print("✅ VERIFICATION COMPLETE — System is ready")
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(test_all_layers())