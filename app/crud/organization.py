from sqlalchemy.orm import Session
from app.models.user import Organization
from app.schemas.organization import OrganizationCreate
from typing import List, Optional, Union
from uuid import UUID


def create_organization(db: Session, organization: OrganizationCreate) -> Organization:
    """
    Create a new organization
    """
    db_organization = Organization(
        name=organization.name,
        email=organization.email,
        phone_number=organization.phone_number,
        organization_metadata=organization.organization_metadata,
        woo_commerce=organization.woo_commerce,
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization


def get_organization(
    db: Session, organization_id: Union[UUID, str], include_users: bool = False
) -> Optional[Organization]:
    """
    Get an organization by ID
    If include_users is True, eager loads the users relationship
    """
    query = db.query(Organization).filter(Organization.id == organization_id)

    if include_users:
        from sqlalchemy.orm import joinedload

        query = query.options(joinedload(Organization.users))

    return query.first()


def get_organization_by_phone(db: Session, phone_number: str) -> Optional[Organization]:
    """
    Get an organization by phone number
    """
    return (
        db.query(Organization).filter(Organization.phone_number == phone_number).first()
    )


def get_organization_by_email(db: Session, email: str) -> Optional[Organization]:
    """
    Get an organization by email address
    """
    return db.query(Organization).filter(Organization.email == email).first()


def get_organizations(
    db: Session, skip: int = 0, limit: int = 100
) -> List[Organization]:
    """
    Get a list of organizations with pagination
    """
    return db.query(Organization).offset(skip).limit(limit).all()


def update_organization(
    db: Session, organization_id: Union[UUID, str], organization_data: dict
) -> Optional[Organization]:
    """
    Update an organization's data
    """
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        return None

    # Handle users separately if present in the data
    users_data = organization_data.pop("users", None)

    # Update organization fields from the data
    for key, value in organization_data.items():
        if hasattr(db_organization, key) and value is not None:
            setattr(db_organization, key, value)

    # Update users if provided
    if users_data is not None and isinstance(users_data, list):
        from app.models.user import User

        # Get all user IDs from the input data
        user_ids = [user.get("id") for user in users_data if user.get("id")]

        # Find existing users in the database
        existing_users = db.query(User).filter(User.id.in_(user_ids)).all()

        # Update existing users or create new ones
        for user_data in users_data:
            user_id = user_data.get("id")

            # Find the user in the existing users
            db_user = next(
                (u for u in existing_users if str(u.id) == str(user_id)), None
            )

            if db_user:
                # Update existing user
                for key, value in user_data.items():
                    if hasattr(db_user, key) and value is not None and key != "id":
                        setattr(db_user, key, value)
                # Ensure the user belongs to this organization
                db_user.organization_id = organization_id

    # Commit the changes
    db.commit()
    db.refresh(db_organization)
    return db_organization


def delete_organization(db: Session, organization_id: Union[UUID, str]) -> bool:
    """
    Delete an organization by ID
    """
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        return False

    db.delete(db_organization)
    db.commit()
    return True


def get_organization_with_users(
    db: Session, organization_id: Union[UUID, str]
) -> Optional[Organization]:
    """
    Get an organization with its users
    """
    return db.query(Organization).filter(Organization.id == organization_id).first()


def add_woocommerce_credentials(
    db: Session,
    organization_id: Union[UUID, str],
    woo_url: str,
    consumer_key: str,
    consumer_secret: str,
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
    metadata = db_organization.organization_metadata or {}

    # Create woo_commerce key if it doesn't exist
    if "woo_commerce" not in metadata:
        metadata["woo_commerce"] = {}

    # Update credentials
    metadata["woo_commerce"].update(
        {"url": woo_url, "key": consumer_key, "secret": consumer_secret}
    )

    db_organization.organization_metadata = metadata

    db.commit()
    db.refresh(db_organization)
    return db_organization
