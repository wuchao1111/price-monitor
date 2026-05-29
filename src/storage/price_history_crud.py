"""
CRUD operations for price_history table
"""
from typing import List
from sqlite3 import Row
from src.storage.database import Database
from src.models.schemas import PriceHistory


class PriceHistoryCRUD:
    """CRUD for price_history table"""

    def __init__(self, db: Database):
        self.db = db

    def _row_to_history(self, row: Row) -> PriceHistory:
        return PriceHistory(
            id=row['id'],
            product_id=row['product_id'],
            price=row['price'],
            source=row['source'],
            queried_at=row['queried_at']
        )

    def create(self, product_id: int, price: float, source: str) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO price_history (product_id, price, source)
            VALUES (?, ?, ?)
            """,
            (product_id, price, source)
        )
        self.db.commit()
        return cursor.lastrowid

    def list_by_product(self, product_id: int, limit: int = 100) -> List[PriceHistory]:
        cursor = self.db.execute(
            """
            SELECT * FROM price_history
            WHERE product_id = ?
            ORDER BY queried_at DESC
            LIMIT ?
            """,
            (product_id, limit)
        )
        rows = cursor.fetchall()
        return [self._row_to_history(row) for row in rows]
