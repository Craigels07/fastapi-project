"""
Check Migration Status - Quick script to see which organizations need migration
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
from app.database import SessionLocal
from app.models.user import Organization
from app.models.whatsapp import WhatsAppUser
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.models.service_credential import ServiceCredential  # Import to resolve relationship

load_dotenv()


def main():
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("WhatsApp Tech Provider Migration Status")
        print("=" * 80)
        
        # Get all organizations
        all_orgs = db.query(Organization).all()
        print(f"\nTotal organizations: {len(all_orgs)}")
        
        # Organizations with WhatsApp users
        orgs_with_whatsapp = db.query(Organization).join(
            WhatsAppUser,
            WhatsAppUser.organization_id == Organization.id
        ).distinct().all()
        
        print(f"Organizations with WhatsApp users: {len(orgs_with_whatsapp)}")
        
        # Organizations with Tech Provider accounts
        orgs_with_tech_provider = db.query(Organization).join(
            WhatsAppAccount,
            WhatsAppAccount.organization_id == Organization.id
        ).distinct().all()
        
        print(f"Organizations with Tech Provider accounts: {len(orgs_with_tech_provider)}")
        
        # Organizations that need migration
        orgs_needing_migration = []
        for org in orgs_with_whatsapp:
            has_tech_account = db.query(WhatsAppAccount).filter(
                WhatsAppAccount.organization_id == org.id
            ).first()
            
            if not has_tech_account:
                orgs_needing_migration.append(org)
        
        print(f"Organizations needing migration: {len(orgs_needing_migration)}")
        
        if orgs_needing_migration:
            print("\n" + "-" * 80)
            print("Organizations that need migration:")
            print("-" * 80)
            
            for org in orgs_needing_migration:
                user_count = db.query(WhatsAppUser).filter(
                    WhatsAppUser.organization_id == org.id
                ).count()
                
                phone = org.phone_number or "⚠️  NO PHONE NUMBER"
                print(f"\n📋 {org.name}")
                print(f"   ID: {org.id}")
                print(f"   Phone: {phone}")
                print(f"   WhatsApp Users: {user_count}")
        else:
            print("\n✅ All organizations are already migrated!")
        
        if orgs_with_tech_provider:
            print("\n" + "-" * 80)
            print("Organizations already migrated:")
            print("-" * 80)
            
            for org in orgs_with_tech_provider:
                tech_account = db.query(WhatsAppAccount).filter(
                    WhatsAppAccount.organization_id == org.id
                ).first()
                
                # Get phone numbers for this account
                phone_numbers = db.query(WhatsAppPhoneNumber).filter(
                    WhatsAppPhoneNumber.whatsapp_account_id == tech_account.id
                ).all()
                
                print(f"\n✅ {org.name}")
                print(f"   Account Code: {tech_account.code}")
                print(f"   Status: {tech_account.status.value}")
                print(f"   Subaccount SID: {tech_account.twilio_subaccount_sid}")
                
                if phone_numbers:
                    print(f"   Phone Numbers ({len(phone_numbers)}):")
                    for pn in phone_numbers:
                        primary = " (PRIMARY)" if pn.is_primary else ""
                        print(f"     - {pn.phone_number}{primary} [{pn.status.value}] - {pn.code}")
                else:
                    print(f"   Phone Numbers: None")
        
        print("\n" + "=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
