"""Tests for the CSV ingestion logic."""

from io import StringIO
from unittest.mock import MagicMock

import pandas as pd

from ebury_customer_transactions import CustomerTransactionsTasks

CSV_CONTENT = """\
transaction_id,customer_id,transaction_date,product_id,product_name,quantity,price,tax
1001,501.0,2023-07-11,101,Product A,1.0,76.27,8.23
1002,502.0,2023-07-12,102,Product B,3.0,119.16,17.06
"""

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "analytics",
    "user": "dbt",
    "password": "test",
}


def _make_tasks():
    """Create a CustomerTransactionsTasks instance with mocked dependencies."""
    tasks = CustomerTransactionsTasks(csv_path="/tmp/test.csv", db_config=DB_CONFIG)

    # Replace real pandas read with our test CSV
    tasks._read_csv = lambda: pd.read_csv(StringIO(CSV_CONTENT), dtype=str, keep_default_na=False)

    # Mock cursor: tracks execute calls and returns row count
    cursor = MagicMock()
    cursor.fetchone.return_value = (2,)

    # Mock the psycopg3 cur.copy() context manager
    mock_copy = MagicMock()
    cursor.copy.return_value.__enter__ = MagicMock(return_value=mock_copy)
    cursor.copy.return_value.__exit__ = MagicMock(return_value=False)

    # Mock connection as context manager
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    # Replace real connection with mock
    tasks._connect = lambda: conn

    return tasks, cursor, conn, mock_copy


def test_ingest_returns_row_count():
    """ingest_csv_to_postgres returns the number of loaded rows."""
    tasks, _, _, _ = _make_tasks()
    assert tasks.ingest_csv_to_postgres() == 2


def test_ingest_drops_and_creates_table():
    """The raw table is dropped and recreated (idempotent full refresh)."""
    tasks, cursor, _, _ = _make_tasks()
    tasks.ingest_csv_to_postgres()

    sqls = [str(c) for c in cursor.execute.call_args_list]
    assert any("DROP TABLE IF EXISTS" in s for s in sqls)
    assert any("CREATE TABLE" in s for s in sqls)


def test_ingest_uses_copy():
    """Bulk loading uses psycopg3 COPY protocol."""
    tasks, cursor, _, mock_copy = _make_tasks()
    tasks.ingest_csv_to_postgres()

    cursor.copy.assert_called_once_with("COPY raw_customer_transactions FROM STDIN WITH CSV")
    mock_copy.write.assert_called_once()


def test_ingest_closes_connection():
    """The database connection is always closed."""
    tasks, _, conn, _ = _make_tasks()
    tasks.ingest_csv_to_postgres()

    conn.close.assert_called_once()
