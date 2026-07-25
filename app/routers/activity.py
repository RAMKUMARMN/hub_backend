import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.security.dependencies import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/activity", tags=["activity"])

def map_audit_log_to_activity(log: AuditLog):
    # Mapping resource to type expected by frontend
    resource_map = {
        "todo": "task",
        "chat": "chat",
        "chat_session": "chat",
        "note": "note",
        "document": "document",
        "event": "event",
        "calendar_event": "event",
        "focus": "task",
        "focus_session": "task",
    }
    activity_type = resource_map.get(log.resource.lower(), "default")
    
    action = log.action.lower()
    resource = log.resource.lower().replace("_", " ")
    
    # Attempt to extract title/name from details/metadata
    title = None
    if isinstance(log.details, dict):
        title = log.details.get("title") or log.details.get("name")
        
    if title:
        desc = f"{action.capitalize()}d {resource}: '{title}'"
    else:
        # Verb mapping
        verb = action
        if action == "create":
            verb = "created"
        elif action == "update":
            verb = "updated"
        elif action == "delete":
            verb = "deleted"
        elif action == "complete":
            verb = "completed"
        elif action == "start":
            verb = "started"
        elif action == "share":
            verb = "shared"
        elif action == "login":
            verb = "logged in to"
            resource = "account"
        
        desc = f"{verb.capitalize()} a {resource}"
        
    return {
        "id": str(log.id),
        "type": activity_type,
        "description": desc,
        "timestamp": log.created_at,
    }

@router.get("")
async def get_activity_feed(
    limit: int = Query(8, description="Max activities to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the activity feed for the logged in user, mapped to the frontend expected format.
    """
    try:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == current_user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [map_audit_log_to_activity(log) for log in logs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
