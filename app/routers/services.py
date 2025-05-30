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
    organization_id: int,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check if user has access to this organization
    check_organization_access(organization_id, current_user)
    """
    Test endpoint to retrieve products from WooCommerce.
    
    Args:
        organization_id: Organization ID to connect to WooCommerce
        query: Optional search query to filter products
    """
    # Get organization credentials
    organization = db.query(Organization).filter_by(id=organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail=f"Organization with ID {organization_id} not found")
    
    # Check if organization has WooCommerce credentials
    if not all([organization.consumer_key, organization.consumer_secret, organization.woo_url]):
        raise HTTPException(
            status_code=400, 
            detail="Organization doesn't have WooCommerce credentials configured"
        )
    
    # Create WooCommerce client
    woo_client = WooCommerceAPIClient(
        base_url=organization.woo_url,
        consumer_key=organization.consumer_key,
        consumer_secret=organization.consumer_secret,
    )
    
    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=organization_id)
    
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
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")


@router.get("/woocommerce/orders/{order_id}", response_model=Dict[str, Any])
async def test_woocommerce_order(
    order_id: int,
    organization_id: str,
    db: Session = Depends(get_db)
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
        raise HTTPException(status_code=404, detail=f"Organization with ID {organization_id} not found")
    
    # Check if organization has WooCommerce credentials
    if not all([organization.consumer_key, organization.consumer_secret, organization.woo_url]):
        raise HTTPException(
            status_code=400, 
            detail="Organization doesn't have WooCommerce credentials configured"
        )
    
    # Create WooCommerce client
    woo_client = WooCommerceAPIClient(
        base_url=organization.woo_url,
        consumer_key=organization.consumer_key,
        consumer_secret=organization.consumer_secret,
    )
    
    # Create WooService instance
    woo_service = WooService(client=woo_client, organization_id=organization_id)
    
    try:
        # Retrieve order
        order = woo_service.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving order: {str(e)}")
