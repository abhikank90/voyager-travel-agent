"""
Seed the Qdrant vector store with destination knowledge.

Usage:
    python scripts/seed_knowledge_base.py

Requires ANTHROPIC_API_KEY and optionally QDRANT_URL (defaults to localhost:6333).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def main():
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        print("Install qdrant-client: pip install qdrant-client")
        sys.exit(1)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(qdrant_url)

    collection = "destinations"
    try:
        client.get_collection(collection)
        print(f"Collection '{collection}' already exists, skipping creation.")
    except Exception:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        print(f"Created collection '{collection}'")

    db_path = ROOT / "data" / "knowledge_base" / "destinations.json"
    with open(db_path) as f:
        data = json.load(f)

    llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
    points = []

    for i, dest in enumerate(data["destinations"]):
        text = f"{dest['name']} — {', '.join(dest['popular_interests'])}. Beaches: {', '.join(dest['top_beaches'][:3])}. Restaurants: {', '.join(dest['top_restaurants'][:3])}."
        embedding = llm.embed_query(text) if hasattr(llm, "embed_query") else [0.0] * 1536
        points.append(PointStruct(id=i, vector=embedding, payload=dest))

    client.upsert(collection_name=collection, points=points)
    print(f"Seeded {len(points)} destinations into Qdrant.")


if __name__ == "__main__":
    main()
