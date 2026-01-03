from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from typing import Any, Dict
from app.database import get_db
from app.auth.dependencies import is_super_admin
from app.models.user import User, Organization
from app.models.whatsapp import WhatsAppUser, WhatsAppMessage, WhatsAppThread
from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_phone_number import WhatsAppPhoneNumber
from app.models.documents import Document, Collection
from app.models.flow import Flow
from app.models.service_credential import ServiceCredential
from app.models.file import File
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])

MODEL_REGISTRY = {
    "users": User,
    "organizations": Organization,
    "whatsapp_users": WhatsAppUser,
    "whatsapp_messages": WhatsAppMessage,
    "whatsapp_threads": WhatsAppThread,
    "whatsapp_accounts": WhatsAppAccount,
    "whatsapp_phone_numbers": WhatsAppPhoneNumber,
    "documents": Document,
    "collections": Collection,
    "flows": Flow,
    "service_credentials": ServiceCredential,
    "files": File,
}

def get_model_metadata(model_class):
    """Extract metadata about a model for the admin interface"""
    mapper = inspect(model_class)
    
    fields = []
    for column in mapper.columns:
        field_info = {
            "name": column.name,
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "unique": column.unique,
            "default": str(column.default) if column.default else None,
        }
        fields.append(field_info)
    
    return {
        "table_name": mapper.local_table.name,
        "fields": fields,
        "display_name": model_class.__name__,
    }

def serialize_value(value):
    """Serialize values for JSON response"""
    if isinstance(value, datetime):
        return value.isoformat()
    elif hasattr(value, '__dict__'):
        return str(value)
    return value

def serialize_record(record):
    """Convert SQLAlchemy record to dict"""
    result = {}
    for column in inspect(record.__class__).columns:
        value = getattr(record, column.name)
        result[column.name] = serialize_value(value)
    return result

@router.get("/models")
async def list_models(
    current_user: User = Depends(is_super_admin),
):
    """List all available models for admin interface"""
    models = []
    for key, model_class in MODEL_REGISTRY.items():
        metadata = get_model_metadata(model_class)
        models.append({
            "key": key,
            "name": metadata["display_name"],
            "table_name": metadata["table_name"],
        })
    return {"models": models}

@router.get("/models/{model_key}")
async def get_model_metadata_endpoint(
    model_key: str,
    current_user: User = Depends(is_super_admin),
):
    """Get detailed metadata about a specific model"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    metadata = get_model_metadata(model_class)
    return metadata

@router.get("/models/{model_key}/records")
async def list_records(
    model_key: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(is_super_admin),
    db: Session = Depends(get_db),
):
    """List records for a specific model with pagination"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    
    total = db.query(model_class).count()
    records = db.query(model_class).offset(skip).limit(limit).all()
    
    serialized_records = [serialize_record(record) for record in records]
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "records": serialized_records,
    }

@router.get("/models/{model_key}/records/{record_id}")
async def get_record(
    model_key: str,
    record_id: str,
    current_user: User = Depends(is_super_admin),
    db: Session = Depends(get_db),
):
    """Get a specific record by ID"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    mapper = inspect(model_class)
    
    primary_key_column = None
    for column in mapper.columns:
        if column.primary_key:
            primary_key_column = column
            break
    
    if not primary_key_column:
        raise HTTPException(status_code=400, detail="Model has no primary key")
    
    record = db.query(model_class).filter(
        getattr(model_class, primary_key_column.name) == record_id
    ).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return serialize_record(record)

@router.put("/models/{model_key}/records/{record_id}")
async def update_record(
    model_key: str,
    record_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(is_super_admin),
    db: Session = Depends(get_db),
):
    """Update a specific record"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    mapper = inspect(model_class)
    
    primary_key_column = None
    for column in mapper.columns:
        if column.primary_key:
            primary_key_column = column
            break
    
    if not primary_key_column:
        raise HTTPException(status_code=400, detail="Model has no primary key")
    
    record = db.query(model_class).filter(
        getattr(model_class, primary_key_column.name) == record_id
    ).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    for key, value in data.items():
        if hasattr(record, key):
            column = None
            for col in mapper.columns:
                if col.name == key:
                    column = col
                    break
            
            if column and not column.primary_key:
                if value is not None and 'DateTime' in str(column.type):
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                
                setattr(record, key, value)
    
    try:
        db.commit()
        db.refresh(record)
        return serialize_record(record)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update record: {str(e)}")

@router.delete("/models/{model_key}/records/{record_id}")
async def delete_record(
    model_key: str,
    record_id: str,
    current_user: User = Depends(is_super_admin),
    db: Session = Depends(get_db),
):
    """Delete a specific record"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    mapper = inspect(model_class)
    
    primary_key_column = None
    for column in mapper.columns:
        if column.primary_key:
            primary_key_column = column
            break
    
    if not primary_key_column:
        raise HTTPException(status_code=400, detail="Model has no primary key")
    
    record = db.query(model_class).filter(
        getattr(model_class, primary_key_column.name) == record_id
    ).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    try:
        db.delete(record)
        db.commit()
        return {"message": "Record deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to delete record: {str(e)}")

@router.post("/models/{model_key}/records")
async def create_record(
    model_key: str,
    data: Dict[str, Any],
    current_user: User = Depends(is_super_admin),
    db: Session = Depends(get_db),
):
    """Create a new record"""
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_class = MODEL_REGISTRY[model_key]
    mapper = inspect(model_class)
    
    filtered_data = {}
    for key, value in data.items():
        if hasattr(model_class, key):
            column = None
            for col in mapper.columns:
                if col.name == key:
                    column = col
                    break
            
            if column and not column.primary_key:
                if value is not None and 'DateTime' in str(column.type):
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                
                filtered_data[key] = value
    
    try:
        record = model_class(**filtered_data)
        db.add(record)
        db.commit()
        db.refresh(record)
        return serialize_record(record)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create record: {str(e)}")
