#!/usr/bin/env python3
"""
Create Super Admin User Script

Creates a platform-level SUPER_ADMIN user for Apertool administration.
This user has global access across all companies.

Usage:
    python scripts/create_super_admin.py

Environment variables (optional):
    SUPER_ADMIN_EMAIL - Super admin email (default: super@apertool.com)
    SUPER_ADMIN_PASSWORD - Super admin password (default: changeme123)
    SUPER_ADMIN_NAME - Super admin full name (default: Apertool Admin)
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.postgresql_session import get_db_session
from app.models.user import User, UserRole
from app.services.auth_service import get_auth_service


def create_super_admin():
    """Create a SUPER_ADMIN user if one doesn't exist."""

    email = os.getenv('SUPER_ADMIN_EMAIL', 'super@apertool.com')
    password = os.getenv('SUPER_ADMIN_PASSWORD', 'changeme123')
    full_name = os.getenv('SUPER_ADMIN_NAME', 'Apertool Admin')

    print(f"Creating SUPER_ADMIN user...")
    print(f"  Email: {email}")
    print(f"  Name: {full_name}")

    auth_service = get_auth_service()

    with get_db_session() as db:
        # Check if super admin already exists
        existing = db.query(User).filter(User.email == email.lower()).first()

        if existing:
            if existing.role == UserRole.SUPER_ADMIN:
                print(f"\n✓ SUPER_ADMIN user already exists: {email}")
                return existing
            else:
                print(f"\n⚠ User exists but is not SUPER_ADMIN. Updating role...")
                existing.role = UserRole.SUPER_ADMIN
                existing.company_id = None  # Super admins have no company
                db.commit()
                print(f"✓ User updated to SUPER_ADMIN")
                return existing

        # Check if any super admin exists
        any_super = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if any_super:
            print(f"\n⚠ A SUPER_ADMIN already exists: {any_super.email}")
            print("   Creating additional SUPER_ADMIN...")

        # Create new super admin
        try:
            user = User(
                email=email.lower(),
                password_hash=auth_service.hash_password(password),
                full_name=full_name,
                role=UserRole.SUPER_ADMIN,
                company_id=None,  # Super admins have no company
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            print(f"\n✓ SUPER_ADMIN user created successfully!")
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Role: {user.role.value}")
            print(f"\n⚠ IMPORTANT: Change the default password immediately!")
            print(f"  Login at: http://localhost:8000/login")

            return user

        except Exception as e:
            db.rollback()
            print(f"\n✗ Error creating SUPER_ADMIN: {e}")
            raise


if __name__ == '__main__':
    create_super_admin()
