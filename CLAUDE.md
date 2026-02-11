# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Apache Airflow 3.1.7 orchestration platform deployed via Docker Compose with CeleryExecutor. Uses PostgreSQL 16 for metadata/application storage, Valkey 9.0.2 (Redis-compatible) as the Celery message broker, and dbt 1.9.0 for data transformations. Documentation is in Spanish.

## Commands

```bash
# First-time setup
cp .env.example .env
docker compose up airflow-init
docker compose up -d

# Check service health
docker compose ps

# View logs for a specific service
docker compose logs -f airflow-scheduler

# Run ad-hoc Airflow CLI commands
docker compose --profile debug run --rm airflow-cli airflow dags list

# Scale workers horizontally
docker compose up -d --scale airflow-worker=3

# Enable Flower (Celery monitoring UI)
docker compose --profile flower up -d

# dbt — verify connection
docker compose --profile dbt run --rm dbt debug

# dbt — run models
docker compose --profile dbt run --rm dbt run

# dbt — run tests
docker compose --profile dbt run --rm dbt test

# dbt — generate docs
docker compose --profile dbt run --rm dbt docs generate

# Stop services (preserve data)
docker compose down

# Stop and destroy all data
docker compose down -v
```

## Architecture

**Services** (defined in `docker-compose.yml` via `x-airflow-common` YAML anchor):

- **postgres** — Shared PostgreSQL 16 instance hosting the application DB (`POSTGRES_DB`), Airflow metadata DB (`AIRFLOW_DB_NAME`), and dbt analytics DB (`DBT_DB_NAME`). The Airflow and dbt DB/users are auto-created by `init-db.sh` on first boot.
- **valkey** — Message broker (Valkey 9.0.2, Redis-protocol compatible). Internal-only (not exposed to host). `noeviction` memory policy to prevent message loss.
- **airflow-apiserver** — Web UI + REST API (port 8080)
- **airflow-scheduler** — Monitors DAGs and enqueues tasks to Valkey
- **airflow-dag-processor** — Parses DAG files from `dags/` and registers them (Airflow 3.x feature, previously done by scheduler)
- **airflow-worker** — Celery worker executing queued tasks (scalable)
- **airflow-triggerer** — Manages deferrable/async operators
- **airflow-init** — One-shot: runs DB migrations, creates admin user, checks resources
- **airflow-cli** — Debug profile only (`--profile debug`)
- **flower** — Celery monitoring, flower profile only (`--profile flower`)
- **dbt** — dbt-postgres 1.9.0 for data transformations, dbt profile only (`--profile dbt`). One-shot service executed via `docker compose --profile dbt run --rm dbt <command>`

**Key directories** (mounted into containers at `/opt/airflow/`):

- `dags/` — DAG definition Python files
- `plugins/` — Custom Airflow operators, hooks, sensors
- `config/` — `airflow.cfg` (env vars `AIRFLOW__*` take precedence)
- `dbt/` — dbt project (models, seeds, macros, tests, profiles.yml)
- `logs/` — Runtime logs (git-ignored)

## Configuration

All env vars are in `.env` (copy from `.env.example`). Airflow config can be overridden via `AIRFLOW__<SECTION>__<KEY>` environment variables, which take precedence over `config/airflow.cfg`.

On Linux, set `AIRFLOW_UID=$(id -u)` in `.env` to match host user permissions on mounted volumes. macOS/Windows can use the default (50000).

## Access Points

| Service    | URL                    | Default credentials  |
|------------|------------------------|----------------------|
| Airflow UI | http://localhost:8080  | airflow / airflow    |
| Flower     | http://localhost:5555  | (none)               |
| PostgreSQL | localhost:5432         | app / changeme       |
