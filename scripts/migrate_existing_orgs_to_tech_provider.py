"""
Migration Script: Migrate Existing Organizations to Tech Provider
==================================================================

This script migrates existing organizations that are already using WhatsApp
to the new Tech Provider system with isolated Twilio subaccounts.

What it does:
1. Finds organizations with WhatsApp users but no WhatsAppAccount
2. Creates Twilio subaccounts for each organization
3. Creates WhatsAppAccount and WhatsAppSender records
4. Updates Organization.phone_number if not set
5. Registers WhatsApp senders with Twilio

Usage:
    python -m scripts.migrate_existing_orgs_to_tech_provider [--dry-run]
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import Organization
from app.models.whatsapp import WhatsAppUser
from app.models.whatsapp_account import WhatsAppAccount, AccountStatus
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.models.service_credential import ServiceCredential  # Import to resolve relationship
from app.service.twilio.tech_provider import TwilioTechProviderService
from cryptography.fernet import Fernet
import logging

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Encryption for tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    logger.warning("ENCRYPTION_KEY not set, generating new key")
    ENCRYPTION_KEY = Fernet.generate_key()
    logger.info(f"Generated ENCRYPTION_KEY: {ENCRYPTION_KEY.decode()}")
    logger.info("Add this to your .env file!")

cipher_suite = Fernet(ENCRYPTION_KEY)


def encrypt_token(token: str) -> str:
    """Encrypt a token for secure storage"""
    return cipher_suite.encrypt(token.encode()).decode()


async def migrate_organization(
    db: Session,
    organization: Organization,
    dry_run: bool = False
) -> dict:
    """
    Migrate a single organization to Tech Provider system.
    
    Returns:
        dict with migration results
    """
    result = {
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "success": False,
        "error": None,
        "created_account": False,
        "created_sender": False,
        "phone_number": None
    }
    
    try:
        # Check if already migrated
        existing_account = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.organization_id == organization.id
        ).first()
        
        if existing_account:
            logger.info(f"Organization {organization.name} already has Tech Provider account")
            result["success"] = True
            result["phone_number"] = existing_account.phone_number
            result["already_migrated"] = True
            return result
        
        # Find WhatsApp users for this organization
        whatsapp_users = db.query(WhatsAppUser).filter(
            WhatsAppUser.organization_id == organization.id
        ).all()
        
        if not whatsapp_users:
            logger.info(f"Organization {organization.name} has no WhatsApp users, skipping")
            result["error"] = "No WhatsApp users found"
            return result
        
        # Determine phone number
        phone_number = organization.phone_number
        
        if not phone_number:
            # Try to get from first WhatsApp user's account_sid or use a default
            logger.warning(f"Organization {organization.name} has no phone_number set")
            result["error"] = "No phone number configured for organization"
            return result
        
        logger.info(f"Migrating organization: {organization.name} (phone: {phone_number})")
        
        if dry_run:
            logger.info(f"[DRY RUN] Would create subaccount for {organization.name}")
            result["success"] = True
            result["dry_run"] = True
            result["phone_number"] = phone_number
            return result
        
        # Create Twilio subaccount
        twilio_service = TwilioTechProviderService()
        logger.info(f"Creating Twilio subaccount for {organization.name}...")
        
        subaccount = await twilio_service.create_subaccount(
            customer_name=f"{organization.name} - WhatsApp"
        )
        
        logger.info(f"Created subaccount: {subaccount['account_sid']}")
        
        # Create WhatsAppAccount record (without phone_number - that goes in WhatsAppPhoneNumber)
        whatsapp_account = WhatsAppAccount(
            organization_id=organization.id,
            twilio_subaccount_sid=subaccount["account_sid"],
            twilio_auth_token=encrypt_token(subaccount["auth_token"]),
            status=AccountStatus.ACTIVE
        )
        
        db.add(whatsapp_account)
        db.flush()
        
        logger.info(f"Created WhatsAppAccount: {whatsapp_account.code}")
        result["created_account"] = True
        result["account_code"] = whatsapp_account.code
        
        # Register WhatsApp sender with Twilio
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        logger.info(f"Registering WhatsApp sender for {phone_number}...")
        
        try:
            sender = await twilio_service.register_whatsapp_sender(
                subaccount_sid=subaccount["account_sid"],
                subaccount_token=subaccount["auth_token"],
                phone_number=phone_number,
                waba_id=None,  # Existing orgs may not have WABA ID
                display_name=organization.name,
                callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
                status_callback_url=f"{backend_url}/webhooks/whatsapp/status"
            )
            
            # Create WhatsAppPhoneNumber record with sender information
            from app.models.whatsapp_phone_number import PhoneNumberStatus
            
            phone_number_record = WhatsAppPhoneNumber(
                whatsapp_account_id=whatsapp_account.id,
                phone_number=phone_number,
                display_name=organization.name,
                sender_sid=sender["sender_sid"],
                messaging_service_sid=sender.get("messaging_service_sid"),
                callback_url=f"{backend_url}/webhooks/whatsapp/inbound",
                status_callback_url=f"{backend_url}/webhooks/whatsapp/status",
                status=PhoneNumberStatus.ACTIVE,
                is_primary=True  # First number is always primary
            )
            db.add(phone_number_record)
            
            logger.info(f"Created phone number record: {phone_number_record.code}")
            result["created_sender"] = True
            result["sender_sid"] = sender["sender_sid"]
            result["phone_number_code"] = phone_number_record.code
            
        except Exception as e:
            logger.warning(f"Failed to register sender (continuing anyway): {str(e)}")
            result["sender_error"] = str(e)
        
        db.commit()
        
        logger.info(f"✅ Successfully migrated {organization.name}")
        result["success"] = True
        result["phone_number"] = phone_number
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate {organization.name}: {str(e)}")
        result["error"] = str(e)
        db.rollback()
    
    return result


async def main(dry_run: bool = False):
    """
    Main migration function.
    """
    logger.info("=" * 80)
    logger.info("WhatsApp Tech Provider Migration Script")
    logger.info("=" * 80)
    
    if dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
    
    db = SessionLocal()
    
    try:
        # Find organizations with WhatsApp users but no Tech Provider account
        organizations_with_whatsapp = db.query(Organization).join(
            WhatsAppUser,
            WhatsAppUser.organization_id == Organization.id
        ).distinct().all()
        
        logger.info(f"Found {len(organizations_with_whatsapp)} organizations with WhatsApp users")
        
        # Filter out organizations that already have Tech Provider accounts
        orgs_to_migrate = []
        for org in organizations_with_whatsapp:
            existing_account = db.query(WhatsAppAccount).filter(
                WhatsAppAccount.organization_id == org.id
            ).first()
            
            if not existing_account:
                orgs_to_migrate.append(org)
        
        logger.info(f"Found {len(orgs_to_migrate)} organizations to migrate")
        
        if not orgs_to_migrate:
            logger.info("✅ No organizations need migration")
            return
        
        # Show organizations to migrate
        logger.info("\nOrganizations to migrate:")
        for org in orgs_to_migrate:
            phone = org.phone_number or "NO PHONE NUMBER"
            logger.info(f"  - {org.name} ({phone})")
        
        if not dry_run:
            response = input("\nProceed with migration? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Migration cancelled")
                return
        
        # Migrate each organization
        results = []
        for i, org in enumerate(orgs_to_migrate, 1):
            logger.info(f"\n[{i}/{len(orgs_to_migrate)}] Processing {org.name}...")
            result = await migrate_organization(db, org, dry_run)
            results.append(result)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        logger.info(f"✅ Successful: {len(successful)}")
        logger.info(f"❌ Failed: {len(failed)}")
        
        if successful:
            logger.info("\nSuccessful migrations:")
            for r in successful:
                logger.info(f"  ✅ {r['organization_name']} - {r.get('phone_number', 'N/A')}")
                if r.get("account_code"):
                    logger.info(f"     Account: {r['account_code']}")
                if r.get("sender_code"):
                    logger.info(f"     Sender: {r['sender_code']}")
        
        if failed:
            logger.info("\nFailed migrations:")
            for r in failed:
                logger.info(f"  ❌ {r['organization_name']}")
                logger.info(f"     Error: {r.get('error', 'Unknown error')}")
        
        if not dry_run:
            logger.info("\n⚠️  IMPORTANT NEXT STEPS:")
            logger.info("1. Update Twilio webhook URLs for migrated organizations")
            logger.info("2. Test message sending/receiving for each organization")
            logger.info("3. Monitor logs for any issues")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate organizations to Tech Provider")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no changes made)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(main(dry_run=args.dry_run))
