"""
Migration script to add Messaging Services to existing WhatsApp accounts.

This script should be run AFTER the Phase 5 database migration has been applied.
It will:
1. Find all WhatsApp accounts without a messaging_service_sid
2. Create a Messaging Service for each subaccount
3. Update the account record with the messaging_service_sid
4. Update all phone numbers to use the Messaging Service

Usage:
    python -m backend.scripts.migrate_existing_accounts_to_messaging_services
"""

import os
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.whatsapp_account import WhatsAppAccount, AccountStatus
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.service.twilio.tech_provider import TwilioTechProviderService
from cryptography.fernet import Fernet
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Encryption for decrypting stored tokens
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable must be set")

cipher_suite = Fernet(ENCRYPTION_KEY)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token"""
    return cipher_suite.decrypt(encrypted_token.encode()).decode()


async def migrate_account(db: Session, account: WhatsAppAccount, twilio_service: TwilioTechProviderService) -> bool:
    """
    Migrate a single account to use Messaging Services.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Processing account {account.code} (org: {account.organization.name})")
        
        # Decrypt auth token
        auth_token = decrypt_token(account.twilio_auth_token)
        
        # Create Messaging Service
        logger.info(f"Creating Messaging Service for subaccount {account.twilio_subaccount_sid}")
        messaging_service = await twilio_service.create_messaging_service(
            subaccount_sid=account.twilio_subaccount_sid,
            subaccount_token=auth_token,
            friendly_name=f"{account.organization.name} WhatsApp Service"
        )
        
        messaging_service_sid = messaging_service["messaging_service_sid"]
        logger.info(f"Created Messaging Service: {messaging_service_sid}")
        
        # Update account
        account.messaging_service_sid = messaging_service_sid
        
        # Update all phone numbers for this account
        phone_numbers = db.query(WhatsAppPhoneNumber).filter(
            WhatsAppPhoneNumber.whatsapp_account_id == account.id
        ).all()
        
        for phone in phone_numbers:
            logger.info(f"Updating phone number {phone.phone_number} to use Messaging Service")
            phone.messaging_service_sid = messaging_service_sid
        
        db.commit()
        logger.info(f"✅ Successfully migrated account {account.code}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate account {account.code}: {str(e)}")
        db.rollback()
        return False


async def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("Starting Messaging Service Migration for Existing Accounts")
    logger.info("=" * 80)
    
    db = SessionLocal()
    twilio_service = TwilioTechProviderService()
    
    try:
        # Find all accounts without messaging_service_sid
        accounts_to_migrate = db.query(WhatsAppAccount).filter(
            WhatsAppAccount.messaging_service_sid.is_(None),
            WhatsAppAccount.status.in_([AccountStatus.ACTIVE, AccountStatus.PENDING])
        ).all()
        
        if not accounts_to_migrate:
            logger.info("✅ No accounts need migration. All accounts already have Messaging Services.")
            return
        
        logger.info(f"Found {len(accounts_to_migrate)} accounts to migrate")
        logger.info("-" * 80)
        
        success_count = 0
        failure_count = 0
        
        for account in accounts_to_migrate:
            success = await migrate_account(db, account, twilio_service)
            if success:
                success_count += 1
            else:
                failure_count += 1
            logger.info("-" * 80)
        
        # Summary
        logger.info("=" * 80)
        logger.info("Migration Summary")
        logger.info("=" * 80)
        logger.info(f"Total accounts processed: {len(accounts_to_migrate)}")
        logger.info(f"✅ Successful migrations: {success_count}")
        logger.info(f"❌ Failed migrations: {failure_count}")
        
        if failure_count > 0:
            logger.warning("Some accounts failed to migrate. Please review the errors above.")
            logger.warning("You may need to manually create Messaging Services for failed accounts.")
        else:
            logger.info("🎉 All accounts successfully migrated!")
        
    except Exception as e:
        logger.error(f"Migration script failed: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
