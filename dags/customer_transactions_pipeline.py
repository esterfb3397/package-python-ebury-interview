"""
DAG: customer_transactions_pipeline

Customer transactions pipeline:
  1. Ingest CSV into PostgreSQL (raw table, TEXT columns)
  2. dbt run — staging + dimensional model (dim_table, fact_table)
  3. dbt test — data quality validation
"""

import os
from datetime import datetime, timedelta

from airflow.sdk import DAG, task
from airflow.operators.bash import BashOperator


DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_CMD = f"dbt {{}} --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"

with DAG(
    dag_id="customer_transactions_pipeline",
    description="CSV ingestion and dbt transformations for customer transactions",
    start_date=datetime(2023, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ebury", "transactions"],
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    },
) as dag:

    @task
    def ingest_csv_to_postgres() -> int:
        """Read customer_transactions.csv and load it into raw_customer_transactions.

        - All columns are loaded as TEXT to preserve the original data.
        - Uses COPY for efficient bulk loading.
        - Idempotent: recreates the table on every run (full refresh).
        """
        import pandas as pd
        import psycopg2
        from io import StringIO

        csv_path = "/opt/airflow/data/customer_transactions.csv"

        # dtype=str preserves everything as text; keep_default_na=False prevents
        # pandas from converting empty strings to NaN
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

        conn = psycopg2.connect(
            host=os.environ["DBT_HOST"],
            port=int(os.environ["DBT_PORT"]),
            dbname=os.environ["DBT_DBNAME"],
            user=os.environ["DBT_USER"],
            password=os.environ["DBT_PASSWORD"],
        )

        try:
            with conn:
                with conn.cursor() as cur:
                    # Full refresh: recreate the table
                    cur.execute("DROP TABLE IF EXISTS raw_customer_transactions;")
                    cur.execute("""
                        CREATE TABLE raw_customer_transactions (
                            transaction_id   TEXT,
                            customer_id      TEXT,
                            transaction_date TEXT,
                            product_id       TEXT,
                            product_name     TEXT,
                            quantity         TEXT,
                            price            TEXT,
                            tax              TEXT
                        );
                    """)

                    # Efficient bulk load with COPY (instead of row-by-row INSERT)
                    buffer = StringIO()
                    df.to_csv(buffer, index=False, header=False)
                    buffer.seek(0)

                    cur.copy_expert(
                        "COPY raw_customer_transactions FROM STDIN WITH CSV",
                        buffer,
                    )

                    cur.execute(
                        "SELECT COUNT(*) FROM raw_customer_transactions;"
                    )
                    count = cur.fetchone()[0]
        finally:
            conn.close()

        print(f"Loaded {count} rows into raw_customer_transactions")
        return count

    # Task 2: dbt run — execute staging + dimensional models
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=DBT_CMD.format("run"),
    )

    # Task 3: dbt test — data quality validation
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=DBT_CMD.format("test"),
    )

    # Dependencies: ingest → dbt run → dbt test
    ingest_csv_to_postgres() >> dbt_run >> dbt_test
