# Migration Scripts

Scripts for migrating existing organizations to the WhatsApp Tech Provider system.

## Prerequisites

1. **Database migrations run**:
   ```bash
   cd backend
   alembic revision --autogenerate -m "Add WhatsApp Tech Provider tables"
   alembic upgrade head
   ```

2. **Environment variables set**:
   ```bash
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   ENCRYPTION_KEY=your_fernet_key  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   BACKEND_URL=https://your-backend.com
   ```

3. **Organizations have phone_number set**:
   - Check with: `python -m scripts.check_migration_status`
   - Update in database if needed

---

## Scripts

### 1. Check Migration Status

See which organizations need migration:

```bash
cd backend
python -m scripts.check_migration_status
```

**Output**:
- Total organizations
- Organizations with WhatsApp users
- Organizations already migrated
- Organizations needing migration (with details)

---

### 2. Migrate Organizations

Migrate existing organizations to Tech Provider system:

```bash
cd backend

# Dry run (no changes made)
python -m scripts.migrate_existing_orgs_to_tech_provider --dry-run

# Actual migration (requires confirmation)
python -m scripts.migrate_existing_orgs_to_tech_provider
```

**What it does**:
1. Finds organizations with WhatsApp users but no Tech Provider account
2. Creates isolated Twilio subaccount for each organization
3. Creates `WhatsAppAccount` record with encrypted credentials
4. Registers WhatsApp sender with Twilio (if possible)
5. Creates `WhatsAppSender` record
6. Updates existing `WhatsAppUser` records to use new subaccount

**Requirements**:
- Organization must have `phone_number` set
- Phone number must be valid E.164 format
- Twilio credentials must be valid

---

## Migration Process

### Step 1: Check Status

```bash
python -m scripts.check_migration_status
```

Review the output. Organizations without phone numbers need to be updated first.

### Step 2: Update Missing Phone Numbers

For organizations without phone numbers, update them in the database:

```sql
UPDATE organizations 
SET phone_number = '+1234567890' 
WHERE id = 'organization-uuid';
```

Or via Python:

```python
from app.database import SessionLocal
from app.models.user import Organization

db = SessionLocal()
org = db.query(Organization).filter(Organization.id == 'uuid').first()
org.phone_number = '+1234567890'
db.commit()
```

### Step 3: Dry Run Migration

```bash
python -m scripts.migrate_existing_orgs_to_tech_provider --dry-run
```

Review what would be migrated. No changes are made.

### Step 4: Run Migration

```bash
python -m scripts.migrate_existing_orgs_to_tech_provider
```

Confirm when prompted. The script will:
- Create subaccounts
- Register senders
- Update database records

### Step 5: Update Twilio Webhooks

For each migrated organization, update Twilio webhook URLs:

**Option A: Automatic (via Twilio Console)**
1. Go to Twilio Console → Messaging → Senders
2. Find the WhatsApp sender for each organization
3. Update webhook URLs to:
   - Inbound: `https://your-backend.com/webhooks/whatsapp/inbound`
   - Status: `https://your-backend.com/webhooks/whatsapp/status`

**Option B: Via API**
The migration script attempts to set webhooks automatically during sender registration.

### Step 6: Test

Send test messages to each migrated organization:
1. Send WhatsApp message to organization's number
2. Check logs for proper routing
3. Verify flow execution or agent response
4. Check message appears in database

---

## Troubleshooting

### "No phone number configured for organization"

**Solution**: Update `Organization.phone_number` in database before migration.

### "Failed to register sender"

**Causes**:
- Phone number not verified with Meta
- Phone number already registered to different WABA
- Invalid phone number format

**Solution**: 
- Migration continues anyway (account created)
- Register sender manually via Twilio Console or onboarding flow

### "Failed to create subaccount"

**Causes**:
- Invalid Twilio credentials
- Twilio account doesn't support subaccounts
- Rate limiting

**Solution**: Check Twilio credentials and account type.

### "Organization already has Tech Provider account"

**Not an error**: Organization was already migrated. Script skips it.

---

## Post-Migration

### Verify Migration

```bash
python -m scripts.check_migration_status
```

Should show all organizations as migrated.

### Monitor Logs

Watch for any webhook errors:

```bash
tail -f logs/app.log | grep whatsapp
```

### Test Each Organization

1. Send test message to each organization
2. Verify proper routing and response
3. Check database for message records

### Update Documentation

Update your internal docs with:
- New webhook URLs
- Subaccount credentials (if needed)
- Migration date and status

---

## Rollback

If migration fails or causes issues:

### Option 1: Delete Tech Provider Records

```python
from app.database import SessionLocal
from app.models.whatsapp_account import WhatsAppAccount

db = SessionLocal()
account = db.query(WhatsAppAccount).filter(
    WhatsAppAccount.organization_id == 'org-uuid'
).first()

if account:
    db.delete(account)  # Cascades to senders
    db.commit()
```

### Option 2: Suspend Subaccount

```python
from app.service.twilio.tech_provider import TwilioTechProviderService

service = TwilioTechProviderService()
await service.suspend_subaccount('subaccount-sid')
```

### Option 3: Revert WhatsApp Users

```python
from app.models.whatsapp import WhatsAppUser

users = db.query(WhatsAppUser).filter(
    WhatsAppUser.organization_id == 'org-uuid'
).all()

for user in users:
    user.account_sid = 'original-account-sid'

db.commit()
```

---

## Notes

- **Backup database** before running migration
- **Test in staging** environment first
- **Migrate during low-traffic** period
- **Monitor closely** after migration
- **Keep old webhook endpoints** active during transition
- **Gradual rollout** recommended (migrate few orgs at a time)

---

## Support

If you encounter issues:
1. Check logs: `logs/app.log`
2. Run status check: `python -m scripts.check_migration_status`
3. Review Twilio Console for subaccount status
4. Check database for incomplete records
