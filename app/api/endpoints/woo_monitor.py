"""
API endpoints for WooCommerce order monitoring and notifications
"""

from typing import Dict, Any, Optional
import hmac
import hashlib
import base64
import json
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel
from app.models.user import Organization
from app.agent.woo_agent import WooAgent
from app.database import get_db
from app.models.service_credential import ServiceCredential, ServiceTypeEnum
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.utils.encryption import decrypt_data

router = APIRouter()

# Store agent instances by organization ID
woo_agent_instances: dict[str, WooAgent] = {}


class WebhookData(BaseModel):
    """Model for incoming WooCommerce webhook data"""

    order: Dict[str, Any]


class PollSettings(BaseModel):
    """Settings for order status polling"""

    interval_minutes: Optional[int] = 15
    enabled: bool = True


async def get_woo_agent(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get or create a WooAgent instance for a specific organization"""
    global woo_agent_instances

    # Check permissions
    if (
        str(current_user.organization_id) != str(organization_id)
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access WooCommerce monitoring for this organization",
        )

    # Return existing instance if available
    if str(organization_id) in woo_agent_instances:
        return woo_agent_instances[str(organization_id)]

    organization_phone_number = (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
        .phone_number
    )

    # Get WooCommerce credentials from database
    creds = (
        db.query(ServiceCredential)
        .filter(
            ServiceCredential.organization_id == organization_id,
            ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
            ServiceCredential.is_active,
        )
        .first()
    )

    if not creds:
        raise HTTPException(
            status_code=404,
            detail="WooCommerce credentials not found. Please set up WooCommerce integration first.",
        )

    # Decrypt the credentials first
    try:
        decrypted_json = decrypt_data(creds.credentials)
        credentials = json.loads(decrypted_json)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing credentials: {e}"
        )

    # Create new agent instance
    woo_agent_instances[str(organization_id)] = WooAgent(
        consumer_key=credentials.get("consumer_key"),
        consumer_secret=credentials.get("consumer_secret"),
        base_url=credentials.get("woo_url"),
        organization_id=str(organization_id),
        organization_phone_number=organization_phone_number,
        webhook_secret=credentials.get("webhook_secret"),
    )

    return woo_agent_instances[str(organization_id)]


async def get_unprotected_woo_agent(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    """Get or create a WooAgent instance for a specific organization without authentication."""
    global woo_agent_instances

    if str(organization_id) in woo_agent_instances:
        return woo_agent_instances[str(organization_id)]

    organization_phone_number = (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
        .phone_number
    )

    creds = (
        db.query(ServiceCredential)
        .filter(
            ServiceCredential.organization_id == organization_id,
            ServiceCredential.service_type == ServiceTypeEnum.WOOCOMMERCE,
            ServiceCredential.is_active,
        )
        .first()
    )

    if not creds:
        raise HTTPException(
            status_code=404,
            detail="WooCommerce credentials not found for this organization.",
        )

    # Decrypt the credentials first
    try:
        decrypted_json = decrypt_data(creds.credentials)
        credentials = json.loads(decrypted_json)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing credentials: {e}"
        )

    woo_agent_instances[str(organization_id)] = WooAgent(
        consumer_key=credentials.get("consumer_key"),
        consumer_secret=credentials.get("consumer_secret"),
        base_url=credentials.get("woo_url"),
        organization_id=str(organization_id),
        organization_phone_number=organization_phone_number,
        webhook_secret=credentials.get("webhook_secret"),
    )

    return woo_agent_instances[str(organization_id)]


@router.post(
    "/webhook/{organization_id}",
    summary="Handle incoming WooCommerce webhooks for order status changes",
    operation_id="woocommerce_webhook",
)
# @router.post("/webhook/{organization_id}")
async def woo_webhook(
    organization_id: UUID, request: Request, db: Session = Depends(get_db)
):
    """
    Process WooCommerce webhooks for order status changes

    This endpoint receives webhooks from WooCommerce when order statuses change
    and sends WhatsApp notifications to customers.
    It also verifies the webhook signature to ensure it's from WooCommerce.
    """
    # print(f"Received webhook for org {organization_id} at URL: {request.url}")
    # print(f"Webhook headers: {request.headers}")

    # Get the WooAgent instance for this organization
    woo_agent = await get_unprotected_woo_agent(organization_id, db)

    # Verify webhook signature
    webhook_secret = woo_agent.credentials.get("webhook_secret")
    raw_body = await request.body()
    print("raw_body", raw_body)

    # Handle WooCommerce test webhooks (they don't have signatures)
    is_test_webhook = raw_body == b"webhook_id=" in raw_body

    if webhook_secret and not is_test_webhook:
        signature = request.headers.get("x-wc-webhook-signature")
        if not signature:
            raise HTTPException(status_code=400, detail="Missing webhook signature")

        expected_signature = base64.b64encode(
            hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        ).decode()

        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    elif is_test_webhook:
        print("Received WooCommerce test webhook - skipping signature verification")

    # Check if body is empty
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty webhook body")

    # Handle test webhooks differently
    if is_test_webhook:
        return {
            "status": "success",
            "message": "WooCommerce test webhook received successfully",
        }

    # Parse webhook data - handle both JSON and form-encoded data
    try:
        # Try JSON first
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        # If not JSON, try form-encoded data
        from urllib.parse import parse_qs

        try:
            decoded_body = raw_body.decode("utf-8")
            # Handle form-encoded data like "webhook_id=12"
            if "=" in decoded_body:
                parsed_data = parse_qs(decoded_body)
                data = {k: v[0] if len(v) == 1 else v for k, v in parsed_data.items()}
            else:
                data = {"raw_data": decoded_body}
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Unable to parse webhook data: {e}"
            )

    result = await woo_agent.process_webhook(data)
    return result


@router.post("/start-polling/{organization_id}")
async def start_polling(
    organization_id: UUID,
    settings: PollSettings,
    background_tasks: BackgroundTasks,
    woo_agent: WooAgent = Depends(get_woo_agent),
):
    """
    Start polling for order status changes

    This endpoint starts a background task that periodically checks for
    order status changes and sends notifications.
    """
    # Update polling interval if provided
    if settings.interval_minutes:
        woo_agent.polling_interval = settings.interval_minutes * 60

    # Start polling in background
    if not woo_agent.is_polling:
        background_tasks.add_task(woo_agent.start_polling)
        return {
            "status": "started",
            "interval_minutes": woo_agent.polling_interval // 60,
        }
    else:
        return {
            "status": "already_running",
            "interval_minutes": woo_agent.polling_interval // 60,
        }


@router.post("/stop-polling/{organization_id}")
async def stop_polling(
    organization_id: UUID, woo_agent: WooAgent = Depends(get_woo_agent)
):
    """
    Stop polling for order status changes
    """
    was_polling = woo_agent.is_polling
    woo_agent.stop_polling()
    return {"status": "stopped" if was_polling else "not_running"}


@router.post("/check-now/{organization_id}")
async def check_now(
    organization_id: UUID, woo_agent: WooAgent = Depends(get_woo_agent)
):
    """
    Manually check for order status changes right now

    This endpoint triggers an immediate check for order status changes
    and sends notifications for any changes found.
    """
    result = await woo_agent.check_and_notify()
    return result


@router.get("/status/{organization_id}")
async def monitoring_status(
    organization_id: UUID, woo_agent: WooAgent = Depends(get_woo_agent)
):
    """
    Get current status of the order monitoring system
    """
    return {
        "is_polling": woo_agent.is_polling,
        "interval_minutes": woo_agent.polling_interval // 60
        if woo_agent.polling_interval
        else None,
        "tracked_orders_count": len(woo_agent.order_status_cache)
        if woo_agent.order_status_cache
        else 0,
    }
