# scripts/setup_db.py

import sys
sys.path.insert(0, ".")

from storage.detection_log import DetectionLog
from storage.session_store import SessionStore
from storage.vector_store import VectorStore

print("Setting up storage layer...")
log = DetectionLog()
print("✅ SQLite database initialized")

store = SessionStore()
print("✅ Session store initialized")

vec = VectorStore()
vec.seed_examples()
print("✅ Vector store initialized")

print("\n✅ All storage layers ready")