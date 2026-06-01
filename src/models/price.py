"""
Price-related data models
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PriceResult(BaseModel):
    """Result from a skill price query"""
    price: float
    product_name: str
    source: str  # skill name
    url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PriceHistory(BaseModel):
    """Price history record"""
    id: Optional[int] = None
    product_id: int
    price: float
    source: str
    queried_at: Optional[datetime] = None


class PriceCompareResult(BaseModel):
    """Result of price comparison"""
    product_id: int
    product_name: str
    current_lowest: Optional[float]
    latest_price: float
    is_new_lowest: bool
    source: str
    all_prices: List[PriceResult]


class FilteredResult(BaseModel):
    """Result of relevance filtering"""
    keyword: str
    kept: List[PriceResult]
    filtered: List[PriceResult]
    filtered_details: List[dict] = []  # [{"title": str, "reason": str}, ...]
