#!/usr/bin/env python3
"""
Setup Test Integration

Creates a test integration configuration in the database for testing webhooks.

Usage:
    python scripts/setup_test_integration.py
    python scripts/setup_test_integration.py --company-id 1 --provider aircall
"""
import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.postgresql_session import get_db_session
from app.models.integration_config import (
    IntegrationConfig,
    IntegrationType,
    IntegrationProvider,
    IntegrationStatus,
)
from app.models.company import Company


def get_or_create_test_company(db) -> Company:
    """Get existing company or create a test one."""
    company = db.query(Company).first()

    if company:
        print(f"Using existing company: {company.name} (ID: {company.id})")
        return company

    # Create test company
    company = Company(
        name="Test Company",
        slug="test-company",
        is_active=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    print(f"Created test company: {company.name} (ID: {company.id})")
    return company


def setup_integration(
    company_id: int = None,
    provider: str = "generic",
    integration_id: str = "test-integration",
    webhook_secret: str = "test-secret-123",
):
    """Create or update a test integration configuration."""

    print("\n" + "="*60)
    print("SETTING UP TEST INTEGRATION")
    print("="*60)

    with get_db_session() as db:
        # Get or create company
        if company_id:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                print(f"Error: Company with ID {company_id} not found")
                return None
        else:
            company = get_or_create_test_company(db)
            company_id = company.id

        # Check if integration already exists
        existing = db.query(IntegrationConfig).filter(
            IntegrationConfig.company_id == company_id,
            IntegrationConfig.integration_id == integration_id,
        ).first()

        if existing:
            print(f"\nIntegration already exists: {existing.name}")
            print(f"  ID: {existing.id}")
            print(f"  Integration ID: {existing.integration_id}")
            print(f"  Provider: {existing.provider.value}")
            print(f"  Active: {existing.is_active}")

            # Update webhook secret if different
            if existing.webhook_secret != webhook_secret:
                existing.webhook_secret = webhook_secret
                db.commit()
                print(f"  Updated webhook secret")

            return existing

        # Map provider string to enum
        try:
            provider_enum = IntegrationProvider(provider)
        except ValueError:
            print(f"Error: Invalid provider '{provider}'")
            print(f"Valid providers: {[p.value for p in IntegrationProvider]}")
            return None

        # Determine integration type
        cloud_providers = ['aircall', 'genesys_cloud', 'talkdesk', 'ringover', 'five9', 'twilio_flex', 'generic']
        if provider in cloud_providers:
            int_type = IntegrationType.CLOUD_WEBHOOK
        else:
            int_type = IntegrationType.SIPREC

        # Create integration
        integration = IntegrationConfig(
            company_id=company_id,
            integration_id=integration_id,
            name=f"Test {provider.title()} Integration",
            description="Test integration for webhook testing",
            integration_type=int_type,
            provider=provider_enum,
            is_active=True,
            is_primary=True,
            webhook_secret=webhook_secret,
            transcription_source="provider_asr",
            health_status=IntegrationStatus.UNKNOWN,
            settings={
                "test_mode": True,
                "auto_create_sessions": True,
            },
        )

        db.add(integration)
        db.commit()
        db.refresh(integration)

        print(f"\nCreated integration: {integration.name}")
        print(f"  ID: {integration.id}")
        print(f"  Integration ID: {integration.integration_id}")
        print(f"  Company ID: {integration.company_id}")
        print(f"  Provider: {integration.provider.value}")
        print(f"  Type: {integration.integration_type.value}")
        print(f"  Webhook Secret: {integration.webhook_secret}")

        # Generate webhook URL
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        webhook_url = f"{base_url}/api/v1/integrations/{provider}/webhook/{integration_id}"
        print(f"\n  Webhook URL: {webhook_url}")

        return integration


def list_integrations():
    """List all existing integrations."""
    print("\n" + "="*60)
    print("EXISTING INTEGRATIONS")
    print("="*60)

    with get_db_session() as db:
        integrations = db.query(IntegrationConfig).all()

        if not integrations:
            print("\nNo integrations found.")
            return

        for i in integrations:
            status = "✓" if i.is_active else "✗"
            print(f"\n{status} [{i.id}] {i.name}")
            print(f"    Integration ID: {i.integration_id}")
            print(f"    Company ID: {i.company_id}")
            print(f"    Provider: {i.provider.value}")
            print(f"    Type: {i.integration_type.value}")
            print(f"    Events received: {i.total_events_received}")
            print(f"    Calls processed: {i.total_calls_processed}")


def delete_integration(integration_id: str, company_id: int = None):
    """Delete an integration by integration_id."""
    with get_db_session() as db:
        query = db.query(IntegrationConfig).filter(
            IntegrationConfig.integration_id == integration_id
        )
        if company_id:
            query = query.filter(IntegrationConfig.company_id == company_id)

        integration = query.first()
        if not integration:
            print(f"Integration '{integration_id}' not found")
            return False

        db.delete(integration)
        db.commit()
        print(f"Deleted integration: {integration_id}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Setup test integration for webhook testing")
    parser.add_argument("--company-id", type=int, help="Company ID to use")
    parser.add_argument("--provider", default="generic",
                        choices=["aircall", "genesys_cloud", "talkdesk", "generic"],
                        help="Provider type")
    parser.add_argument("--integration-id", default="test-integration",
                        help="Integration identifier")
    parser.add_argument("--secret", default="test-secret-123",
                        help="Webhook secret for signature verification")
    parser.add_argument("--list", action="store_true",
                        help="List all existing integrations")
    parser.add_argument("--delete", action="store_true",
                        help="Delete the specified integration")

    args = parser.parse_args()

    if args.list:
        list_integrations()
        return

    if args.delete:
        delete_integration(args.integration_id, args.company_id)
        return

    integration = setup_integration(
        company_id=args.company_id,
        provider=args.provider,
        integration_id=args.integration_id,
        webhook_secret=args.secret,
    )

    if integration:
        print("\n" + "="*60)
        print("SETUP COMPLETE")
        print("="*60)
        print("\nYou can now test webhooks with:")
        print(f"  python scripts/test_integration_webhooks.py --provider {args.provider}")
        print(f"\nOr with signature verification:")
        print(f"  python scripts/test_integration_webhooks.py --provider {args.provider} --secret {args.secret}")


if __name__ == "__main__":
    main()
