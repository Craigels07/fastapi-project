"""
Router for WooCommerce order monitoring and notifications
"""

from fastapi import APIRouter

from app.api.endpoints import woo_monitor

router = APIRouter(
    tags=["woo-monitor"],
    responses={404: {"description": "Not found"}},
)

# Include the endpoints from the woo_monitor module
router.include_router(woo_monitor.router)
