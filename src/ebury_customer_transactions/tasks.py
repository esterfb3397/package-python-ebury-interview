"""Business logic for the customer transactions pipeline."""

from io import StringIO

import pandas as pd
import psycopg


class CustomerTransactionsTasks:
    """Encapsulates task logic for the customer transactions pipeline.

    Each public method corresponds to an Airflow task and can be called
    independently for testing or ad-hoc execution.
    """

    def __init__(self, csv_path: str, db_config: dict):
        self.csv_path = csv_path
        self.db_config = db_config

    def _read_csv(self) -> pd.DataFrame:
        """Read the CSV file preserving all values as text."""
        return pd.read_csv(self.csv_path, dtype=str, keep_default_na=False)

    def _connect(self):
        """Create a database connection."""
        return psycopg.connect(**self.db_config)

    def ingest_csv_to_postgres(self) -> int:
        """Read customer_transactions.csv and load it into raw_customer_transactions.

        - All columns are loaded as TEXT to preserve the original data.
        - Uses COPY for efficient bulk loading.
        - Idempotent: recreates the table on every run (full refresh).
        """
        df = self._read_csv()
        conn = self._connect()

        try:
            with conn:
                with conn.cursor() as cur:
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

                    buffer = StringIO()
                    df.to_csv(buffer, index=False, header=False)
                    buffer.seek(0)

                    with cur.copy("COPY raw_customer_transactions FROM STDIN WITH CSV") as copy:
                        copy.write(buffer.read())

                    cur.execute("SELECT COUNT(*) FROM raw_customer_transactions;")
                    count = cur.fetchone()[0]
        finally:
            conn.close()

        print(f"Loaded {count} rows into raw_customer_transactions")
        return count
