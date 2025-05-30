from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.crud.user import create_user, get_user, get_users, update_user, delete_user
from app.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
def create_new_user(user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)) -> User:
    """Create a new user - super_admin can create anywhere, org_admin can only create within their organization"""
    # Check if user has appropriate permissions
    if current_user.role == "super_admin":
        # Super admin can create users in any organization
        pass
    elif current_user.role == "org_admin":
        # Org admin can only create users in their organization
        if user.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admins can only create users in their own organization"
            )
    else:
        # Regular users cannot create new users
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users"
        )
    
    return create_user(db, user)


@router.get("/{user_id}", response_model=UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)) -> User:
    """Get user by ID - users can only view themselves unless admin"""
    # Regular users can only view their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this user")
        
    db_user = get_user(db, user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.get("/", response_model=List[UserResponse])
def read_users(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
) -> List[User]:
    """Get users - super_admin sees all users, org_admin sees only users in their organization"""
    if current_user.role == "super_admin":
        # Super admin can see all users
        return get_users(db, skip=skip, limit=limit)
    elif current_user.role == "org_admin":
        # Org admin can only see users in their organization
        return db.query(User).filter(User.organization_id == current_user.organization_id).offset(skip).limit(limit).all()
    else:
        # Regular users cannot list all users
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list users"
        )


@router.put("/{user_id}", response_model=UserResponse)
def update_user_endpoint(
    user_id: int, user: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)
) -> User:
    """Update user - users can only update themselves unless admin"""
    # Regular users can only update their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this user")
        
    db_user = update_user(db, user_id, user)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.delete("/{user_id}")
def delete_user_endpoint(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)) -> dict:
    """Delete user - super_admin can delete anyone, org_admin can only delete in their organization"""
    # First, get the user to be deleted
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check permissions
    if current_user.role == "super_admin":
        # Super admin can delete any user
        pass
    elif current_user.role == "org_admin":
        # Org admin can only delete users in their organization
        if user_to_delete.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admins can only delete users in their own organization"
            )
        # Also prevent org admins from deleting other org admins
        if user_to_delete.role == "org_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admins cannot delete other organization admins"
            )
    else:
        # Regular users cannot delete users
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users"
        )
    
    if not delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="Failed to delete user")
    return {"message": "User deleted successfully"}
