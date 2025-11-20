from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.models.flow import Flow
from app.schemas.flow import FlowCreate, FlowUpdate


def create_flow(db: Session, flow: FlowCreate, organization_id: UUID) -> Flow:
    """Create a new flow"""
    db_flow = Flow(
        organization_id=organization_id,
        name=flow.name,
        description=flow.description,
        nodes=flow.nodes,
        edges=flow.edges,
        trigger_type=flow.trigger_type,
        trigger_keywords=flow.trigger_keywords,
    )
    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)
    return db_flow


def get_flow(db: Session, flow_id: UUID) -> Optional[Flow]:
    """Get a flow by ID"""
    return db.query(Flow).filter(Flow.id == flow_id).first()


def get_flows_by_organization(
    db: Session, organization_id: UUID, skip: int = 0, limit: int = 100
) -> List[Flow]:
    """Get all flows for an organization"""
    return (
        db.query(Flow)
        .filter(Flow.organization_id == organization_id)
        .order_by(Flow.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_active_flows_by_organization(
    db: Session, organization_id: UUID
) -> List[Flow]:
    """Get all active published flows for an organization"""
    return (
        db.query(Flow)
        .filter(
            Flow.organization_id == organization_id,
            Flow.status == Flow.STATUS["PUBLISHED"],
            Flow.is_active == True,
        )
        .all()
    )


def update_flow(db: Session, flow_id: UUID, flow_update: FlowUpdate) -> Optional[Flow]:
    """Update a flow"""
    db_flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not db_flow:
        return None

    update_data = flow_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_flow, field, value)

    db_flow.updated_at = datetime.now()
    db.commit()
    db.refresh(db_flow)
    return db_flow


def publish_flow(db: Session, flow_id: UUID, is_active: bool = True) -> Optional[Flow]:
    """Publish a flow"""
    db_flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not db_flow:
        return None

    db_flow.status = Flow.STATUS["PUBLISHED"]
    db_flow.is_active = is_active
    db_flow.published_at = datetime.now()
    db_flow.updated_at = datetime.now()
    
    db.commit()
    db.refresh(db_flow)
    return db_flow


def archive_flow(db: Session, flow_id: UUID) -> Optional[Flow]:
    """Archive a flow"""
    db_flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not db_flow:
        return None

    db_flow.status = Flow.STATUS["ARCHIVED"]
    db_flow.is_active = False
    db_flow.updated_at = datetime.now()
    
    db.commit()
    db.refresh(db_flow)
    return db_flow


def delete_flow(db: Session, flow_id: UUID) -> bool:
    """Delete a flow"""
    db_flow = db.query(Flow).filter(Flow.id == flow_id).first()
    if not db_flow:
        return False

    db.delete(db_flow)
    db.commit()
    return True


def match_flow_trigger(
    db: Session, organization_id: UUID, message_text: str
) -> Optional[Flow]:
    """
    Match an incoming message to a flow trigger.
    Returns the first matching active flow.
    """
    active_flows = get_active_flows_by_organization(db, organization_id)
    
    message_lower = message_text.lower().strip()
    
    for flow in active_flows:
        # Match keyword triggers
        if flow.trigger_type == "keyword" and flow.trigger_keywords:
            for keyword in flow.trigger_keywords:
                if keyword.lower() in message_lower:
                    return flow
        
        # Match any_message triggers (lowest priority)
        elif flow.trigger_type == "any_message":
            return flow
    
    return None
