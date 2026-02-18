"""Tests for the CSV ingestion logic."""

import os
from io import StringIO
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest


CSV_CONTENT = """\
transaction_id,customer_id,transaction_date,product_id,product_name,quantity,price,tax
1001,501.0,2023-07-11,101,Product A,1.0,76.27,8.23
1002,502.0,2023-07-12,102,Product B,3.0,119.16,17.06
"""


@pytest.fixture(autouse=True)
def _set_env_vars(monkeypatch):
    monkeypatch.setenv("DBT_HOST", "localhost")
    monkeypatch.setenv("DBT_PORT", "5432")
    monkeypatch.setenv("DBT_DBNAME", "analytics")
    monkeypatch.setenv("DBT_USER", "dbt")
    monkeypatch.setenv("DBT_PASSWORD", "test")


@patch("psycopg2.connect")
@patch("pandas.read_csv")
def test_ingest_reads_csv_as_text(mock_read_csv, mock_connect):
    """Verify that CSV is read with dtype=str and keep_default_na=False."""
    mock_read_csv.return_value = pd.read_csv(StringIO(CSV_CONTENT), dtype=str, keep_default_na=False)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (2,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    from customer_transactions_pipeline import ingest_csv_to_postgres

    # Call the underlying function (unwrap the Airflow @task decorator)
    func = ingest_csv_to_postgres.function
    result = func()

    mock_read_csv.assert_called_once_with(
        "/opt/airflow/data/customer_transactions.csv",
        dtype=str,
        keep_default_na=False,
    )
    assert result == 2


@patch("psycopg2.connect")
@patch("pandas.read_csv")
def test_ingest_drops_and_creates_table(mock_read_csv, mock_connect):
    """Verify that the raw table is dropped and recreated (idempotent)."""
    mock_read_csv.return_value = pd.read_csv(StringIO(CSV_CONTENT), dtype=str, keep_default_na=False)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (2,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    from customer_transactions_pipeline import ingest_csv_to_postgres

    func = ingest_csv_to_postgres.function
    func()

    executed_sqls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("DROP TABLE IF EXISTS" in s for s in executed_sqls)
    assert any("CREATE TABLE" in s for s in executed_sqls)


@patch("psycopg2.connect")
@patch("pandas.read_csv")
def test_ingest_uses_copy(mock_read_csv, mock_connect):
    """Verify that COPY is used for bulk loading."""
    mock_read_csv.return_value = pd.read_csv(StringIO(CSV_CONTENT), dtype=str, keep_default_na=False)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (2,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value = mock_conn

    from customer_transactions_pipeline import ingest_csv_to_postgres

    func = ingest_csv_to_postgres.function
    func()

    mock_cursor.copy_expert.assert_called_once()
    copy_sql = mock_cursor.copy_expert.call_args[0][0]
    assert "COPY raw_customer_transactions FROM STDIN WITH CSV" in copy_sql
