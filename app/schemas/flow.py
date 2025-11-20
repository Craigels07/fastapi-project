from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class FlowNodeBase(BaseModel):
    """Base schema for flow nodes"""
    id: str
    type: str
    data: Dict[str, Any]
    position: Dict[str, float]


class FlowEdgeBase(BaseModel):
    """Base schema for flow edges"""
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None


class FlowCreate(BaseModel):
    """Schema for creating a new flow"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    trigger_type: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None


class FlowUpdate(BaseModel):
    """Schema for updating a flow"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    trigger_type: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    is_active: Optional[bool] = None


class FlowPublish(BaseModel):
    """Schema for publishing a flow"""
    is_active: bool = True


class FlowResponse(BaseModel):
    """Schema for flow response"""
    id: str
    code: str
    organization_id: str
    name: str
    description: Optional[str]
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    status: str
    is_active: bool
    trigger_type: Optional[str]
    trigger_keywords: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime]

    class Config:
        from_attributes = True


class FlowListResponse(BaseModel):
    """Schema for flow list item"""
    id: str
    code: str
    name: str
    description: Optional[str]
    status: str
    is_active: bool
    trigger_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
