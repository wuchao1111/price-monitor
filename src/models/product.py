"""
Product-related data models
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Product(BaseModel):
    """Product model"""
    id: Optional[int] = None
    name: str
    keywords: str
    welfare_policy: Optional[str] = None
    current_lowest_price: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 保价相关字段
    original_price: Optional[float] = None  # 初始团购价格
    original_order_no: Optional[str] = None  # 初始订单号
    original_channel: Optional[str] = None  # 初始购买渠道
    current_guaranteed_price: Optional[float] = None  # 当前已保的最低价格
    pending_guarantee_price: Optional[float] = None  # 待保价（已提交未到账）
    store_activity: Optional[str] = None  # 店铺活动
    group_activity: Optional[str] = None  # 团购活动
    store_activity_claimed: bool = False  # 店铺活动是否已领取
    group_activity_claimed: bool = False  # 团购活动是否已领取


class PriceGuaranteeRecord(BaseModel):
    """Price guarantee record model"""
    id: Optional[int] = None
    product_id: int
    low_price_channel: str  # 低价渠道
    low_price_order_no: Optional[str] = None  # 低价订单号
    low_price: float  # 发现的低价
    guarantee_amount: float  # 保价金额
    status: str = "pending"  # pending:待保价 / confirmed:已保价 / rejected:已拒绝
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    note: Optional[str] = None
