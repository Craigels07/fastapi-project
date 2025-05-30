from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from app.database import get_db
from app.models.user import Organization, User
from app.schemas.user import OrganizationCreate, Organization as OrganizationSchema
from app.crud.organization import (
    create_organization,
    get_organization,
    get_organization_by_phone,
    get_organizations,
    update_organization,
    delete_organization,
    add_woocommerce_credentials
)
from app.auth.dependencies import get_current_active_user, has_role, check_organization_access

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"}
    }
)


# Schema for WooCommerce credentials
class WooCommerceCredentials(BaseModel):
    woo_url: str
    consumer_key: str
    consumer_secret: str


@router.post("/", response_model=OrganizationSchema)
async def create_new_organization(
    organization: OrganizationCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(has_role(["admin"]))
):
    """
    Create a new organization
    
    Requires admin role
    """
    return create_organization(db, organization)


@router.get("/{organization_id}", response_model=OrganizationSchema)
async def get_organization_by_id(
    organization_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):  
    # Check organization access directly
    check_organization_access(organization_id, current_user)
    """
    Get an organization by ID
    
    Users can only access their own organization. Admins can access any organization.
    """
    db_organization = get_organization(db, organization_id)
    if db_organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return db_organization


@router.get("/phone/{phone_number}", response_model=OrganizationSchema)
async def get_organization_by_phone_number(
    phone_number: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(has_role(["admin"]))
):
    """
    Get an organization by phone number
    
    Requires admin role
    """
    db_organization = get_organization_by_phone(db, phone_number)
    if db_organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return db_organization


@router.get("/", response_model=List[OrganizationSchema])
async def list_organizations(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(has_role(["admin"]))
):
    """
    Get a list of all organizations with pagination
    
    Requires admin role
    """
    return get_organizations(db, skip=skip, limit=limit)


@router.put("/{organization_id}", response_model=OrganizationSchema)
async def update_organization_endpoint(
    organization_id: int, 
    organization_data: Dict[str, Any] = Body(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check organization access directly
    check_organization_access(organization_id, current_user)
    """
    Update an organization
    
    Users can only update their own organization. Admins can update any organization.
    """
    db_organization = update_organization(db, organization_id, organization_data)
    if db_organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return db_organization


@router.delete("/{organization_id}")
async def delete_organization_endpoint(
    organization_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(has_role(["admin"]))
):
    """
    Delete an organization
    
    Requires admin role
    """
    if not delete_organization(db, organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return {"message": "Organization deleted successfully"}


@router.post("/{organization_id}/woocommerce", response_model=OrganizationSchema)
async def add_woocommerce_to_organization(
    organization_id: int,
    credentials: WooCommerceCredentials,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check organization access directly
    check_organization_access(organization_id, current_user)
    """
    Add WooCommerce credentials to an organization
    
    Users can only add credentials to their own organization. Admins can add to any organization.
    """
    db_organization = add_woocommerce_credentials(
        db, 
        organization_id, 
        credentials.woo_url,
        credentials.consumer_key, 
        credentials.consumer_secret
    )
    
    if db_organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        
    return db_organization


@router.get("/{organization_id}/services", response_model=Dict[str, bool])
async def get_organization_services(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check organization access directly
    check_organization_access(organization_id, current_user)
    """
    Get available services for an organization
    
    Users can only view services for their own organization. Admins can view for any organization.
    """
    db_organization = get_organization(db, organization_id)
    if db_organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    
    # Get services from organization metadata
    import json
    metadata = json.loads(db_organization.organization_metadata or "{}")
    
    services = {
        "woocommerce": db_organization.woo_commerce and "woo_url" in metadata,
        # Add other services here as they become available
        "octive": False  # Example for future service
    }
    
    return services
