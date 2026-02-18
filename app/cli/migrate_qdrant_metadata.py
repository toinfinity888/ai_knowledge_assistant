"""
Qdrant Metadata Migration Script

Updates existing Qdrant points to include proper metadata fields for source provenance.
Run this script once to fix documents that were uploaded without proper metadata.

Usage:
    python -m app.cli.migrate_qdrant_metadata
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from tqdm import tqdm

load_dotenv()

QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = os.getenv('QDRANT_PORT')
COLLECTION = "mvp_support"  # Main collection for MVP
COMPANY_ID = 1  # Default company for existing documents
BATCH_SIZE = 100


def migrate_metadata():
    """Update existing Qdrant points with proper metadata fields."""

    # Connect to Qdrant
    client = QdrantClient(
        url=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY
    )

    if not client.collection_exists(COLLECTION):
        print(f"Collection '{COLLECTION}' does not exist.")
        return

    # Get collection info
    collection_info = client.get_collection(COLLECTION)
    total_points = collection_info.points_count
    print(f"Found {total_points} points in collection '{COLLECTION}'")

    if total_points == 0:
        print("No points to migrate.")
        return

    # Scroll through all points and update metadata
    offset = None
    updated_count = 0

    with tqdm(total=total_points, desc="Migrating metadata") as pbar:
        while True:
            # Scroll through points
            result = client.scroll(
                collection_name=COLLECTION,
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = result

            if not points:
                break

            # Update each point's payload
            for point in points:
                payload = point.payload or {}

                # Check if already has proper metadata (not default values)
                has_good_file_name = payload.get("file_name") and payload.get("file_name") != "Untitled Document"
                has_company_id = payload.get("company_id") is not None
                has_good_source = payload.get("source") and payload.get("source") not in ["arxiv", ""]

                if has_good_file_name and has_company_id and has_good_source:
                    pbar.update(1)
                    continue

                # Build updated payload
                updated_payload = dict(payload)

                # Add file_name from various possible fields
                if not updated_payload.get("file_name") or updated_payload.get("file_name") == "Untitled Document":
                    # Try different fields in order of preference
                    file_name = (
                        payload.get("title") or
                        payload.get("section") or
                        payload.get("url", "").split("/")[-1] or
                        "Document"
                    )
                    # Truncate long file names
                    if len(file_name) > 100:
                        file_name = file_name[:97] + "..."
                    updated_payload["file_name"] = file_name

                # Add text from various content fields if missing
                if not updated_payload.get("text"):
                    updated_payload["text"] = (
                        payload.get("abstract") or
                        payload.get("content") or
                        payload.get("subsection") or
                        ""
                    )

                # Add chunk_id if missing
                if not updated_payload.get("chunk_id"):
                    updated_payload["chunk_id"] = str(point.id)

                # Add source from url if available
                if not updated_payload.get("source") or updated_payload.get("source") == "arxiv":
                    url = payload.get("url", "")
                    if url:
                        # Extract domain from URL
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(url).netloc
                            updated_payload["source"] = domain or "knowledge_base"
                        except:
                            updated_payload["source"] = "knowledge_base"
                    else:
                        updated_payload["source"] = "knowledge_base"

                # Add company_id if missing
                if updated_payload.get("company_id") is None:
                    updated_payload["company_id"] = COMPANY_ID

                # Update the point's payload
                client.set_payload(
                    collection_name=COLLECTION,
                    payload=updated_payload,
                    points=[point.id],
                )

                updated_count += 1
                pbar.update(1)

            offset = next_offset

            if offset is None:
                break

    print(f"\nMigration complete. Updated {updated_count} points.")


if __name__ == "__main__":
    print("Starting Qdrant metadata migration...")
    migrate_metadata()
