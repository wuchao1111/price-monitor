"""
CRUD operations for change_log table
"""
from typing import List
from sqlite3 import Row
from src.storage.database import Database
from src.models.schemas import ChangeLog


class ChangeLogCRUD:
    """CRUD for change_log table"""

    def __init__(self, db: Database):
        self.db = db

    def _row_to_changelog(self, row: Row) -> ChangeLog:
        return ChangeLog(
            id=row['id'],
            product_id=row['product_id'],
            old_price=row['old_price'],
            new_price=row['new_price'],
            changed_by=row['changed_by'],
            changed_at=row['changed_at'],
            note=row['note']
        )

    def list_by_product(self, product_id: int, limit: int = 100) -> List[ChangeLog]:
        cursor = self.db.execute(
            """
            SELECT * FROM change_log
            WHERE product_id = ?
            ORDER BY changed_at DESC
            LIMIT ?
            """,
            (product_id, limit)
        )
        rows = cursor.fetchall()
        return [self._row_to_changelog(row) for row in rows]
