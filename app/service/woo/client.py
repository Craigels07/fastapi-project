"""WooCommerce API client for interacting with the WooCommerce REST API."""

import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin


class WooCommerceAPIClient:
    def __init__(self, base_url, consumer_key, consumer_secret):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(consumer_key, consumer_secret)

    def _request(self, method, endpoint, params=None, data=None):
        url = urljoin(self.base_url, f"/wp-json/wc/v3/{endpoint}")
        response = requests.request(
            method, url, auth=self.auth, params=params, json=data
        )
        response.raise_for_status()
        return response.json()

    def get_orders(self, params=None):
        """Get all orders with optional filtering parameters.

        Args:
            params (dict, optional): Query parameters to filter orders.
                Common params: status, after, before, page, per_page, etc.

        Returns:
            list: List of order objects
        """
        return self._request("GET", "orders", params=params)

    def get_order(self, order_id):
        """Get a specific order by ID.

        Args:
            order_id (int): The order ID

        Returns:
            dict: Order details
        """
        return self._request("GET", f"orders/{order_id}")

    def get_order_statuses(self):
        """Get all available order statuses from WooCommerce.

        Returns:
            dict: Available order statuses
        """
        return self._request("GET", "reports/orders/totals")

    def update_order(self, order_id, data):
        """Update an order.

        Args:
            order_id (int): The order ID
            data (dict): The data to update

        Returns:
            dict: Updated order details
        """
        return self._request("PUT", f"orders/{order_id}", data=data)

    def get_recent_orders(self, hours=24, status=None, per_page=50):
        """Get orders from the last specified hours.

        Args:
            hours (int): Hours to look back
            status (str, optional): Filter by specific status
            per_page (int): Number of orders per page (max 100)

        Returns:
            list: List of order objects
        """
        import datetime

        from_date = datetime.datetime.now() - datetime.timedelta(hours=hours)
        params = {"after": from_date.isoformat(), "per_page": per_page}
        if status:
            params["status"] = status

        return self.get_orders(params=params)

    def get_products(self, params=None):
        """Get all products with optional filtering parameters.

        Args:
            params (dict, optional): Query parameters to filter products.
                Common params: status, category, include, etc.

        Returns:
            list: List of product objects
        """
        return self._request("GET", "products", params=params)

    def get_product(self, product_id):
        """Get a specific product by ID.

        Args:
            product_id (int): The product ID

        Returns:
            dict: Product details
        """
        return self._request("GET", f"products/{product_id}")
