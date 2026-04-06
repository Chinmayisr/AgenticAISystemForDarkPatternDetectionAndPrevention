# storage/vector_store.py
# Qdrant vector DB for RAG — retrieves similar dark pattern examples
# during agent classification to improve accuracy

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
from config import get_settings
import uuid

COLLECTION_NAME = "dark_pattern_examples"
VECTOR_SIZE = 384   # all-MiniLM-L6-v2 embedding size


class VectorStore:
    def __init__(self):
        settings = get_settings()
        try:
            self._client = QdrantClient(url=settings.qdrant_url, timeout=5)
            self._client.get_collections()
            self._available = True
            self._ensure_collection()
            print("✅ Vector store: Qdrant connected")
        except Exception as e:
            self._available = False
            print(f"⚠️  Vector store: Qdrant unavailable ({e}), RAG disabled")

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        existing = [c.name for c in self._client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )

    def _embed(self, text: str) -> list:
        """
        Embed text using a local sentence transformer.
        In production, use: sentence-transformers/all-MiniLM-L6-v2
        """
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return model.encode(text).tolist()
        except Exception:
            # Return zero vector if embedding fails
            return [0.0] * VECTOR_SIZE

    def add_example(self, text: str, pattern_id: str, pattern_name: str, source: str = ""):
        """Add a labeled dark pattern example to the vector store."""
        if not self._available:
            return
        embedding = self._embed(text)
        self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": text,
                    "pattern_id": pattern_id,
                    "pattern_name": pattern_name,
                    "source": source
                }
            )]
        )

    def search_similar(self, text: str, pattern_id: str = None, limit: int = 3) -> list:
        """
        Find similar dark pattern examples from the store.
        Used by agents for few-shot context.
        """
        if not self._available:
            return []
        embedding = self._embed(text)
        query_filter = None
        if pattern_id:
            query_filter = Filter(
                must=[FieldCondition(key="pattern_id", match=MatchValue(value=pattern_id))]
            )
        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            query_filter=query_filter,
            limit=limit
        )
        return [
            {"text": r.payload["text"], "pattern_id": r.payload["pattern_id"], "score": r.score}
            for r in results
        ]

    def seed_examples(self):
        """Seed the vector store with initial dark pattern examples."""
        if not self._available:
            return
        examples = [
            ("Only 2 left in stock!", "DP01", "False Urgency"),
            ("Hurry! Sale ends in 00:09:44", "DP01", "False Urgency"),
            ("🔥 12 people are viewing this right now", "DP01", "False Urgency"),
            ("No thanks, I hate saving money", "DP03", "Confirm Shaming"),
            ("No, I don't want free shipping", "DP03", "Confirm Shaming"),
            ("Add Premium Protection Plan $4.99/mo", "DP02", "Basket Sneaking"),
            ("Auto-renews at $99/year. Cancel anytime*", "DP05", "Subscription Trap"),
            ("Service fee: $3.99 | Convenience fee: $2.50", "DP08", "Drip Pricing"),
            ("Uncheck this box if you do not want to opt out of marketing", "DP11", "Trick Question"),
        ]
        for text, pid, pname in examples:
            self.add_example(text, pid, pname, source="seed")
        print(f"✅ Vector store seeded with {len(examples)} examples")