from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.service_credential import ServiceTypeEnum
from app.schemas.service_credential import (
    ServiceCredentialCreate,
    ServiceCredentialUpdate,
    ServiceCredentialResponse,
    WooCommerceCredentials,
    TakealotCredentials,
)
from app.crud import service_credential as credential_crud

router = APIRouter(prefix="/service-credentials", tags=["service-credentials"])


@router.post(
    "/", response_model=ServiceCredentialResponse, status_code=status.HTTP_201_CREATED
)
async def create_service_credential(
    credential: ServiceCredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new service credential (Admin or Organization Owner only)"""
    # Check if user has permission to add credentials for this organization
    if (
        str(current_user.organization_id) != str(credential.organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create credentials for this organization",
        )

    # Create the credential
    db_credential = credential_crud.create_service_credential(db, credential)
    return db_credential


@router.get(
    "/organization/{organization_id}", response_model=List[ServiceCredentialResponse]
)
async def get_organization_credentials(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all service credentials for an organization"""
    # Check if user has permission to view organization credentials
    if (
        str(current_user.organization_id) != str(organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view credentials for this organization",
        )

    credentials = credential_crud.get_service_credentials_by_org(db, organization_id)
    return credentials


@router.get("/{credential_id}", response_model=ServiceCredentialResponse)
async def get_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific service credential"""
    credential = credential_crud.get_service_credential(db, credential_id)

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service credential not found"
        )

    # Check if user has permission to view this credential
    if (
        str(current_user.organization_id) != str(credential.organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this credential",
        )

    return credential


@router.put("/{credential_id}", response_model=ServiceCredentialResponse)
async def update_credential(
    credential_id: UUID,
    credential_update: ServiceCredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a service credential"""
    # First check if credential exists
    existing_credential = credential_crud.get_service_credential(db, credential_id)
    if not existing_credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service credential not found"
        )

    # Check if user has permission to update this credential
    if (
        str(current_user.organization_id) != str(existing_credential.organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this credential",
        )

    # Update the credential
    updated_credential = credential_crud.update_service_credential(
        db, credential_id, credential_update
    )
    return updated_credential


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a service credential"""
    # First check if credential exists
    existing_credential = credential_crud.get_service_credential(db, credential_id)
    if not existing_credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service credential not found"
        )

    # Check if user has permission to delete this credential
    if (
        str(current_user.organization_id) != str(existing_credential.organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this credential",
        )

    # Delete the credential
    credential_crud.delete_service_credential(db, credential_id)
    return None


# Type-specific endpoints for easier frontend integration
@router.post("/woocommerce/{organization_id}", response_model=ServiceCredentialResponse)
async def create_woocommerce_credential(
    organization_id: UUID,
    credentials: WooCommerceCredentials,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create WooCommerce credentials for an organization"""
    # Check if user has permission
    if (
        str(current_user.organization_id) != str(organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create credentials for this organization",
        )

    # Create credential object
    credential = ServiceCredentialCreate(
        organization_id=organization_id,
        service_type=ServiceTypeEnum.WOOCOMMERCE,
        name="WooCommerce API",
        credentials=credentials.dict(),
    )

    # Create in database
    db_credential = credential_crud.create_service_credential(db, credential)
    return db_credential


@router.post("/takealot/{organization_id}", response_model=ServiceCredentialResponse)
async def create_takealot_credential(
    organization_id: UUID,
    credentials: TakealotCredentials,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Takealot credentials for an organization"""
    # Check if user has permission
    if (
        str(current_user.organization_id) != str(organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create credentials for this organization",
        )

    # Create credential object
    credential = ServiceCredentialCreate(
        organization_id=organization_id,
        service_type=ServiceTypeEnum.TAKEALOT,
        name="Takealot API",
        credentials=credentials.dict(),
    )

    # Create in database
    db_credential = credential_crud.create_service_credential(db, credential)
    return db_credential
