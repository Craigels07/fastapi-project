from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from uuid import UUID
import json

from app.models.service_credential import ServiceCredential, ServiceTypeEnum
from app.schemas.service_credential import (
    ServiceCredentialCreate,
    ServiceCredentialUpdate,
)
from app.utils.encryption import encrypt_data, decrypt_data


def create_service_credential(
    db: Session, credential: ServiceCredentialCreate
) -> ServiceCredential:
    """
    Create a new service credential with encrypted credentials
    """
    # Convert credentials to JSON string and encrypt
    credentials_json = json.dumps(credential.credentials)
    encrypted_credentials = encrypt_data(credentials_json)

    # Create DB model instance with encrypted credentials
    db_credential = ServiceCredential(
        organization_id=credential.organization_id,
        service_type=credential.service_type,
        credentials=encrypted_credentials,
        name=credential.name,
        is_active=credential.is_active,
    )

    # Add to DB and commit
    db.add(db_credential)
    db.commit()
    db.refresh(db_credential)

    return db_credential


def get_service_credential(
    db: Session, credential_id: UUID
) -> Optional[ServiceCredential]:
    """
    Get a service credential by ID
    """
    return (
        db.query(ServiceCredential)
        .filter(ServiceCredential.id == credential_id)
        .first()
    )


def get_service_credentials_by_org(
    db: Session, organization_id: UUID, service_type: Optional[ServiceTypeEnum] = None
) -> List[ServiceCredential]:
    """
    Get all service credentials for an organization, optionally filtered by service type
    """
    query = db.query(ServiceCredential).filter(
        ServiceCredential.organization_id == organization_id
    )

    if service_type:
        query = query.filter(ServiceCredential.service_type == service_type)

    return query.all()


def update_service_credential(
    db: Session, credential_id: UUID, credential_update: ServiceCredentialUpdate
) -> Optional[ServiceCredential]:
    """
    Update a service credential
    """
    db_credential = get_service_credential(db, credential_id)

    if not db_credential:
        return None

    # Update fields
    update_data = credential_update.model_dump(exclude_unset=True)

    # Handle credentials specially - they need to be encrypted
    if "credentials" in update_data:
        credentials_json = json.dumps(update_data["credentials"])
        update_data["credentials"] = encrypt_data(credentials_json)

    # Update model
    for key, value in update_data.items():
        setattr(db_credential, key, value)

    db.commit()
    db.refresh(db_credential)

    return db_credential


def delete_service_credential(db: Session, credential_id: UUID) -> bool:
    """
    Delete a service credential
    """
    db_credential = get_service_credential(db, credential_id)

    if not db_credential:
        return False

    db.delete(db_credential)
    db.commit()

    return True


def get_decrypted_credentials(
    db: Session, credential_id: UUID
) -> Optional[Dict[str, Any]]:
    """
    Get decrypted credentials for a service
    """
    db_credential = get_service_credential(db, credential_id)

    if not db_credential:
        return None

    # Decrypt the credentials
    decrypted_json = decrypt_data(db_credential.credentials)
    credentials = json.loads(decrypted_json)

    return credentials


def get_organization_service_credentials(
    db: Session, organization_id: UUID
) -> Dict[str, Dict[str, Any]]:
    """
    Get all decrypted credentials for an organization's services, organized by service type
    """
    db_credentials = get_service_credentials_by_org(db, organization_id)
    result = {}

    for cred in db_credentials:
        if not cred.is_active:
            continue

        decrypted_json = decrypt_data(cred.credentials)
        credentials = json.loads(decrypted_json)

        service_type = (
            cred.service_type.value
            if isinstance(cred.service_type, ServiceTypeEnum)
            else cred.service_type
        )

        # Add to result
        result[service_type] = {
            "id": str(cred.id),
            "name": cred.name,
            "credentials": credentials,
        }

    return result
