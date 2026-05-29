"""
Database connection and initialization
"""
import os
import sqlite3
from logging import getLogger
from typing import Optional

logger = getLogger(__name__)


class Database:
    """SQLite database wrapper"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        # Enable foreign keys
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))

    def connect(self) -> sqlite3.Connection:
        """Get a database connection"""
        if self._conn is None:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            self._conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False
            )
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode = WAL")
            # Use Row factory to enable column name access
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Close database connection"""
        if self._conn is not None:
            self._conn.close
            self._conn = None

    def init_schema(self, migration_path: str) -> None:
        """Initialize database schema from migration file"""
        conn = self.connect()
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
        logger.info("Database schema initialized")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL statement"""
        conn = self.connect()
        return conn.execute(sql, params)

    def commit(self) -> None:
        """Commit current transaction"""
        if self._conn is not None:
            self._conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction"""
        if self._conn is not None:
            self._conn.rollback()

    def begin_transaction(self) -> None:
        """Begin a transaction"""
        conn = self.connect()
        conn.execute("BEGIN")
