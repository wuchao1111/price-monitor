"""
CRUD operations for price_guarantee_records table
"""
from typing import List, Optional
from sqlite3 import Row
from src.storage.database import Database
from src.models.schemas import PriceGuaranteeRecord


class PriceGuaranteeCRUD:
    """CRUD for price_guarantee_records table"""

    def __init__(self, db: Database):
        self.db = db

    def _row_to_record(self, row: Row) -> PriceGuaranteeRecord:
        record = PriceGuaranteeRecord(
            id=row['id'],
            product_id=row['product_id'],
            low_price_channel=row['low_price_channel'],
            low_price=row['low_price'],
            guarantee_amount=row['guarantee_amount'],
            status=row['status']
        )
        for col in ['low_price_order_no', 'submitted_at', 'confirmed_at', 'note']:
            if col in row.keys():
                setattr(record, col, row[col])
        return record

    def create(self, record: PriceGuaranteeRecord) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO price_guarantee_records
            (product_id, low_price_channel, low_price_order_no,
             low_price, guarantee_amount, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (record.product_id, record.low_price_channel, record.low_price_order_no,
             record.low_price, record.guarantee_amount, record.status, record.note)
        )
        self.db.commit()
        return cursor.lastrowid

    def get_by_id(self, record_id: int) -> Optional[PriceGuaranteeRecord]:
        cursor = self.db.execute("SELECT * FROM price_guarantee_records WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def list_by_product(self, product_id: int, limit: int = 100) -> List[PriceGuaranteeRecord]:
        cursor = self.db.execute(
            """
            SELECT * FROM price_guarantee_records
            WHERE product_id = ?
            ORDER BY submitted_at DESC
            LIMIT ?
            """,
            (product_id, limit)
        )
        rows = cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    def update_status(self, record_id: int, status: str, note: Optional[str] = None) -> bool:
        updates = ["status = ?"]
        params = [status]

        if status == "confirmed":
            updates.append("confirmed_at = CURRENT_TIMESTAMP")
        elif status == "pending":
            updates.append("confirmed_at = NULL")

        if note is not None:
            updates.append("note = ?")
            params.append(note)

        params.append(record_id)

        cursor = self.db.execute(
            f"UPDATE price_guarantee_records SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        self.db.commit()
        return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        cursor = self.db.execute("DELETE FROM price_guarantee_records WHERE id = ?", (record_id,))
        self.db.commit()
        return cursor.rowcount > 0
