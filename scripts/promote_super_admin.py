#!/usr/bin/env python3
"""
Promote a user to super_admin role.
Usage: python scripts/promote_super_admin.py <email>
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgresql_session import get_db_session
from app.models.user import User, UserRole


def promote_to_super_admin(email: str):
    with get_db_session() as db:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            print(f"User with email '{email}' not found.")
            print("\nExisting users:")
            users = db.query(User).all()
            for u in users:
                print(f"  - {u.email} (role: {u.role.value})")
            return False

        old_role = user.role.value
        user.role = UserRole.SUPER_ADMIN
        user.company_id = None  # Super admin has global access
        db.commit()

        print(f"Successfully promoted user:")
        print(f"  Email: {user.email}")
        print(f"  Old role: {old_role}")
        print(f"  New role: super_admin")
        print(f"\nYou can now login and access /admin/system-config")
        return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/promote_super_admin.py <email>")
        print("\nTo see all users, run without email argument and it will list them.")

        # List users anyway
        with get_db_session() as db:
            users = db.query(User).all()
            if users:
                print("\nExisting users:")
                for u in users:
                    print(f"  - {u.email} (role: {u.role.value})")
        sys.exit(1)

    email = sys.argv[1]
    promote_to_super_admin(email)
