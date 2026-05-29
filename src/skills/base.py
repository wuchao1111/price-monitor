"""
Base Skill interface definition
All skills must inherit from this class
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.models.schemas import PriceResult


class BaseSkill(ABC):
    """Base abstract class for all price query skills"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill name, used for registration and identification"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Skill description for humans"""
        pass

    @abstractmethod
    async def query_price(self, keyword: str) -> List[PriceResult]:
        """
        Query price by keyword

        Args:
            keyword: Search keyword (product name or keywords)

        Returns:
            List of PriceResult, sorted by price ascending (cheapest first)
        """
        pass

    def is_supported(self, keyword: str) -> bool:
        """
        Check if this skill supports the given keyword.
        Override this for platform-specific routing optimization.

        Args:
            keyword: Search keyword

        Returns:
            True if supported, False otherwise
        """
        return True

    @property
    def enabled(self) -> bool:
        """Whether this skill is enabled"""
        return True
