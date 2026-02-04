#!/usr/bin/env python3
"""
Data Migration Script for Multi-Tenancy

This script:
1. Creates a default company for existing data
2. Creates an admin user for the default company
3. Updates existing call_sessions with the default company_id
4. Updates existing query_logs with the default company_id
5. Updates Qdrant vectors with company_id metadata
6. Creates the company_id index on Qdrant collection

Run this AFTER running the Alembic migrations:
    alembic upgrade head
    python scripts/migrate_to_multitenancy.py

Environment variables required:
    DATABASE_URL - PostgreSQL connection string
    ADMIN_EMAIL - Email for the default admin user (optional)
    ADMIN_PASSWORD - Password for the default admin user (optional)
"""
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.database.postgresql_session import get_db_session
from app.models.company import Company
from app.models.user import User, UserRole
from app.services.auth_service import get_auth_service


def create_default_company(db):
    """Create the default company for existing data"""
    print("Creating default company...")

    # Check if default company already exists
    existing = db.query(Company).filter(Company.slug == 'default').first()
    if existing:
        print(f"  Default company already exists (id: {existing.id})")
        return existing

    company = Company(
        slug='default',
        name='Default Company',
        plan='enterprise',
        is_active=True,
        settings={
            'migrated_from_single_tenant': True,
            'migration_date': datetime.now(timezone.utc).isoformat(),
        }
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    print(f"  Created default company (id: {company.id})")
    return company


def create_admin_user(db, company):
    """Create an admin user for the default company"""
    print("Creating admin user...")

    # Get admin credentials from environment
    admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.getenv('ADMIN_PASSWORD', 'changeme123')

    # Check if admin user already exists
    existing = db.query(User).filter(User.email == admin_email).first()
    if existing:
        print(f"  Admin user already exists: {admin_email}")
        return existing

    auth_service = get_auth_service()

    try:
        user = auth_service.create_user(
            email=admin_email,
            password=admin_password,
            full_name='System Administrator',
            company_id=company.id,
            role=UserRole.ADMIN,
            db=db
        )
        print(f"  Created admin user: {admin_email}")
        print(f"  IMPORTANT: Change the password after first login!")
        return user
    except ValueError as e:
        print(f"  Error creating admin user: {e}")
        return None


def update_call_sessions(db, company_id):
    """Update existing call_sessions with company_id"""
    print("Updating call_sessions with company_id...")

    result = db.execute(
        text("""
            UPDATE call_sessions
            SET company_id = :company_id
            WHERE company_id IS NULL
        """),
        {'company_id': company_id}
    )
    db.commit()

    print(f"  Updated {result.rowcount} call_sessions")


def update_query_logs(db, company_id):
    """Update existing query_logs with company_id"""
    print("Updating query_logs with company_id...")

    result = db.execute(
        text("""
            UPDATE query_logs
            SET company_id = :company_id
            WHERE company_id IS NULL
        """),
        {'company_id': company_id}
    )
    db.commit()

    print(f"  Updated {result.rowcount} query_logs")


def make_call_sessions_company_id_required(db):
    """Make company_id NOT NULL on call_sessions after data migration"""
    print("Making company_id NOT NULL on call_sessions...")

    try:
        db.execute(
            text("""
                ALTER TABLE call_sessions
                ALTER COLUMN company_id SET NOT NULL
            """)
        )
        db.commit()
        print("  company_id is now required on call_sessions")
    except Exception as e:
        print(f"  Warning: Could not alter column (may already be NOT NULL): {e}")
        db.rollback()


def update_qdrant_vectors(company_id):
    """Update Qdrant vectors with company_id metadata"""
    print("Updating Qdrant vectors with company_id...")

    try:
        from app.config.qdrant_config import QdrantSetting
        from qdrant_client import QdrantClient
        from qdrant_client.models import PayloadSchemaType

        settings = QdrantSetting()

        # Build URL
        if settings.https:
            url = f"https://{settings.host}:{settings.port}"
        else:
            url = f"http://{settings.host}:{settings.port}"

        client = QdrantClient(url=url, api_key=settings.api_key)

        collection_name = settings.collection_name

        # Check if collection exists
        if not client.collection_exists(collection_name):
            print(f"  Qdrant collection '{collection_name}' does not exist, skipping")
            return

        # Create company_id index for efficient filtering
        print(f"  Creating company_id index on {collection_name}...")
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="company_id",
                field_schema=PayloadSchemaType.INTEGER
            )
            print("  Index created successfully")
        except Exception as e:
            print(f"  Index may already exist: {e}")

        # Update all vectors with default company_id
        # Note: This updates all vectors that don't have company_id set
        print(f"  Updating vectors in {collection_name} with company_id={company_id}...")

        # Get all points from collection
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        points_to_update = []
        total_updated = 0

        while scroll_result[0]:
            for point in scroll_result[0]:
                # Only update if company_id is not set
                if point.payload.get('company_id') is None:
                    points_to_update.append(point.id)

            # Update batch
            if points_to_update:
                client.set_payload(
                    collection_name=collection_name,
                    payload={"company_id": company_id},
                    points=points_to_update,
                )
                total_updated += len(points_to_update)
                points_to_update = []

            # Get next batch
            if scroll_result[1] is None:
                break

            scroll_result = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=scroll_result[1],
                with_payload=True,
                with_vectors=False,
            )

        print(f"  Updated {total_updated} vectors with company_id")

    except ImportError:
        print("  Qdrant client not available, skipping vector update")
    except Exception as e:
        print(f"  Error updating Qdrant: {e}")


def main():
    print("=" * 60)
    print("Multi-Tenancy Data Migration")
    print("=" * 60)
    print()

    # Verify database connection
    print("Checking database connection...")
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"  Database: {database_url.split('@')[1] if '@' in database_url else 'local'}")
    print()

    with get_db_session() as db:
        # Step 1: Create default company
        company = create_default_company(db)
        company_id = company.id  # Store id before session closes
        print()

        # Step 2: Create admin user
        create_admin_user(db, company)
        print()

        # Step 3: Update call_sessions
        update_call_sessions(db, company_id)
        print()

        # Step 4: Update query_logs
        update_query_logs(db, company_id)
        print()

        # Step 5: Make company_id required on call_sessions
        make_call_sessions_company_id_required(db)
        print()

    # Step 6: Update Qdrant vectors (outside DB session)
    update_qdrant_vectors(company_id)
    print()

    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Update .env with JWT_SECRET_KEY (generate a secure random string)")
    print("2. Restart the application")
    print("3. Log in with the admin credentials:")
    print(f"   Email: {os.getenv('ADMIN_EMAIL', 'admin@example.com')}")
    print(f"   Password: {os.getenv('ADMIN_PASSWORD', 'changeme123')}")
    print("4. Change the admin password immediately after first login")
    print()


if __name__ == '__main__':
    main()
