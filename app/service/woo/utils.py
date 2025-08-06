"""Utils for handling WooCommerce operations."""

from typing import Dict, Any, List


def extract_product_names(products: List[Dict[str, Any]]) -> List[str]:
    return [product.get("name", "Unnamed") for product in products]


def format_order_status(order: Dict[str, Any]) -> str:
    return f"Order {order['id']} is currently '{order['status']}' and totals {order['total']} {order['currency']}."


def simplify_product(product: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": product.get("id"),
        "name": product.get("name"),
        "price": product.get("price"),
        "stock_status": product.get("stock_status"),
    }


def format_product_list(products: List[Dict[str, Any]]) -> str:
    return "\n".join([f"{p['name']} - ${p['price']}" for p in products])


def calculate_order_total(order: Dict[str, Any]) -> float:
    return sum(float(item["total"]) for item in order.get("line_items", []))


def filter_products_by_availability(
    products: List[Dict[str, Any]], status: str = "instock"
) -> List[Dict[str, Any]]:
    return [p for p in products if p.get("stock_status") == status]


def convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    # This function would require a currency conversion API or a conversion rate table.
    pass


def validate_order_data(order: Dict[str, Any]) -> bool:
    required_fields = ["id", "status", "total", "currency"]
    return all(field in order for field in required_fields)
