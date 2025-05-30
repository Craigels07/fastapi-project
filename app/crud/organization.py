from sqlalchemy.orm import Session
from app.models.user import Organization
from app.schemas.user import OrganizationCreate, Organization as OrganizationSchema
from typing import List, Optional

def create_organization(db: Session, organization: OrganizationCreate) -> Organization:
    """
    Create a new organization
    """
    db_organization = Organization(
        name=organization.name,
        email=organization.email,
        phone_number=organization.phone_number,
        organization_metadata=organization.organization_metadata,
        woo_commerce=organization.woo_commerce
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization

def get_organization(db: Session, organization_id: int) -> Optional[Organization]:
    """
    Get an organization by ID
    """
    return db.query(Organization).filter(Organization.id == organization_id).first()

def get_organization_by_phone(db: Session, phone_number: str) -> Optional[Organization]:
    """
    Get an organization by phone number
    """
    return db.query(Organization).filter(Organization.phone_number == phone_number).first()

def get_organizations(db: Session, skip: int = 0, limit: int = 100) -> List[Organization]:
    """
    Get a list of organizations with pagination
    """
    return db.query(Organization).offset(skip).limit(limit).all()

def update_organization(db: Session, organization_id: int, organization_data: dict) -> Optional[Organization]:
    """
    Update an organization's data
    """
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        return None
        
    # Update fields
    for key, value in organization_data.items():
        if hasattr(db_organization, key) and value is not None:
            setattr(db_organization, key, value)
            
    db.commit()
    db.refresh(db_organization)
    return db_organization

def delete_organization(db: Session, organization_id: int) -> bool:
    """
    Delete an organization by ID
    """
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        return False
        
    db.delete(db_organization)
    db.commit()
    return True

def get_organization_with_users(db: Session, organization_id: int) -> Optional[Organization]:
    """
    Get an organization with its users
    """
    return db.query(Organization).filter(Organization.id == organization_id).first()

def add_woocommerce_credentials(
    db: Session, 
    organization_id: int, 
    woo_url: str,
    consumer_key: str, 
    consumer_secret: str
) -> Optional[Organization]:
    """
    Add WooCommerce credentials to an organization
    """
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        return None
        
    # Mark as WooCommerce enabled
    db_organization.woo_commerce = True
    
    # Store credentials in metadata (in a real app, you would encrypt these)
    import json
    metadata = json.loads(db_organization.organization_metadata or "{}")
    metadata.update({
        "woo_url": woo_url,
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret
    })
    db_organization.organization_metadata = json.dumps(metadata)
    
    db.commit()
    db.refresh(db_organization)
    return db_organization
