# app/agent/tools/woo_tools.py

from langchain_core.tools import BaseTool
from app.service.woo.service import WooService
from typing import Optional

# Assuming WooService is already instantiated elsewhere and injected here
# woo_service = WooService(woo_client)


class WooCommerceOrderStatusTool(BaseTool):
    name = "get_order_status"
    description = (
        "Get the status of a WooCommerce order by order ID or customer phone number."
    )

    def __init__(self, woo_service: WooService):
        super().__init__()
        self.woo_service = woo_service

    def _run(self, query: str) -> str:
        """Accepts an order ID or phone number (basic logic)."""
        try:
            if query.isdigit():
                return self.woo_service.get_order_status(query)
            else:
                # Optional: search orders by phone number, not implemented
                return "Order lookup by phone not implemented yet."
        except Exception as e:
            return f"Failed to fetch order status: {str(e)}"

    async def _arun(self, query: str) -> str:
        return self._run(query)


class WooCommerceListProductsTool(BaseTool):
    name = "list_products"
    description = "Search for WooCommerce products by keyword."

    def __init__(self, woo_service: WooService):
        super().__init__()
        self.woo_service = woo_service

    def _run(self, query: Optional[str] = None) -> str:
        try:
            products = self.woo_service.list_products()
            if query:
                products = [p for p in products if query.lower() in p["name"].lower()]
            return "\n".join(
                [f"{p['name']} - {p['price']} ({p['stock_status']})" for p in products]
            )
        except Exception as e:
            return f"Failed to list products: {str(e)}"

    async def _arun(self, query: Optional[str] = None) -> str:
        return self._run(query)
