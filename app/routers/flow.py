from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.crud import flow as flow_crud
from app.schemas.flow import (
    FlowCreate,
    FlowUpdate,
    FlowPublish,
    FlowResponse,
    FlowListResponse,
)
from app.service.flow_executor import execute_flow
from pydantic import BaseModel

router = APIRouter(prefix="/flows", tags=["flows"])


@router.post(
    "",
    response_model=FlowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new flow",
)
async def create_flow(
    flow: FlowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new flow for the user's organization.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    db_flow = flow_crud.create_flow(db, flow, current_user.organization_id)
    
    return FlowResponse(
        id=str(db_flow.id),
        code=db_flow.code,
        organization_id=str(db_flow.organization_id),
        name=db_flow.name,
        description=db_flow.description,
        nodes=db_flow.nodes,
        edges=db_flow.edges,
        status=db_flow.status,
        is_active=db_flow.is_active,
        trigger_type=db_flow.trigger_type,
        trigger_keywords=db_flow.trigger_keywords,
        created_at=db_flow.created_at,
        updated_at=db_flow.updated_at,
        published_at=db_flow.published_at,
    )


@router.get(
    "",
    response_model=List[FlowListResponse],
    summary="Get all flows for organization",
)
async def get_flows(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all flows for the user's organization.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must belong to an organization",
        )

    flows = flow_crud.get_flows_by_organization(
        db, current_user.organization_id, skip, limit
    )
    
    return [
        FlowListResponse(
            id=str(flow.id),
            code=flow.code,
            name=flow.name,
            description=flow.description,
            status=flow.status,
            is_active=flow.is_active,
            trigger_type=flow.trigger_type,
            created_at=flow.created_at,
            updated_at=flow.updated_at,
        )
        for flow in flows
    ]


@router.get(
    "/{flow_id}",
    response_model=FlowResponse,
    summary="Get a specific flow",
)
async def get_flow(
    flow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific flow by ID.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    return FlowResponse(
        id=str(db_flow.id),
        code=db_flow.code,
        organization_id=str(db_flow.organization_id),
        name=db_flow.name,
        description=db_flow.description,
        nodes=db_flow.nodes,
        edges=db_flow.edges,
        status=db_flow.status,
        is_active=db_flow.is_active,
        trigger_type=db_flow.trigger_type,
        trigger_keywords=db_flow.trigger_keywords,
        created_at=db_flow.created_at,
        updated_at=db_flow.updated_at,
        published_at=db_flow.published_at,
    )


@router.put(
    "/{flow_id}",
    response_model=FlowResponse,
    summary="Update a flow",
)
async def update_flow(
    flow_id: UUID,
    flow_update: FlowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a flow.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    updated_flow = flow_crud.update_flow(db, flow_id, flow_update)
    
    return FlowResponse(
        id=str(updated_flow.id),
        code=updated_flow.code,
        organization_id=str(updated_flow.organization_id),
        name=updated_flow.name,
        description=updated_flow.description,
        nodes=updated_flow.nodes,
        edges=updated_flow.edges,
        status=updated_flow.status,
        is_active=updated_flow.is_active,
        trigger_type=updated_flow.trigger_type,
        trigger_keywords=updated_flow.trigger_keywords,
        created_at=updated_flow.created_at,
        updated_at=updated_flow.updated_at,
        published_at=updated_flow.published_at,
    )


@router.post(
    "/{flow_id}/publish",
    response_model=FlowResponse,
    summary="Publish a flow",
)
async def publish_flow(
    flow_id: UUID,
    publish_data: FlowPublish,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish a flow to make it active.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    published_flow = flow_crud.publish_flow(db, flow_id, publish_data.is_active)
    
    return FlowResponse(
        id=str(published_flow.id),
        code=published_flow.code,
        organization_id=str(published_flow.organization_id),
        name=published_flow.name,
        description=published_flow.description,
        nodes=published_flow.nodes,
        edges=published_flow.edges,
        status=published_flow.status,
        is_active=published_flow.is_active,
        trigger_type=published_flow.trigger_type,
        trigger_keywords=published_flow.trigger_keywords,
        created_at=published_flow.created_at,
        updated_at=published_flow.updated_at,
        published_at=published_flow.published_at,
    )


@router.post(
    "/{flow_id}/archive",
    response_model=FlowResponse,
    summary="Archive a flow",
)
async def archive_flow(
    flow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Archive a flow to deactivate it.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    archived_flow = flow_crud.archive_flow(db, flow_id)
    
    return FlowResponse(
        id=str(archived_flow.id),
        code=archived_flow.code,
        organization_id=str(archived_flow.organization_id),
        name=archived_flow.name,
        description=archived_flow.description,
        nodes=archived_flow.nodes,
        edges=archived_flow.edges,
        status=archived_flow.status,
        is_active=archived_flow.is_active,
        trigger_type=archived_flow.trigger_type,
        trigger_keywords=archived_flow.trigger_keywords,
        created_at=archived_flow.created_at,
        updated_at=archived_flow.updated_at,
        published_at=archived_flow.published_at,
    )


@router.delete(
    "/{flow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a flow",
)
async def delete_flow(
    flow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a flow permanently.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    flow_crud.delete_flow(db, flow_id)
    return None


class FlowTestRequest(BaseModel):
    """Request model for testing a flow"""
    message: str
    phone_number: str = "+1234567890"


class FlowTestResponse(BaseModel):
    """Response model for flow testing"""
    success: bool
    matched: bool
    flow_code: str | None = None
    flow_name: str | None = None
    response_message: str | None = None
    error: str | None = None
    context: dict | None = None


@router.post(
    "/{flow_id}/test",
    response_model=FlowTestResponse,
    summary="Test a flow with a simulated message",
)
async def test_flow(
    flow_id: UUID,
    test_request: FlowTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test a flow by simulating an inbound message.
    This endpoint allows testing flows without sending actual WhatsApp messages.
    """
    db_flow = flow_crud.get_flow(db, flow_id)
    
    if not db_flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found",
        )
    
    # Verify user has access to this flow's organization
    if str(current_user.organization_id) != str(db_flow.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this flow",
        )
    
    try:
        # Execute the flow with test context
        response_message = execute_flow(
            db_flow,
            test_request.message,
            test_request.phone_number
        )
        
        if response_message:
            return FlowTestResponse(
                success=True,
                matched=True,
                flow_code=db_flow.code,
                flow_name=db_flow.name,
                response_message=response_message,
                context={
                    "user_input": test_request.message,
                    "user_phone": test_request.phone_number,
                    "message": test_request.message,
                }
            )
        else:
            return FlowTestResponse(
                success=True,
                matched=False,
                flow_code=db_flow.code,
                flow_name=db_flow.name,
                error="Flow executed but returned no response"
            )
    
    except Exception as e:
        return FlowTestResponse(
            success=False,
            matched=False,
            flow_code=db_flow.code,
            flow_name=db_flow.name,
            error=str(e)
        )
