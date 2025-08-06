from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import Organization, User
from app.service.woo.client import WooCommerceAPIClient
from app.service.woo.service import WooService
from app.auth.dependencies import get_current_active_user, check_organization_access

router = APIRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
)


@router.get("/woocommerce/products", response_model=List[Dict[str, Any]])
async def test_woocommerce_products(
    organization_id: str,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Test endpoint to retrieve products from WooCommerce.

    Args:
        organization_id: Organization ID to connect to WooCommerce
        query: Optional search query to filter products
    """
    # Check if user has access to this organization
    # Convert organization_id to string if it's not already
    check_organization_access(str(organization_id), current_user)

    # Get organization credentials
    organization = db.query(Organization).filter_by(id=organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=404, detail=f"Organization with ID {organization_id} not found"
        )

    # Get WooCommerce credentials from service_credentials table
    from app.models.service_credential import ServiceCredential, ServiceTypeEnum
    from app.utils.encryption import decrypt_data
    import json

    try:
        # Find WooCommerce credentials for this organization
        woo_credentials = (
            db.query(ServiceCredential)
            .filter(
                ServiceCredential.organization_id == organization.id,
                ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
                ServiceCredential.is_active == "true",
            )
            .first()
        )

        if not woo_credentials:
            raise HTTPException(
                status_code=400,
                detail="Organization doesn't have WooCommerce credentials configured",
            )

        # Decrypt credentials
        decrypted_json = decrypt_data(woo_credentials.credentials)
        creds = json.loads(decrypted_json)

        # Extract credential values
        woo_url = creds.get("woo_url")
        consumer_key = creds.get("consumer_key")
        consumer_secret = creds.get("consumer_secret")

        if not all([woo_url, consumer_key, consumer_secret]):
            raise HTTPException(
                status_code=400,
                detail="Organization's WooCommerce credentials are incomplete",
            )

        # Create WooCommerce client
        woo_client = WooCommerceAPIClient(
            base_url=woo_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving WooCommerce credentials: {str(e)}",
        )

    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=str(organization_id))

    try:
        # Retrieve products
        if query:
            # Get products filtered by query
            product_names = woo_service.get_product_names(query=query)
            return [{"name": product} for product in product_names]
        else:
            # Get detailed product information
            products = woo_service.list_products()
            return products
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving products: {str(e)}"
        )


@router.get("/woocommerce/all-products", response_model=List[Dict[str, Any]])
async def test_get_all_woocommerce_products(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Test endpoint to retrieve all products from WooCommerce.

    Args:
        organization_id: Organization ID to connect to WooCommerce
    """
    # Check if user has access to this organization
    # Convert organization_id to string if it's not already
    check_organization_access(str(organization_id), current_user)

    # Get organization credentials
    organization = db.query(Organization).filter_by(id=organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=404, detail=f"Organization with ID {organization_id} not found"
        )

    # Get WooCommerce credentials from service_credentials table
    from app.models.service_credential import ServiceCredential, ServiceTypeEnum
    from app.utils.encryption import decrypt_data
    import json

    try:
        # Find WooCommerce credentials for this organization
        woo_credentials = (
            db.query(ServiceCredential)
            .filter(
                ServiceCredential.organization_id == organization.id,
                ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
                ServiceCredential.is_active == "true",
            )
            .first()
        )

        if not woo_credentials:
            raise HTTPException(
                status_code=400,
                detail="Organization doesn't have WooCommerce credentials configured",
            )

        # Decrypt credentials
        decrypted_json = decrypt_data(woo_credentials.credentials)
        creds = json.loads(decrypted_json)

        # Extract credential values
        woo_url = creds.get("woo_url")
        consumer_key = creds.get("consumer_key")
        consumer_secret = creds.get("consumer_secret")

        if not all([woo_url, consumer_key, consumer_secret]):
            raise HTTPException(
                status_code=400,
                detail="Organization's WooCommerce credentials are incomplete",
            )

        # Create WooCommerce client
        woo_client = WooCommerceAPIClient(
            base_url=woo_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving WooCommerce credentials: {str(e)}",
        )

    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=str(organization_id))

    try:
        # Get all products with complete details
        products = woo_service.list_products()
        return products
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving products: {str(e)}"
        )


@router.get("/woocommerce/all-orders", response_model=List[Dict[str, Any]])
async def test_get_all_woocommerce_orders(
    organization_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Test endpoint to retrieve all orders from WooCommerce.

    Args:
        organization_id: Organization ID to connect to WooCommerce
    """
    # Check if user has access to this organization
    # Convert organization_id to string if it's not already
    check_organization_access(str(organization_id), current_user)

    # Get organization credentials
    organization = db.query(Organization).filter_by(id=organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=404, detail=f"Organization with ID {organization_id} not found"
        )

    # Get WooCommerce credentials from service_credentials table
    from app.models.service_credential import ServiceCredential, ServiceTypeEnum
    from app.utils.encryption import decrypt_data
    import json

    try:
        # Find WooCommerce credentials for this organization
        woo_credentials = (
            db.query(ServiceCredential)
            .filter(
                ServiceCredential.organization_id == organization.id,
                ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
                ServiceCredential.is_active == "true",
            )
            .first()
        )

        if not woo_credentials:
            raise HTTPException(
                status_code=400,
                detail="Organization doesn't have WooCommerce credentials configured",
            )

        # Decrypt credentials
        decrypted_json = decrypt_data(woo_credentials.credentials)
        creds = json.loads(decrypted_json)

        # Extract credential values
        woo_url = creds.get("woo_url")
        consumer_key = creds.get("consumer_key")
        consumer_secret = creds.get("consumer_secret")

        if not all([woo_url, consumer_key, consumer_secret]):
            raise HTTPException(
                status_code=400,
                detail="Organization's WooCommerce credentials are incomplete",
            )

        # Create WooCommerce client
        woo_client = WooCommerceAPIClient(
            base_url=woo_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving WooCommerce credentials: {str(e)}",
        )

    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=str(organization_id))

    try:
        # Get all orders
        orders = woo_service.get_orders()
        return orders
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving orders: {str(e)}"
        )


@router.get("/woocommerce/orders/{order_id}", response_model=Dict[str, Any])
async def test_woocommerce_order(
    order_id: int, organization_id: str, db: Session = Depends(get_db)
):
    """
    Test endpoint to retrieve a specific order from WooCommerce.

    Args:
        order_id: Order ID to retrieve
        organization_id: Organization ID to connect to WooCommerce
    """
    # Get organization credentials
    organization = db.query(Organization).filter_by(id=organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=404, detail=f"Organization with ID {organization_id} not found"
        )

    # Get WooCommerce credentials from service_credentials table
    from app.models.service_credential import ServiceCredential, ServiceTypeEnum
    from app.utils.encryption import decrypt_data
    import json

    try:
        # Find WooCommerce credentials for this organization
        woo_credentials = (
            db.query(ServiceCredential)
            .filter(
                ServiceCredential.organization_id == organization.id,
                ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
                ServiceCredential.is_active == "true",
            )
            .first()
        )

        if not woo_credentials:
            raise HTTPException(
                status_code=400,
                detail="Organization doesn't have WooCommerce credentials configured",
            )

        # Decrypt credentials
        decrypted_json = decrypt_data(woo_credentials.credentials)
        creds = json.loads(decrypted_json)

        # Extract credential values
        woo_url = creds.get("woo_url")
        consumer_key = creds.get("consumer_key")
        consumer_secret = creds.get("consumer_secret")

        if not all([woo_url, consumer_key, consumer_secret]):
            raise HTTPException(
                status_code=400,
                detail="Organization's WooCommerce credentials are incomplete",
            )

        # Create WooCommerce client
        woo_client = WooCommerceAPIClient(
            base_url=woo_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving WooCommerce credentials: {str(e)}",
        )

    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=str(organization_id))

    try:
        # Retrieve order
        order = woo_service.get_order_by_id(order_id)
        if not order:
            raise HTTPException(
                status_code=404, detail=f"Order with ID {order_id} not found"
            )
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving order: {str(e)}")
