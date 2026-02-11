#!/bin/bash
set -euo pipefail

# Create the Airflow database and user if they do not exist.
# This script runs only on first Postgres initialisation.
# Variables AIRFLOW_DB_USER, AIRFLOW_DB_PASSWORD and AIRFLOW_DB_NAME
# are injected from the .env file via docker-compose env_file.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${AIRFLOW_DB_USER}') THEN
            CREATE ROLE ${AIRFLOW_DB_USER} WITH LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE ${AIRFLOW_DB_NAME} OWNER ${AIRFLOW_DB_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${AIRFLOW_DB_NAME}')\gexec

    GRANT ALL PRIVILEGES ON DATABASE ${AIRFLOW_DB_NAME} TO ${AIRFLOW_DB_USER};

    -- dbt database and user
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DBT_DB_USER}') THEN
            CREATE ROLE ${DBT_DB_USER} WITH LOGIN PASSWORD '${DBT_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE ${DBT_DB_NAME} OWNER ${DBT_DB_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DBT_DB_NAME}')\gexec

    GRANT ALL PRIVILEGES ON DATABASE ${DBT_DB_NAME} TO ${DBT_DB_USER};
EOSQL
