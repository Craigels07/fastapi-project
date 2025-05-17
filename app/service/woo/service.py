# app/service/woo/service.py

from typing import List, Dict
from app.clients.woocommerce_client import WooCommerceAPIClient  # Adjusted import
from app.service.woo.utils import (
    simplify_product,
    extract_product_names,
    format_order_status,
)


class WooService:
    def __init__(self, client: WooCommerceAPIClient):  # Adjusted type hint
        self.client = client

    def _request(self, method, endpoint, params=None, data=None):
        return self.client._request(method, endpoint, params=params, data=data)

    def list_products(self) -> List[Dict]:
        """Retrieve a list of simplified product information."""
        products = self._request("GET", "products")
        return [simplify_product(p) for p in products]

    def get_product_names(self) -> List[str]:
        """Get a list of all available product names."""
        products = self._request("GET", "products")
        return extract_product_names(products)

    def get_order_status(self, order_id: str) -> str:
        """Retrieve and format the status of a given order."""
        order = self._request("GET", f"orders/{order_id}")
        return format_order_status(order)

    def get_orders(self, **params):
        return self._request("GET", "orders", params=params)

    def get_products(self, **params):
        return self._request("GET", "products", params=params)

    def get_order_by_id(self, order_id: int):
        return self._request("GET", f"orders/{order_id}")

    def get_product_by_id(self, product_id: int):
        return self._request("GET", f"products/{product_id}")
