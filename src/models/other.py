"""
Other data models (change log, notification, agent response)
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChangeLog(BaseModel):
    """Change log for lowest price updates"""
    id: Optional[int] = None
    product_id: int
    old_price: Optional[float]
    new_price: float
    changed_by: str  # 'user' or 'system'
    changed_at: Optional[datetime] = None
    note: Optional[str] = None


class NotificationRequest(BaseModel):
    """Notification request"""
    product_id: int
    product_name: str
    old_price: Optional[float]
    new_price: float
    source: str
    confirm_command: str


class AgentResponse(BaseModel):
    """Agent response to user"""
    message: str
    success: bool = True
    data: Optional[dict] = None
