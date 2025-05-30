# woo_helper.py
from app.service.woo.service import WooService


def get_order_status(woo_service: WooService, order_id_or_phone: str) -> str:
    # Use WooService.get_order_status to fetch and return the order status
    return woo_service.get_order_status(order_id_or_phone)


def list_products(woo_service: WooService, query: str, limit: int = 5) -> str:
    # Use WooService.list_products to fetch and list products
    products = woo_service.list_products(query=query, limit=limit)
    return "\n".join(
        [f"{product['name']} - Price: {product['price']}" for product in products]
    )
