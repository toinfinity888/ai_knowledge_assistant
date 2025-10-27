"""
Verify Configuration and Load Knowledge Base
Checks Qdrant connection and loads camera support articles
"""
import asyncio
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from uuid import uuid4
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app.core.rag_singleton import embedder
from app.models.text_chunk import TextChunk
from app.models.embedded import EmbeddedChunk

# Camera support knowledge base
CAMERA_KNOWLEDGE_BASE = [
    {
        "title": "Subscription Not Showing After Renewal",
        "content": """
**Issue:** Customer's subscription is not visible in their account after renewal

**Common Causes:**
1. Payment processing delay (24-48 hours)
2. Account sync issue between billing and service
3. Browser cache showing old data

**Resolution Steps:**
1. Verify payment was processed successfully
2. Force account sync: Have customer log out completely, clear cache, log back in
3. Manual sync in admin panel: Admin > Subscriptions > Force Sync
4. If still not showing: Escalate to Tier 2 support

**Resolution Time:** 5-10 minutes
**Success Rate:** 95%
        """,
        "category": "subscription",
        "keywords": ["subscription not showing", "renewal", "account sync"]
    },
    {
        "title": "Camera Recordings Not Visible - Subscription Active",
        "content": """
**Issue:** Customer has active subscription but cannot view recordings

**Symptoms:**
- Motion notifications work
- Recording indicator shows
- "No recordings" message when viewing
- Affects mobile app and web

**Resolution Steps:**
1. Check camera status: Verify all cameras show "Online"
2. Check storage quota: Admin > Account > Storage
3. Verify subscription tier: Confirm correct plan is active
4. Force recording refresh: Admin > Recordings > Rebuild Index

**Resolution Time:** 10-15 minutes
        """,
        "category": "recordings",
        "keywords": ["no recordings", "can't see recordings", "camera subscription"]
    },
    {
        "title": "Multi-Camera Subscription Issues",
        "content": """
**Issue:** Problems with multi-camera subscriptions (5+ cameras)

**Resolution Steps:**
1. Verify camera allocation: Admin > Subscriptions > Camera Slots
2. Check bandwidth: Minimum 2 Mbps per camera
3. Storage distribution: Verify storage allocated evenly
4. Long-term customers may have legacy plan - check migration needed

**Resolution Time:** 15-20 minutes
        """,
        "category": "multi-camera",
        "keywords": ["10 cameras", "multiple cameras", "camera limit"]
    },
    {
        "title": "Known Issue - Recent Subscription Problems",
        "content": """
**Issue:** Subscription display issues from last week's database migration

**Status:** RESOLVED - Fast fix available

**Resolution Steps:**
1. This is a KNOWN ISSUE - apologize to customer
2. Admin > Tools > Subscription Repair
3. Enter customer email/ID and click "Repair Subscription Link"
4. Takes 2-3 minutes, have customer log out/in
5. Offer 1 week free service as compensation

**Resolution Time:** 5 minutes
        """,
        "category": "known-issues",
        "keywords": ["last week", "subscription stopped", "recent issue"]
    },
]


async def main():
    print("="*80)
    print("CONFIGURATION VERIFICATION & KNOWLEDGE BASE LOADING")
    print("="*80)
    print()

    # Step 1: Check environment variables
    print("[1/5] Checking configuration...")
    host = os.getenv('QDRANT_HOST')
    api_key = os.getenv('QDRANT_API_KEY')
    collection = os.getenv('QDRANT_COLLECTION_NAME') or os.getenv('QDRANT_COLLECTION')
    vector_size = int(os.getenv('QDRANT_VECTOR_SIZE', 3065))

    print(f"  Host: {host}")
    print(f"  Collection: {collection}")
    print(f"  Vector Size: {vector_size}")
    print()

    # Step 2: Connect to Qdrant
    print("[2/5] Connecting to Qdrant...")
    client = QdrantClient(
        url=f"https://{host}:6333",
        api_key=api_key,
    )

    # List collections
    collections = client.get_collections()
    print(f"✓ Connected! Found {len(collections.collections)} collections:")
    for col in collections.collections:
        print(f"  - {col.name}")
    print()

    # Step 3: Ensure collection exists
    print(f"[3/5] Checking collection '{collection}'...")
    if not client.collection_exists(collection):
        print(f"  Creating collection '{collection}'...")
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        print(f"✓ Collection created!")
    else:
        print(f"✓ Collection exists!")

    # Check collection info
    info = client.get_collection(collection)
    print(f"  Vectors: {info.points_count}")
    print()

    # Step 4: Load knowledge base
    print(f"[4/5] Loading knowledge base articles...")
    print(f"  Articles to load: {len(CAMERA_KNOWLEDGE_BASE)}")
    print()

    # Embedder already initialized from singleton

    # Process articles
    points = []
    for i, article in enumerate(CAMERA_KNOWLEDGE_BASE):
        print(f"  [{i+1}/{len(CAMERA_KNOWLEDGE_BASE)}] {article['title']}")

        # Create full text
        full_text = f"Title: {article['title']}\n\nCategory: {article['category']}\n\n{article['content']}"

        # Create text chunk
        source_file = f"kb_article_{i+1}.txt"
        chunk = TextChunk(
            text=full_text,
            source=Path(source_file),
            file_name=source_file,
            page=1,
            file_type="knowledge_base",
            last_modified=datetime.utcnow()
        )

        # Generate embedding (expects list of TextChunk objects)
        embedded_chunks = embedder.embed_text([chunk])
        embedded = embedded_chunks[0]

        # Create Qdrant point with custom metadata
        point = PointStruct(
            id=str(uuid4()),
            vector=embedded.embedding,
            payload={
                "text": chunk.text,
                "source": str(chunk.source),
                "file_name": chunk.file_name,
                "page": chunk.page,
                "file_type": chunk.file_type,
                "metadata": {
                    "title": article['title'],
                    "category": article['category'],
                    "keywords": article['keywords']
                }
            }
        )

        points.append(point)

    print()
    print(f"  Uploading {len(points)} points to Qdrant...")

    # Upload to Qdrant
    client.upsert(
        collection_name=collection,
        points=points
    )

    print(f"✓ Knowledge base loaded!")
    print()

    # Step 5: Verify
    print("[5/5] Verifying...")
    info = client.get_collection(collection)
    print(f"  Total vectors in collection: {info.points_count}")
    print()

    # Test search
    print("Testing search with example query...")
    test_query = "Customer subscription not showing, cameras stopped recording"

    # Create query object for embedding
    from app.models.query import Query
    query_obj = Query(text=test_query)
    embedded_query = embedder.embed_query(query_obj)
    query_embedding = embedded_query.embedding

    results = client.search(
        collection_name=collection,
        query_vector=query_embedding,
        limit=3
    )

    print(f"  Query: '{test_query}'")
    print(f"  Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        title = result.payload.get('metadata', {}).get('title', 'Unknown')
        print(f"    {i}. {title} (score: {result.score:.3f})")

    print()
    print("="*80)
    print("✅ SETUP COMPLETE!")
    print("="*80)
    print()
    print("Your system is ready! Try:")
    print("  1. python test_camera_scenario.py  # Test with example scenario")
    print("  2. ./launch_demo.sh                # Launch web demo")
    print("  3. http://localhost:8080/demo      # Open in browser")
    print()


if __name__ == "__main__":
    asyncio.run(main())
