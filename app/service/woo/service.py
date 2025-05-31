# app/service/woo/service.py

from typing import List, Dict, Any, ClassVar
from app.service.woo.client import WooCommerceAPIClient
from app.service.woo.utils import (
    simplify_product,
    extract_product_names,
    format_order_status,
)
from app.service.base import ServiceInterface, ServiceRegistry


@ServiceRegistry.register
class WooService(ServiceInterface):
    # Define service type and capabilities as required by ServiceInterface
    _service_type: ClassVar[str] = "woocommerce"
    _capabilities: ClassVar[List[str]] = [
        "order_query",
        "get_product_info",
        "order_status",
    ]

    def __init__(
        self,
        client: WooCommerceAPIClient = None,
        organization_id: str = None,
        credentials: dict = None,
        **kwargs,
    ):
        self.client = client
        self.organization_id = organization_id

        # Initialize with provided credentials if available
        if credentials:
            self.woo_url = credentials.get("woo_url")
            self.consumer_key = credentials.get("consumer_key")
            self.consumer_secret = credentials.get("consumer_secret")
        elif client and organization_id:
            try:
                # Retrieve credentials from service_credentials table
                self.woo_url, self.consumer_key, self.consumer_secret = (
                    self.retrieve_credentials()
                )
            except Exception:
                # Handle initialization errors gracefully
                self.woo_url = self.consumer_key = self.consumer_secret = None

    def retrieve_credentials(self):
        from app.database import get_db
        from sqlalchemy.orm import Session
        from app.models.service_credential import ServiceCredential, ServiceTypeEnum
        from app.utils.encryption import decrypt_data
        import json

        # Open a database session
        db_generator = get_db()
        db: Session = next(db_generator)

        try:
            # Query the service credentials
            credential = (
                db.query(ServiceCredential)
                .filter(
                    ServiceCredential.organization_id == self.organization_id,
                    ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
                    ServiceCredential.is_active.is_(True),
                )
                .first()
            )

            if not credential:
                raise ValueError(
                    f"WooCommerce credentials for organization ID {self.organization_id} not found"
                )

            # Decrypt the credentials
            try:
                decrypted_json = decrypt_data(credential.credentials)
                credentials = json.loads(decrypted_json)

                return (
                    credentials.get("woo_url"),
                    credentials.get("consumer_key"),
                    credentials.get("consumer_secret"),
                )
            except Exception as e:
                raise ValueError(f"Error decrypting credentials: {str(e)}")
        finally:
            # Close the database session
            db.close()

    def _request(self, method, endpoint, params=None, data=None):
        return self.client._request(method, endpoint, params=params, data=data)

    def list_products(self) -> List[Dict]:
        """Retrieve a list of simplified product information."""
        products = self._request("GET", "products")
        return [simplify_product(p) for p in products]

    def get_product_names(self, query: str = None) -> List[str]:
        """Get a list of all available product names, optionally filtered by query."""
        products = self._request("GET", "products")
        product_names = extract_product_names(products)

        # If query is provided, filter product names that contain the query (case-insensitive)
        if query:
            query = query.lower()
            return [name for name in product_names if query in name.lower()]

        return product_names

    def get_order_status(self, order_id: str) -> str:
        """Retrieve and format the status of a given order."""
        order = self._request("GET", f"orders/{order_id}")
        return format_order_status(order)

    def get_orders(self, **params):
        return self._request("GET", "orders", params=params)

    def get_products(self, **params):
        return self._request("GET", "products", params=params)

    def get_order_by_id(self, order_id):
        # Convert order_id to integer if it's a string containing only digits
        if isinstance(order_id, str) and order_id.isdigit():
            order_id = int(order_id)
        # Use try-except to handle potential API errors
        try:
            return self._request("GET", f"orders/{order_id}")
        except Exception as e:
            print(f"Error fetching order {order_id}: {e}")
            return None

    def get_product_by_id(self, product_id: int):
        return self._request("GET", f"products/{product_id}")

    def can_handle(self, message_purpose: str, message_details: Dict[str, Any]) -> bool:
        """
        Determine if this WooService can handle the given message purpose and details

        Args:
            message_purpose: Message purpose (e.g., 'order_query')
            message_details: Message details extracted from user input

        Returns:
            True if this service can handle the request, False otherwise
        """
        # Check if we have the necessary client
        if not self.client or not hasattr(self, "woo_url") or not self.woo_url:
            return False

        # Check if message purpose is one we can handle
        if message_purpose == "order_query":
            return "order_id" in message_details
        elif message_purpose == "get_product_info":
            return (
                "product_name" in message_details
                or "product_description" in message_details
            )

        return False

    def process_request(
        self, message_purpose: str, message_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a request and return response data

        Args:
            message_purpose: Message purpose
            message_details: Message details

        Returns:
            Response data including 'response_text' and optionally 'tool_output'
        """
        if not self.client:
            return {
                "response_text": "I'm having trouble accessing service information. Please try again later.",
                "tool_output": None,
            }

        if message_purpose == "order_query":
            return self._handle_order_query(message_details)
        elif message_purpose == "get_product_info":
            return self._handle_product_info(message_details)

        return {
            "response_text": "I'm not sure how to handle that request with WooCommerce.",
            "tool_output": None,
        }

    def _handle_order_query(self, message_details: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order query request with security validation"""
        order_id = message_details.get("order_id")
        user_phone_number = message_details.get("user_phone_number")
        
        if not order_id:
            return {
                "response_text": "It looks like you're asking about an order, but I couldn't identify the order number. Could you please provide the order ID?",
                "tool_output": None,
            }

        print(f"Attempting to fetch order with ID: {order_id} (type: {type(order_id)})")
        
        try:
            order_info = self.get_order_by_id(order_id)
            if not order_info:
                return {
                    "response_text": f"I couldn't find an order with ID #{order_id}. Could you please check the order number and try again?",
                    "tool_output": None,
                }
            
            # Security check: Verify user has permission to view this order
            if not self._verify_order_access(order_info, user_phone_number):
                # Don't reveal that the order exists but the user doesn't have access
                return {
                    "response_text": f"I'm sorry, I couldn't find an order with ID #{order_id} associated with your phone number. If you believe this is an error, please contact customer support.",
                    "tool_output": None,
                }
                
            # Format a nice response with key order details
            order_status = order_info.get('status', 'unknown')
            order_date = order_info.get('date_created', 'unknown')
            order_total = order_info.get('total', 'unknown')
            
            response_text = f"I found information for order #{order_id}. \n\n" \
                          f"Status: {order_status}\n" \
                          f"Date: {order_date}\n" \
                          f"Total: {order_total}"
            
            return {
                "response_text": response_text,
                "tool_output": order_info,
            }
        except Exception as e:
            print(f"Error in _handle_order_query: {e}")
            return {
                "response_text": f"I'm having trouble retrieving information for order #{order_id}. Please try again later.",
                "tool_output": None,
            }
            
    def _verify_order_access(self, order_info: Dict[str, Any], user_phone_number: str) -> bool:
        """Verify that the user has permission to access this order
        
        Args:
            order_info: The order information from WooCommerce
            user_phone_number: The phone number of the user making the request
            
        Returns:
            bool: True if the user has permission to access this order, False otherwise
        """
        if not user_phone_number:
            print("Security warning: No user phone number provided for order verification")
            return False
            
        # Clean up the phone number for comparison
        # Remove any 'whatsapp:' prefix if present
        if user_phone_number.startswith('whatsapp:'):
            user_phone_number = user_phone_number[9:]
            
        # Normalize phone number by removing non-digit characters
        user_phone_number = ''.join(filter(str.isdigit, user_phone_number))
        
        # Check if the user's phone number matches billing or shipping phone
        billing_phone = order_info.get('billing', {}).get('phone', '')
        shipping_phone = order_info.get('shipping', {}).get('phone', '')
        
        # Normalize order phone numbers
        billing_phone = ''.join(filter(str.isdigit, billing_phone))
        shipping_phone = ''.join(filter(str.isdigit, shipping_phone))
        
        # Try to match the last digits if the numbers are different lengths
        # This helps with country code differences (e.g., +27 vs 0)
        min_match_length = 9  # Match at least the last 9 digits
        
        # Check full match first
        if user_phone_number == billing_phone or user_phone_number == shipping_phone:
            return True
            
        # Check last digits
        if (len(user_phone_number) >= min_match_length and len(billing_phone) >= min_match_length and 
            user_phone_number[-min_match_length:] == billing_phone[-min_match_length:]):
            return True
            
        if (len(user_phone_number) >= min_match_length and len(shipping_phone) >= min_match_length and 
            user_phone_number[-min_match_length:] == shipping_phone[-min_match_length:]):
            return True
            
        # If none of the above conditions match, the user doesn't have permission
        print(f"Security warning: Unauthorized access attempt to order. User phone: {user_phone_number}, Order phones: {billing_phone}/{shipping_phone}")
        return False

    def _handle_product_info(self, message_details: Dict[str, Any]) -> Dict[str, Any]:
        """Handle product info request"""
        product_query = message_details.get(
            "product_name", message_details.get("product_description", "")
        )

        if not product_query:
            return {
                "response_text": "I couldn't identify which product you're asking about. Could you please provide a product name or description?",
                "tool_output": None,
            }

        product_info = self.get_product_names(query=product_query)
        if product_info:
            return {
                "response_text": f"I found these products matching '{product_query}':",
                "tool_output": product_info,
            }
        else:
            return {
                "response_text": f"I couldn't find any products matching '{product_query}'. Could you try a different search term?",
                "tool_output": None,
            }
