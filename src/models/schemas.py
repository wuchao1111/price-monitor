"""
Data models - re-exports from domain modules for backward compatibility
"""
from src.models.product import Product, PriceGuaranteeRecord
from src.models.price import (
    PriceResult,
    PriceHistory,
    PriceCompareResult,
    FilteredResult,
)
from src.models.other import (
    ChangeLog,
    NotificationRequest,
    AgentResponse,
)
