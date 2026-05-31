"""
Test: 商品保价状态筛选，应以最新保价记录状态为准
"""
import os
import sys
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.storage.database import Database
from src.storage.product_crud import ProductCRUD
from src.storage.price_guarantee_crud import PriceGuaranteeCRUD
from src.models.schemas import Product, PriceGuaranteeRecord


class TestStatusFilter(unittest.TestCase):
    """测试状态筛选以最新保价记录为准"""

    def setUp(self):
        """创建测试数据库和数据"""
        # 使用独立的测试数据库文件
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        os.remove(self.db_path)  # 让 Database 自己创建

        self.db = Database(self.db_path)

        # 创建表结构
        migration_path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '001_init.sql')
        if os.path.exists(migration_path):
            self.db.init_schema(migration_path)
        else:
            self._init_tables()

        self.product_crud = ProductCRUD(self.db)
        self.guarantee_crud = PriceGuaranteeCRUD(self.db)

        # 创建测试商品
        self.product = Product(
            name="测试商品-状态筛选",
            keywords="测试",
            original_price=100.0
        )
        self.product_id = self.product_crud.create(self.product)

    def _init_tables(self):
        """手动创建表结构（当迁移文件不存在时）"""
        conn = self.db.connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keywords TEXT DEFAULT '',
                welfare_policy TEXT DEFAULT '',
                current_lowest_price REAL,
                original_price REAL,
                original_order_no TEXT DEFAULT '',
                original_channel TEXT DEFAULT '',
                current_guaranteed_price REAL,
                pending_guarantee_price REAL,
                store_activity TEXT DEFAULT '',
                group_activity TEXT DEFAULT '',
                store_activity_claimed INTEGER DEFAULT 0,
                group_activity_claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_guarantee_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                low_price_channel TEXT NOT NULL,
                low_price_order_no TEXT DEFAULT '',
                low_price REAL NOT NULL,
                guarantee_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                note TEXT DEFAULT '',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
        """)
        conn.commit()

    def _add_record(self, product_id: int, low_price: float, status: str, note: str = ""):
        """添加保价记录（直接 SQL，控制时间）"""
        record = PriceGuaranteeRecord(
            product_id=product_id,
            low_price_channel="测试渠道",
            low_price=low_price,
            guarantee_amount=100.0 - low_price,
            status=status,
            note=note
        )
        return self.guarantee_crud.create(record)

    def test_list_by_status_uses_latest_record(self):
        """验证 list_by_status 使用最新保价记录状态"""
        # 创建两条记录：第一条 pending，第二条 confirmed（最新）
        id1 = self._add_record(self.product_id, 90.0, "pending", "旧记录")
        id2 = self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        # 按 pending 筛选 - 不应返回该商品（最新状态是 confirmed）
        pending_products = self.product_crud.list_by_status("pending")
        self.assertNotIn(self.product_id, [p.id for p in pending_products],
                         "最新状态是 confirmed，按 pending 筛选不应返回该商品")

        # 按 confirmed 筛选 - 应返回该商品
        confirmed_products = self.product_crud.list_by_status("confirmed")
        self.assertIn(self.product_id, [p.id for p in confirmed_products],
                      "最新状态是 confirmed，按 confirmed 筛选应返回该商品")

    def test_count_by_status_uses_latest_record(self):
        """验证 count_by_status 使用最新保价记录状态"""
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        pending_count = self.product_crud.count_by_status("pending")
        confirmed_count = self.product_crud.count_by_status("confirmed")

        self.assertEqual(pending_count, 0,
                         "最新状态是 confirmed，pending 计数应为 0")
        self.assertEqual(confirmed_count, 1,
                         "最新状态是 confirmed，confirmed 计数应为 1")

    def test_list_by_status_paginated_uses_latest_record(self):
        """验证 list_by_status_paginated 使用最新保价记录状态"""
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        pending_products = self.product_crud.list_by_status_paginated("pending", 1, 10)
        confirmed_products = self.product_crud.list_by_status_paginated("confirmed", 1, 10)

        self.assertNotIn(self.product_id, [p.id for p in pending_products])
        self.assertIn(self.product_id, [p.id for p in confirmed_products])

    def test_search_by_status_uses_latest_record(self):
        """验证 search_by_status 使用最新保价记录状态"""
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        pending_products = self.product_crud.search_by_status("测试商品", "pending")
        confirmed_products = self.product_crud.search_by_status("测试商品", "confirmed")

        self.assertNotIn(self.product_id, [p.id for p in pending_products])
        self.assertIn(self.product_id, [p.id for p in confirmed_products])

    def test_count_search_by_status_uses_latest_record(self):
        """验证 count_search_by_status 使用最新保价记录状态"""
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        pending_count = self.product_crud.count_search_by_status("测试商品", "pending")
        confirmed_count = self.product_crud.count_search_by_status("测试商品", "confirmed")

        self.assertEqual(pending_count, 0)
        self.assertEqual(confirmed_count, 1)

    def test_search_by_status_paginated_uses_latest_record(self):
        """验证 search_by_status_paginated 使用最新保价记录状态"""
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        pending_products = self.product_crud.search_by_status_paginated("测试商品", "pending", 1, 10)
        confirmed_products = self.product_crud.search_by_status_paginated("测试商品", "confirmed", 1, 10)

        self.assertNotIn(self.product_id, [p.id for p in pending_products])
        self.assertIn(self.product_id, [p.id for p in confirmed_products])

    def test_multiple_products_with_different_latest_status(self):
        """多个商品各有多条保价记录，验证筛选正确性"""
        # 商品2：最新状态是 pending
        p2 = Product(name="测试商品-状态筛选2", keywords="测试", original_price=200.0)
        p2_id = self.product_crud.create(p2)
        self._add_record(p2_id, 180.0, "confirmed", "旧记录")
        self._add_record(p2_id, 170.0, "pending", "新记录")

        # 商品1（已有）：最新状态是 confirmed
        self._add_record(self.product_id, 90.0, "pending", "旧记录")
        self._add_record(self.product_id, 85.0, "confirmed", "新记录")

        # 按 pending 筛选 - 应只返回商品2
        pending_products = self.product_crud.list_by_status("pending")
        pending_ids = [p.id for p in pending_products]
        self.assertNotIn(self.product_id, pending_ids,
                         "商品1最新是 confirmed，不应出现在 pending 列表中")
        self.assertIn(p2_id, pending_ids,
                      "商品2最新是 pending，应出现在 pending 列表中")

        # 按 confirmed 筛选 - 应只返回商品1
        confirmed_products = self.product_crud.list_by_status("confirmed")
        confirmed_ids = [p.id for p in confirmed_products]
        self.assertIn(self.product_id, confirmed_ids,
                      "商品1最新是 confirmed，应出现在 confirmed 列表中")
        self.assertNotIn(p2_id, confirmed_ids,
                         "商品2最新是 pending，不应出现在 confirmed 列表中")

    def test_no_guarantee_filter(self):
        """验证 'none' 筛选不变（无保价记录的商品）"""
        # 给 self.product 添加一条保价记录，使其不在 "none" 中
        self._add_record(self.product_id, 90.0, "pending", "已有记录")
        p3 = Product(name="测试商品-无保价", keywords="测试", original_price=300.0)
        p3_id = self.product_crud.create(p3)

        # 使用 list_by_status_paginated("none", ...) 验证无保价商品筛选
        none_products = self.product_crud.list_by_status_paginated("none", 1, 10)
        none_ids = [p.id for p in none_products]
        self.assertIn(p3_id, none_ids, "无保价记录的商品应出现在 'none' 列表中")
        self.assertNotIn(self.product_id, none_ids,
                         "有保价记录的商品不应出现在 'none' 列表中")

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)


if __name__ == "__main__":
    unittest.main()
