"""
Price Comparator - compares latest price with current lowest
"""
from typing import List, Optional
from logging import getLogger
from src.models.schemas import Product, PriceResult, PriceCompareResult
from src.storage import PriceHistoryCRUD, ProductCRUD

logger = getLogger(__name__)


class PriceComparator:
    """Price comparison service"""

    def __init__(
        self,
        product_crud: ProductCRUD,
        price_history_crud: PriceHistoryCRUD
    ):
        self.product_crud = product_crud
        self.price_history_crud = price_history_crud

    def compare(
        self,
        product: Product,
        latest_prices: List[PriceResult]
    ) -> Optional[PriceCompareResult]:
        """
        Compare latest prices with current lowest price

        Args:
            product: Product to compare
            latest_prices: List of latest price results from skills

        Returns:
            PriceCompareResult if we have any valid prices, None otherwise
        """
        if not latest_prices:
            logger.warning(f"No prices obtained for product {product.id} ({product.name})")
            return None

        # Find the cheapest price from latest results
        latest_prices.sort(key=lambda x: x.price)
        cheapest = latest_prices[0]
        latest_price = cheapest.price

        # Record all prices in history
        for result in latest_prices:
            self.price_history_crud.create(product.id, result.price, result.source)

        current_lowest = product.current_lowest_price
        is_new_lowest = False

        if current_lowest is None:
            # No previous price, any price is a new lowest
            is_new_lowest = True
        else:
            if latest_price < current_lowest:
                is_new_lowest = True

        logger.info(
            f"Product {product.id} ({product.name}): "
            f"current={current_lowest}, latest={latest_price}, is_new_lowest={is_new_lowest}"
        )

        return PriceCompareResult(
            product_id=product.id,
            product_name=product.name,
            current_lowest=current_lowest,
            latest_price=latest_price,
            is_new_lowest=is_new_lowest,
            source=cheapest.source,
            all_prices=latest_prices
        )
