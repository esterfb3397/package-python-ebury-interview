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

from ebury_customer_transactions import CustomerTransactionsTasks


DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_CMD = f"dbt {{}} --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"

pipeline = CustomerTransactionsTasks(
    csv_path="/opt/airflow/data/customer_transactions.csv",
    db_config={
        "host": os.environ.get("DBT_HOST", "postgres"),
        "port": int(os.environ.get("DBT_PORT", "5432")),
        "dbname": os.environ.get("DBT_DBNAME", "analytics"),
        "user": os.environ.get("DBT_USER", "dbt"),
        "password": os.environ.get("DBT_PASSWORD", ""),
    },
)

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
        """Delegate to CustomerTransactionsTasks."""
        return pipeline.ingest_csv_to_postgres()

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
