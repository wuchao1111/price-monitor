"""
CRUD operations for products table
"""
from typing import List, Optional
from sqlite3 import Row
from src.storage.database import Database
from src.models.schemas import Product


class ProductCRUD:
    """CRUD for products table"""

    def __init__(self, db: Database):
        self.db = db

    def _row_to_product(self, row: Row) -> Product:
        product = Product(
            id=row['id'],
            name=row['name'],
            keywords=row['keywords'],
            welfare_policy=row['welfare_policy'],
            current_lowest_price=row['current_lowest_price'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        for col in ['original_price', 'original_order_no', 'original_channel',
                    'current_guaranteed_price', 'pending_guarantee_price',
                    'store_activity', 'group_activity']:
            if col in row.keys():
                setattr(product, col, row[col])
        if 'store_activity_claimed' in row.keys():
            product.store_activity_claimed = bool(row['store_activity_claimed'])
        if 'group_activity_claimed' in row.keys():
            product.group_activity_claimed = bool(row['group_activity_claimed'])
        return product

    def create(self, product: Product) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO products (name, keywords, welfare_policy, current_lowest_price,
                original_price, original_order_no, original_channel,
                current_guaranteed_price, pending_guarantee_price,
                store_activity, group_activity,
                store_activity_claimed, group_activity_claimed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (product.name, product.keywords, product.welfare_policy, product.current_lowest_price,
             product.original_price, product.original_order_no, product.original_channel,
             product.current_guaranteed_price, product.pending_guarantee_price,
             product.store_activity, product.group_activity,
             int(product.store_activity_claimed), int(product.group_activity_claimed))
        )
        self.db.commit()
        return cursor.lastrowid

    def update(self, product: Product) -> bool:
        cursor = self.db.execute(
            """
            UPDATE products
            SET name = ?, keywords = ?, welfare_policy = ?, current_lowest_price = ?,
                original_price = ?, original_order_no = ?, original_channel = ?,
                current_guaranteed_price = ?, pending_guarantee_price = ?,
                store_activity = ?, group_activity = ?,
                store_activity_claimed = ?, group_activity_claimed = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (product.name, product.keywords, product.welfare_policy, product.current_lowest_price,
             product.original_price, product.original_order_no, product.original_channel,
             product.current_guaranteed_price, product.pending_guarantee_price,
             product.store_activity, product.group_activity,
             int(product.store_activity_claimed), int(product.group_activity_claimed),
             product.id)
        )
        self.db.commit()
        return cursor.rowcount > 0

    def update_price_guarantee(
        self,
        product_id: int,
        current_guaranteed_price: Optional[float] = None,
        pending_guarantee_price: Optional[float] = None
    ) -> bool:
        updates = []
        params = []
        if current_guaranteed_price is not None:
            updates.append("current_guaranteed_price = ?")
            params.append(current_guaranteed_price)
        if pending_guarantee_price is not None:
            updates.append("pending_guarantee_price = ?")
            params.append(pending_guarantee_price)
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(product_id)
        self.db.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        self.db.commit()
        return True

    def update_activity_claimed(
        self,
        product_id: int,
        store_activity_claimed: Optional[bool] = None,
        group_activity_claimed: Optional[bool] = None
    ) -> bool:
        updates = []
        params = []
        if store_activity_claimed is not None:
            updates.append("store_activity_claimed = ?")
            params.append(int(store_activity_claimed))
        if group_activity_claimed is not None:
            updates.append("group_activity_claimed = ?")
            params.append(int(group_activity_claimed))
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(product_id)
        self.db.execute(
            f"UPDATE products SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        self.db.commit()
        return True

    def recalculate_guaranteed_price(self, product_id: int) -> None:
        cursor = self.db.execute(
            """
            SELECT MIN(low_price) FROM price_guarantee_records
            WHERE product_id = ? AND status = 'confirmed'
            """,
            (product_id,)
        )
        row = cursor.fetchone()
        lowest_confirmed = row[0] if row else None
        self.db.execute(
            "UPDATE products SET current_guaranteed_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lowest_confirmed, product_id)
        )
        self.db.commit()

    def get_by_id(self, product_id: int) -> Optional[Product]:
        cursor = self.db.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_product(row)

    def list_all(self) -> List[Product]:
        cursor = self.db.execute("SELECT * FROM products ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def search(self, keyword: str) -> List[Product]:
        search_pattern = f"%{keyword}%"
        cursor = self.db.execute(
            "SELECT * FROM products WHERE name LIKE ? OR keywords LIKE ? OR original_order_no LIKE ? ORDER BY created_at DESC",
            (search_pattern, search_pattern, search_pattern)
        )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def list_by_status(self, status: str) -> List[Product]:
        cursor = self.db.execute(
            """
            SELECT p.* FROM products p
            WHERE (SELECT status FROM price_guarantee_records
                   WHERE product_id = p.id
                   ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
            ORDER BY p.created_at DESC
            """,
            (status,)
        )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def search_by_status(self, keyword: str, status: str) -> List[Product]:
        search_pattern = f"%{keyword}%"
        if status == "none":
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                LEFT JOIN price_guarantee_records r ON p.id = r.product_id
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND r.id IS NULL
                ORDER BY p.created_at DESC
                """,
                (search_pattern, search_pattern, search_pattern)
            )
        else:
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND (SELECT status FROM price_guarantee_records
                     WHERE product_id = p.id
                     ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
                ORDER BY p.created_at DESC
                """,
                (search_pattern, search_pattern, search_pattern, status)
            )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def list_by_no_guarantee(self) -> List[Product]:
        cursor = self.db.execute(
            """
            SELECT p.* FROM products p
            LEFT JOIN price_guarantee_records r ON p.id = r.product_id
            WHERE r.id IS NULL
            ORDER BY p.created_at DESC
            """
        )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def count_by_no_guarantee(self) -> int:
        cursor = self.db.execute(
            """
            SELECT COUNT(*) as cnt FROM products p
            LEFT JOIN price_guarantee_records r ON p.id = r.product_id
            WHERE r.id IS NULL
            """
        )
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def count_all(self) -> int:
        cursor = self.db.execute("SELECT COUNT(*) as cnt FROM products")
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def count_search(self, keyword: str) -> int:
        search_pattern = f"%{keyword}%"
        cursor = self.db.execute(
            "SELECT COUNT(*) as cnt FROM products WHERE name LIKE ? OR keywords LIKE ? OR original_order_no LIKE ?",
            (search_pattern, search_pattern, search_pattern)
        )
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def count_by_status(self, status: str) -> int:
        if status == "none":
            cursor = self.db.execute(
                """
                SELECT COUNT(*) as cnt FROM products p
                LEFT JOIN price_guarantee_records r ON p.id = r.product_id
                WHERE r.id IS NULL
                """
            )
        else:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) as cnt FROM products p
                WHERE (SELECT status FROM price_guarantee_records
                       WHERE product_id = p.id
                       ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
                """,
                (status,)
            )
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def count_search_by_status(self, keyword: str, status: str) -> int:
        search_pattern = f"%{keyword}%"
        if status == "none":
            cursor = self.db.execute(
                """
                SELECT COUNT(*) as cnt FROM products p
                LEFT JOIN price_guarantee_records r ON p.id = r.product_id
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND r.id IS NULL
                """,
                (search_pattern, search_pattern, search_pattern)
            )
        else:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) as cnt FROM products p
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND (SELECT status FROM price_guarantee_records
                     WHERE product_id = p.id
                     ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
                """,
                (search_pattern, search_pattern, search_pattern, status)
            )
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def list_all_paginated(self, page: int, page_size: int) -> List[Product]:
        offset = (page - 1) * page_size
        cursor = self.db.execute(
            "SELECT * FROM products ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def search_paginated(self, keyword: str, page: int, page_size: int) -> List[Product]:
        search_pattern = f"%{keyword}%"
        offset = (page - 1) * page_size
        cursor = self.db.execute(
            "SELECT * FROM products WHERE name LIKE ? OR keywords LIKE ? OR original_order_no LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (search_pattern, search_pattern, search_pattern, page_size, offset)
        )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def list_by_status_paginated(self, status: str, page: int, page_size: int) -> List[Product]:
        offset = (page - 1) * page_size
        if status == "none":
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                LEFT JOIN price_guarantee_records r ON p.id = r.product_id
                WHERE r.id IS NULL
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
                """,
                (page_size, offset)
            )
        else:
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                WHERE (SELECT status FROM price_guarantee_records
                       WHERE product_id = p.id
                       ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
                """,
                (status, page_size, offset)
            )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def search_by_status_paginated(self, keyword: str, status: str, page: int, page_size: int) -> List[Product]:
        search_pattern = f"%{keyword}%"
        offset = (page - 1) * page_size
        if status == "none":
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                LEFT JOIN price_guarantee_records r ON p.id = r.product_id
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND r.id IS NULL
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
                """,
                (search_pattern, search_pattern, search_pattern, page_size, offset)
            )
        else:
            cursor = self.db.execute(
                """
                SELECT p.* FROM products p
                WHERE (p.name LIKE ? OR p.keywords LIKE ? OR p.original_order_no LIKE ?)
                AND (SELECT status FROM price_guarantee_records
                     WHERE product_id = p.id
                     ORDER BY submitted_at DESC, id DESC LIMIT 1) = ?
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
                """,
                (search_pattern, search_pattern, search_pattern, status, page_size, offset)
            )
        rows = cursor.fetchall()
        return [self._row_to_product(row) for row in rows]

    def update_lowest_price(
        self,
        product_id: int,
        new_price: float,
        old_price: Optional[float],
        changed_by: str,
        note: Optional[str] = None
    ) -> bool:
        try:
            self.db.begin_transaction()
            self.db.execute(
                """
                UPDATE products
                SET current_lowest_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_price, product_id)
            )
            self.db.execute(
                """
                INSERT INTO change_log (product_id, old_price, new_price, changed_by, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, old_price, new_price, changed_by, note)
            )
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def delete(self, product_id: int) -> bool:
        cursor = self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.db.commit()
        return cursor.rowcount > 0
