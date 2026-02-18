"""Tests for customer_transactions_pipeline DAG structure."""

import pytest
from airflow.models import DagBag


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="dags", include_examples=False)


def test_dag_loaded(dagbag):
    assert "customer_transactions_pipeline" in dagbag.dags
    assert dagbag.import_errors == {}


def test_dag_has_correct_tags(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]
    assert set(dag.tags) == {"ebury", "transactions"}


def test_dag_has_three_tasks(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]
    assert len(dag.tasks) == 3


def test_dag_task_ids(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {"ingest_csv_to_postgres", "dbt_run", "dbt_test"}


def test_dag_dependencies(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]

    ingest = dag.get_task("ingest_csv_to_postgres")
    dbt_run = dag.get_task("dbt_run")
    dbt_test = dag.get_task("dbt_test")

    # ingest_csv_to_postgres >> dbt_run >> dbt_test
    assert "dbt_run" in {t.task_id for t in ingest.downstream_list}
    assert "dbt_test" in {t.task_id for t in dbt_run.downstream_list}
    assert dbt_test.downstream_list == []


def test_dag_no_schedule(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]
    assert dag.schedule_interval is None


def test_dag_default_args(dagbag):
    dag = dagbag.dags["customer_transactions_pipeline"]
    assert dag.default_args["owner"] == "data-engineering"
    assert dag.default_args["retries"] == 2
