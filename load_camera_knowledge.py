"""
Load Camera Support Knowledge Base
Loads camera subscription troubleshooting articles into Qdrant
"""
import asyncio
from datetime import datetime
from app.core.rag_singleton import get_rag_engine, embedder, vector_store
from app.models.text_chunk import TextChunk
from app.models.embedded import EmbeddedChunk

# Sample knowledge base articles for camera subscription issues
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
           - Check email for payment confirmation
           - Verify with billing team if payment cleared

        2. Force account sync:
           - Have customer log out completely
           - Clear browser cache/app data
           - Log back in

        3. Manual sync in admin panel:
           - Go to Admin > Subscriptions
           - Find customer account
           - Click "Force Sync"
           - Wait 5 minutes, have customer refresh

        4. If still not showing:
           - Escalate to Tier 2 support
           - Create ticket with subscription ID

        **Resolution Time:** 5-10 minutes (or 24-48 hours if payment pending)
        **Success Rate:** 95%
        """,
        "category": "subscription",
        "keywords": ["subscription not showing", "renewal", "account sync", "payment"]
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

        **Common Causes:**
        1. Storage quota exceeded
        2. Camera offline/disconnected
        3. Subscription plan downgraded
        4. Service outage in region

        **Resolution Steps:**
        1. Check camera status:
           - Admin > Devices > [Customer Cameras]
           - Verify all cameras show "Online"
           - If offline: Restart cameras, check Wi-Fi

        2. Check storage quota:
           - Admin > Account > Storage
           - If exceeded: Upgrade plan or delete old recordings

        3. Verify subscription tier:
           - Confirm 10-camera plan is active
           - Check if recent downgrade occurred
           - Restore proper tier if needed

        4. Check service status:
           - Status page: status.yourservice.com
           - If outage: Provide ETA to customer

        5. Force recording refresh:
           - Admin > Recordings > Rebuild Index
           - Wait 10 minutes
           - Have customer refresh app

        **Resolution Time:** 10-15 minutes
        **Escalation:** If cameras online and storage OK, escalate to engineering
        """,
        "category": "recordings",
        "keywords": ["no recordings", "can't see recordings", "recordings missing", "camera subscription"]
    },
    {
        "title": "Multi-Camera Subscription Troubleshooting",
        "content": """
        **Issue:** Problems specific to multi-camera subscriptions (5+ cameras)

        **Common Issues:**
        1. Only some cameras recording
        2. Recordings delayed or intermittent
        3. Subscription shows wrong camera count

        **Resolution Steps:**
        1. Verify camera allocation:
           - Admin > Subscriptions > Camera Slots
           - Ensure all 10 cameras are assigned
           - Check for duplicate assignments

        2. Check individual camera settings:
           - Each camera must have unique device ID
           - Verify recording is enabled per camera
           - Check motion detection sensitivity

        3. Bandwidth check:
           - Multi-camera setups need good upload speed
           - Minimum: 2 Mbps per camera
           - Test: Admin > Diagnostics > Bandwidth Test

        4. Storage distribution:
           - Verify storage is allocated evenly
           - Check if one camera is using all quota
           - Rebalance if needed

        **Pro Tips:**
        - Long-term customers (years) may have legacy plan
        - Check if migration to new plan needed
        - Offer plan upgrade if near camera limit

        **Resolution Time:** 15-20 minutes
        """,
        "category": "multi-camera",
        "keywords": ["10 cameras", "multiple cameras", "camera limit", "subscription"]
    },
    {
        "title": "Recent Subscription Issues - Known Problem",
        "content": """
        **Issue:** Widespread subscription display issues reported last week

        **Affected:** Customers who renewed or had billing updates 7-14 days ago

        **Root Cause:** Database migration caused sync issues between billing and service systems

        **Status:** RESOLVED as of [current date]

        **Resolution for Affected Customers:**
        1. This is a KNOWN ISSUE - not customer's fault
        2. Apologize for inconvenience
        3. Fast resolution available:

        **Fix Steps:**
        1. Admin > Tools > Subscription Repair
        2. Enter customer email/ID
        3. Click "Repair Subscription Link"
        4. System will:
           - Re-link billing to service account
           - Restore recording access
           - Rebuild recording index
        5. Takes 2-3 minutes
        6. Have customer log out/in

        **Follow-up:**
        - Offer 1 week free service extension as apology
        - Document case for engineering team
        - Send follow-up email in 24 hours

        **If repair fails:**
        - Escalate immediately to Tier 2
        - Include: Customer ID, subscription ID, repair attempt log

        **Resolution Time:** 5 minutes
        **Customer Compensation:** 1 week free
        """,
        "category": "known-issues",
        "keywords": ["last week", "subscription stopped", "recent issue", "known problem"]
    },
    {
        "title": "Mobile App vs Web Link Sync Issues",
        "content": """
        **Issue:** Customer reports issue on "both mobile app and web link"

        **This indicates:** Account-level problem, not device-specific

        **Common Causes:**
        1. Session token expired
        2. Account locked/suspended
        3. Subscription not synced at account level

        **Quick Check:**
        - Admin > Account > [Customer Email]
        - Look for red flags:
           - "Subscription Sync Error"
           - "Payment Failed"
           - "Account Suspended"

        **Resolution:**
        1. Clear all sessions:
           - Admin > Account > Active Sessions > "Clear All"

        2. Force re-authentication:
           - Have customer log out everywhere
           - Wait 2 minutes
           - Log in with password (not saved session)

        3. Verify account status:
           - Ensure "Active" status
           - Check for holds or restrictions

        4. Re-sync subscription:
           - Admin > Subscriptions > Force Sync

        **Prevention:**
        - Advise customer to update app to latest version
        - Check if using VPN (can cause issues)

        **Resolution Time:** 5-10 minutes
        """,
        "category": "cross-platform",
        "keywords": ["mobile app", "web link", "both platforms", "sync"]
    }
]


async def load_knowledge_base():
    """Load camera support articles into vector database"""
    print("="*80)
    print("LOADING CAMERA SUPPORT KNOWLEDGE BASE")
    print("="*80)
    print()

    chunks_to_embed = []

    for i, article in enumerate(CAMERA_KNOWLEDGE_BASE):
        print(f"[{i+1}/{len(CAMERA_KNOWLEDGE_BASE)}] Processing: {article['title']}")

        # Create text chunk
        chunk = TextChunk(
            text=f"Title: {article['title']}\n\n{article['content']}",
            source=f"kb_article_{i+1}",
            page_number=1,
            file_type="knowledge_base",
            timestamp=datetime.utcnow(),
            metadata={
                "title": article['title'],
                "category": article['category'],
                "keywords": article['keywords']
            }
        )

        chunks_to_embed.append(chunk)

    print()
    print(f"✓ Created {len(chunks_to_embed)} text chunks")
    print()

    # Embed chunks
    print("Generating embeddings with OpenAI...")
    embedded_chunks = []

    for chunk in chunks_to_embed:
        # Get embedding
        embedding = await asyncio.to_thread(embedder.embed_text, chunk.text)

        # Create embedded chunk
        embedded_chunk = EmbeddedChunk(
            text=chunk.text,
            embedding=embedding,
            source=chunk.source,
            page_number=chunk.page_number,
            file_type=chunk.file_type,
            timestamp=chunk.timestamp,
            metadata=chunk.metadata
        )

        embedded_chunks.append(embedded_chunk)

    print(f"✓ Generated {len(embedded_chunks)} embeddings")
    print()

    # Store in Qdrant
    print("Storing in Qdrant vector database...")
    vector_store.upsert(embedded_chunks)

    print("✓ Knowledge base loaded successfully!")
    print()
    print("="*80)
    print("KNOWLEDGE BASE SUMMARY")
    print("="*80)
    print(f"Total articles: {len(CAMERA_KNOWLEDGE_BASE)}")
    print()
    print("Categories:")
    categories = {}
    for article in CAMERA_KNOWLEDGE_BASE:
        cat = article['category']
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in categories.items():
        print(f"  - {cat}: {count} articles")

    print()
    print("✅ Ready to answer customer questions!")
    print()
    print("Try running: python test_camera_scenario.py")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(load_knowledge_base())
