import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.service.woo.client import WooCommerceAPIClient
from app.helpers.whatsapp_helper import send_whatsapp_message, get_tools
from app.agent.models import WhatsAppMessageState
from app.agent.woo_agent_helpers import enhanced_agent_workflow_node

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
WOO_COMMERCE_BASE_URL = os.getenv("WOO_COMMERCE_BASE_URL")


# Path to store order status cache
def get_cache_path(organization_id):
    """Generate organization-specific cache path"""
    filename = (
        f"order_status_cache_{organization_id}.json"
        if organization_id
        else "order_status_cache.json"
    )
    return os.path.join(os.path.dirname(__file__), "../..", "data", filename)


# Status notification map - map of statuses and their friendly descriptions
STATUS_NOTIFICATIONS = {
    "pending": "We've received your order and are processing it.",
    "processing": "Your order is being prepared.",
    "on-hold": "Your order is currently on hold. Our team will contact you shortly.",
    "completed": "Your order has been completed and shipped! It's on its way to you.",
    "cancelled": "Your order has been cancelled. If you have any questions, please contact us.",
    "refunded": "Your order has been refunded. The amount should appear in your account within a few days.",
    "failed": "There was an issue processing your order. Please contact our support team.",
    "trash": "Your order has been removed.",
    "packed": "Good news! Your order has been packed and is ready for shipping.",
    "shipped": "Your order is on the way! You should receive it soon.",
}


class WooAgent:
    """
    Agent for handling WooCommerce operations including order status monitoring
    and sending customer notifications via WhatsApp.
    """

    def __init__(
        self,
        consumer_key=None,
        consumer_secret=None,
        base_url=None,
        model=None,
        organization_id=None,
        organization_phone_number=None,
        webhook_secret=None,
    ):
        # Initialize WooCommerce client if credentials are provided
        if consumer_key and consumer_secret and base_url:
            self.woo_client = WooCommerceAPIClient(
                base_url=base_url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
            )
        else:
            self.woo_client = None

        # Save organization and model info
        self.organization_id = organization_id
        self.organization_phone_number = organization_phone_number
        self.model = model or ChatOpenAI(
            model_name="gpt-4o-mini", temperature=0.8
        )  # Higher temperature for more human-like variation

        # Load or initialize order status cache
        self.order_status_cache = self._load_order_status_cache()

        # Configure the agent workflow
        self.config = {
            "configurable": {
                "model": self.model,
                "tools": get_tools(),
                "woo_client": self.woo_client,
                "organization_id": self.organization_id,
                "organization_phone_number": self.organization_phone_number,
            }
        }
        self.workflow = self._build_agent()

        # Polling settings
        self.polling_interval = 15 * 60  # 15 minutes in seconds
        self.is_polling = False
        self.polling_task = None
        self.webhook_secret = webhook_secret

        # Create data directory if it doesn't exist
        os.makedirs(
            os.path.dirname(get_cache_path(self.organization_id)), exist_ok=True
        )

    @property
    def credentials(self) -> Dict[str, Any]:
        """Return the credentials used by the agent."""
        return {
            # "consumer_key": self.woo_client.consumer_key if self.woo_client else None,
            # "consumer_secret": self.woo_client.consumer_secret
            # if self.woo_client
            # else None,
            # "base_url": self.woo_client.base_url if self.woo_client else None,
            "webhook_secret": self.webhook_secret,
        }

    def _load_order_status_cache(self):
        """Load the organization-specific order status cache from disk or create a new one if it doesn't exist."""
        # Get organization-specific cache path
        cache_path = get_cache_path(self.organization_id)

        # Make sure data directory exists
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logging.error(
                f"Error loading order status cache for org {self.organization_id}: {e}"
            )
            return {}

    def _save_order_status_cache(self):
        """Save the current organization-specific order status cache to disk."""
        try:
            # Get organization-specific cache path
            cache_path = get_cache_path(self.organization_id)
            with open(cache_path, "w") as f:
                json.dump(self.order_status_cache, f)
        except Exception as e:
            logging.error(
                f"Error saving order status cache for org {self.organization_id}: {e}"
            )

    def _check_order_status_changes(self, orders):
        """Check for order status changes and return a list of changed orders.

        Args:
            orders (list): List of order objects from WooCommerce API

        Returns:
            list: Orders with status changes
        """
        changed_orders = []
        current_time = datetime.now().isoformat()

        for order in orders:
            order_id = str(order.get("id"))
            current_status = order.get("status")
            customer_phone = self._get_customer_phone(order)

            # Skip if we can't notify the customer
            if not customer_phone:
                continue

            # Check if order exists in cache
            if order_id in self.order_status_cache:
                cached_status = self.order_status_cache[order_id]["status"]

                # If status has changed, add to changed_orders
                if current_status != cached_status:
                    changed_orders.append(
                        {
                            "order": order,
                            "previous_status": cached_status,
                            "current_status": current_status,
                            "customer_phone": customer_phone,
                        }
                    )

                    # Update cache with new status
                    self.order_status_cache[order_id] = {
                        "status": current_status,
                        "last_updated": current_time,
                    }
            else:
                # New order, add to cache
                self.order_status_cache[order_id] = {
                    "status": current_status,
                    "last_updated": current_time,
                }

                # If it's a new order and not 'pending', add to changed_orders
                # This ensures we don't spam customers with 'pending' notifications
                # for all new orders we start tracking
                if current_status not in ["pending"]:
                    changed_orders.append(
                        {
                            "order": order,
                            "previous_status": None,
                            "current_status": current_status,
                            "customer_phone": customer_phone,
                        }
                    )

        # Save updated cache
        if changed_orders:
            self._save_order_status_cache()

        return changed_orders

    def _build_agent(self):
        """
        Build and return the enhanced workflow for the Woo agent.
        """
        workflow = StateGraph(WhatsAppMessageState)

        workflow.add_node("agent", enhanced_agent_workflow_node)
        workflow.set_entry_point("agent")
        workflow.add_edge("agent", END)

        # The checkpointer is now managed in the `run` method, so we don't pass it here.
        return workflow.compile()

    async def run(
        self, user_input: str, whatsapp_message_id: str, user_phone_number: str
    ) -> Dict[str, Any]:
        """
        Run the RAG agent asynchronously on a list of messages.
        Uses an async Postgres checkpointer and connection pool.
        """
        # Import necessary type annotations

        # Prepare database connection arguments
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }

        # Ensure DATABASE_URL is not None
        if DATABASE_URL is None:
            raise ValueError("DATABASE_URL environment variable is not set")

        # Create connection pool with explicit type
        async with AsyncConnectionPool(
            conninfo=str(DATABASE_URL),  # Explicit cast to str for mypy
            max_size=10,
            kwargs=connection_kwargs,
        ) as connection_pool:

            checkpointer = AsyncPostgresSaver(connection_pool)
            await checkpointer.setup()

            # Compile the graph with the checkpointer
            compiled_graph = self.workflow.compile(checkpointer=checkpointer)

            # Create initial state with user input and phone number
            initial_state = {
                "received_message": user_input,
                "whatsapp_message_id": whatsapp_message_id,
                "organization_id": self.organization_id,
                "user_phone_number": user_phone_number,
            }

            config = self.config.copy()
            config["configurable"] = self.config["configurable"].copy()
            config["configurable"]["thread_id"] = f"whatsapp_{user_phone_number}"

            # Invoke the graph with the initial state
            result = await compiled_graph.ainvoke(initial_state, config=config)

            # Return the final result
            return result

    def _prepare_order_data_for_agent(self, order, status):
        """Prepare comprehensive order data for the LLM agent.

        Args:
            order (dict): Order object from WooCommerce API
            status (str): Current order status

        Returns:
            dict: Structured order data for agent processing
        """
        # Extract customer information
        customer_info = {
            "name": "valued customer",
            "email": None,
            "phone": self._get_customer_phone(order),
        }

        if "billing" in order:
            billing = order["billing"]
            if billing.get("first_name"):
                customer_info["name"] = billing["first_name"]
                if billing.get("last_name"):
                    customer_info["name"] += f" {billing['last_name']}"
            customer_info["email"] = billing.get("email")
            if not customer_info["phone"]:
                customer_info["phone"] = billing.get("phone")

        # Extract order details
        order_details = {
            "id": order.get("id"),
            "number": order.get("number", order.get("id", "unknown")),
            "status": status,
            "previous_status": self.order_status_cache.get(
                str(order.get("id", "")), {}
            ).get("status"),
            "total": order.get("total"),
            "currency": order.get("currency"),
            "date_created": order.get("date_created"),
            "date_modified": order.get("date_modified"),
        }

        # Extract line items
        line_items = []
        if "line_items" in order:
            for item in order["line_items"]:
                line_items.append(
                    {
                        "name": item.get("name"),
                        "quantity": item.get("quantity"),
                        "price": item.get("price"),
                        "total": item.get("total"),
                    }
                )

        # Extract shipping information
        shipping_info = {}
        if "shipping" in order:
            shipping = order["shipping"]
            shipping_info = {
                "first_name": shipping.get("first_name"),
                "last_name": shipping.get("last_name"),
                "address_1": shipping.get("address_1"),
                "address_2": shipping.get("address_2"),
                "city": shipping.get("city"),
                "state": shipping.get("state"),
                "postcode": shipping.get("postcode"),
                "country": shipping.get("country"),
            }

        # Extract meta data for additional information
        meta_data = {}
        if "meta_data" in order:
            for meta in order["meta_data"]:
                key = meta.get("key", "")
                if key.startswith("_estimated_delivery"):
                    meta_data["estimated_delivery"] = meta.get("value")
                elif key.startswith("_tracking"):
                    meta_data["tracking_number"] = meta.get("value")
                elif key.startswith("_delivery"):
                    meta_data["delivery_notes"] = meta.get("value")

        return {
            "customer": customer_info,
            "order": order_details,
            "items": line_items,
            "shipping": shipping_info,
            "meta": meta_data,
            "status_description": STATUS_NOTIFICATIONS.get(
                status, f"Order status: {status}"
            ),
        }

    def _create_notification_prompt(self, order_data, status):
        """Create a detailed prompt for the LLM to generate professional notifications.

        Args:
            order_data (dict): Structured order data
            status (str): Current order status

        Returns:
            str: Detailed prompt for the LLM
        """
        customer_name = order_data["customer"]["name"]
        order_number = order_data["order"]["number"]

        prompt = f"""Generate a professional and personalized WhatsApp message for a WooCommerce order status update.

Customer Information:
- Name: {customer_name}
- Phone: {order_data["customer"]["phone"]}
- Email: {order_data["customer"]["email"]}

Order Information:
- Order Number: #{order_number}
- Status: {status}
- Previous Status: {order_data["order"]["previous_status"]}
- Total: {order_data["order"]["currency"]} {order_data["order"]["total"]}
- Date Created: {order_data["order"]["date_created"]}

Items Ordered:
{self._format_items_for_prompt(order_data["items"])}

Shipping Address:
{self._format_shipping_for_prompt(order_data["shipping"])}

Additional Information:
{self._format_meta_for_prompt(order_data["meta"])}

Status Description: {order_data["status_description"]}

Please generate a warm, professional, and personalized WhatsApp message that:
1. Addresses the customer by name
2. References their specific order number
3. Clearly communicates the status update
4. Includes relevant details based on the status (delivery info for shipped orders, etc.)
5. Maintains a friendly but professional tone
6. Is concise but informative (under 200 words)
7. Includes a call-to-action or next steps if appropriate
8. Uses emojis sparingly and appropriately for WhatsApp
9. Ends with gratitude and contact information if needed

The message should be ready to send directly to the customer via WhatsApp."""

        return prompt

    def _format_items_for_prompt(self, items):
        """Format order items for the prompt."""
        if not items:
            return "No items found"

        formatted_items = []
        for item in items[:3]:  # Limit to first 3 items to keep prompt concise
            formatted_items.append(f"- {item['name']} (Qty: {item['quantity']})")

        if len(items) > 3:
            formatted_items.append(f"... and {len(items) - 3} more items")

        return "\n".join(formatted_items)

    def _format_shipping_for_prompt(self, shipping):
        """Format shipping information for the prompt."""
        if not shipping or not any(shipping.values()):
            return "No shipping address provided"

        address_parts = []
        if shipping.get("address_1"):
            address_parts.append(shipping["address_1"])
        if shipping.get("city"):
            address_parts.append(shipping["city"])
        if shipping.get("state"):
            address_parts.append(shipping["state"])
        if shipping.get("postcode"):
            address_parts.append(shipping["postcode"])

        return ", ".join(address_parts) if address_parts else "Address not complete"

    def _format_meta_for_prompt(self, meta):
        """Format meta data for the prompt."""
        if not meta:
            return "No additional information"

        info_parts = []
        if meta.get("estimated_delivery"):
            info_parts.append(f"Estimated Delivery: {meta['estimated_delivery']}")
        if meta.get("tracking_number"):
            info_parts.append(f"Tracking Number: {meta['tracking_number']}")
        if meta.get("delivery_notes"):
            info_parts.append(f"Delivery Notes: {meta['delivery_notes']}")

        return "\n".join(info_parts) if info_parts else "No additional information"

    def _generate_fallback_notification(self, order, status):
        """Generate a simple fallback notification if LLM generation fails."""
        # Get customer name
        customer_name = "valued customer"
        if "billing" in order and "first_name" in order["billing"]:
            customer_name = order["billing"]["first_name"]

        # Get order number
        order_number = order.get("number", order.get("id", "unknown"))

        # Get status message
        status_message = STATUS_NOTIFICATIONS.get(
            status, f"Your order status is now: {status}"
        )

        # Compose simple message
        message = f"Hi {customer_name}! 👋\n\n"
        message += f"Your order #{order_number} update: {status_message}\n\n"

        # Add order details for completed/shipped orders
        if status in ["completed", "shipped"]:
            message += "🚚 Your order is on its way!\n"
            # Add estimated delivery date if available
            if "meta_data" in order:
                for meta in order["meta_data"]:
                    if meta.get("key") == "_estimated_delivery":
                        delivery_date = meta.get("value")
                        message += f"📅 Estimated delivery: {delivery_date}\n"
                        break

        message += "\nThank you for your business! 🙏"
        return message

    async def _generate_status_notification(self, order, status):
        """Generate a personalized status update notification using LLM agent.

        Args:
            order (dict): Order object from WooCommerce API
            status (str): Current order status

        Returns:
            str: Personalized message for the customer generated by LLM
        """
        try:
            # Prepare comprehensive order data for the agent
            order_data = self._prepare_order_data_for_agent(order, status)

            # Create a prompt for the agent to generate a professional notification
            notification_prompt = self._create_notification_prompt(order_data, status)

            # Create initial state for notification generation
            initial_state = {
                "received_message": notification_prompt,
                "whatsapp_message_id": f"notification_{order.get('id', 'unknown')}",
                "organization_id": self.organization_id,
                "user_phone_number": self._get_customer_phone(order) or "unknown",
                "messagePurpose": "order_status_notification",
                "messageDetails": {"order_id": order.get("id"), "status": status},
            }

            # Use the existing agent workflow for generation
            config = self.config.copy()
            config["configurable"] = self.config["configurable"].copy()
            config["configurable"]["thread_id"] = (
                f"notification_{order.get('id', 'unknown')}"
            )

            # Use the same connection configuration as the working RAG agent
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }

            if DATABASE_URL is None:
                # Fallback to simple message generation if no database
                return self._generate_fallback_notification(order, status)

            async with AsyncConnectionPool(
                conninfo=str(DATABASE_URL),
                max_size=5,
                kwargs=connection_kwargs,
            ) as connection_pool:
                # Setup the checkpointer
                checkpointer = AsyncPostgresSaver(connection_pool)
                await checkpointer.setup()
                
                # We need to recompile the workflow with the checkpointer
                # but use our existing workflow definition
                workflow = StateGraph(WhatsAppMessageState)
                workflow.add_node("agent", enhanced_agent_workflow_node)
                workflow.set_entry_point("agent")
                workflow.add_edge("agent", END)
                
                # Now compile with the checkpointer
                compiled_graph = workflow.compile(checkpointer=checkpointer)
                
                # Invoke the newly compiled graph
                result = await compiled_graph.ainvoke(
                    initial_state, 
                    config=config
                )
                
                return result.get(
                    "final_message", self._generate_fallback_notification(order, status)
                )

        except Exception as e:
            logging.error(f"Error generating LLM notification: {e}")
            return self._generate_fallback_notification(order, status)

    def _get_customer_phone(self, order):
        """Extract customer phone number from WooCommerce order data.

        Args:
            order (dict): Order object from WooCommerce API

        Returns:
            str or None: Customer phone number if found, None otherwise
        """
        # Try billing phone first
        if "billing" in order and "phone" in order["billing"]:
            phone = order["billing"]["phone"]
            if phone and phone.strip():
                return phone.strip()

        # Try shipping phone as fallback
        if "shipping" in order and "phone" in order["shipping"]:
            phone = order["shipping"]["phone"]
            if phone and phone.strip():
                return phone.strip()

        # Try meta data for custom phone fields
        if "meta_data" in order:
            for meta in order["meta_data"]:
                key = meta.get("key", "")
                if "phone" in key.lower() or "mobile" in key.lower():
                    phone = meta.get("value")
                    if phone and str(phone).strip():
                        return str(phone).strip()

        return None

    async def send_status_notification(self, order, status):
        """Send a WhatsApp notification for an order status update.

        Args:
            order (dict): Order object from WooCommerce API
            status (str): The current order status

        Returns:
            dict: Result of the WhatsApp send operation
        """
        # Get customer phone
        customer_phone = self._get_customer_phone(order)
        if not customer_phone:
            logging.warning(f"No phone number found for order {order.get('id')}")
            return {"error": "No phone number found"}

        # Generate notification message
        message = await self._generate_status_notification(order, status)

        # Create WhatsApp message state
        state = {"final_message": message, "user_phone_number": customer_phone}

        # Create config with organization phone
        config = {
            "configurable": {
                "organization_phone_number": self.organization_phone_number
            }
        }

        # Send the message
        try:
            result = send_whatsapp_message(state, config)
            logging.info(
                f"Sent status notification for order {order.get('id')} to {customer_phone}"
            )
            return result
        except Exception as e:
            logging.error(f"Error sending status notification: {e}")
            return {"error": str(e)}

    async def check_and_notify(self):
        """Check for order status changes and send notifications."""
        if not self.woo_client:
            logging.error("WooCommerce client not initialized")
            return

        try:
            # Get recent orders from last 24 hours
            orders = self.woo_client.get_recent_orders(hours=24)

            # Check for status changes
            changed_orders = self._check_order_status_changes(orders)

            # Send notifications for changed orders
            for change in changed_orders:
                order = change["order"]
                status = change["current_status"]
                await self.send_status_notification(order, status)

            return {"checked": len(orders), "notifications_sent": len(changed_orders)}
        except Exception as e:
            logging.error(f"Error checking order statuses: {e}")
            return {"error": str(e)}

    async def _polling_loop(self):
        """Background polling loop for order status changes."""
        while self.is_polling:
            try:
                result = await self.check_and_notify()
                logging.info(f"Polling result: {result}")
            except Exception as e:
                logging.error(f"Error in polling loop: {e}")

            # Wait for next polling interval
            await asyncio.sleep(self.polling_interval)

    def start_polling(self):
        """Start the background polling for order status changes."""
        if self.is_polling:
            logging.warning("Polling already started")
            return

        self.is_polling = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        logging.info(
            f"Started order status polling (interval: {self.polling_interval} seconds)"
        )

    def stop_polling(self):
        """Stop the background polling for order status changes."""
        if not self.is_polling:
            logging.warning("Polling not started")
            return

        self.is_polling = False
        if self.polling_task:
            self.polling_task.cancel()
            self.polling_task = None
        logging.info("Stopped order status polling")

    async def process_webhook(self, webhook_data):
        """Process WooCommerce webhook data for order status changes.

        This method can be used if you set up webhooks in WooCommerce to notify
        when order statuses change, as an alternative to polling.

        Args:
            webhook_data (dict): Webhook payload from WooCommerce

        Returns:
            dict: Result of notification operation
        """
        try:
            # Extract order data from webhook
            order = webhook_data.get("order", webhook_data)
            order_id = str(order.get("id"))
            print("order_id", order_id)
            new_status = order.get("status")
            print("new_status", new_status)

            if not order_id or not new_status:
                return {"error": "Invalid webhook data"}

            # Get previous status from cache
            previous_status = None
            if order_id in self.order_status_cache:
                previous_status = self.order_status_cache[order_id]["status"]
                print("previous_status", previous_status)

            # Update cache
            self.order_status_cache[order_id] = {
                "status": new_status,
                "last_updated": datetime.now().isoformat(),
            }
            self._save_order_status_cache()

            # Send notification if status changed
            if new_status != previous_status:
                return await self.send_status_notification(order, new_status)
            else:
                return {"status": "unchanged"}
        except Exception as e:
            logging.error(f"Error processing webhook: {e}")
            return {"error": str(e)}
