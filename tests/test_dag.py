"""Tests for customer_transactions_pipeline DAG structure."""

from airflow.models import DagBag

dagbag = DagBag(dag_folder="dags", include_examples=False)
dag = dagbag.dags["customer_transactions_pipeline"]


def test_dag_loaded():
    assert "customer_transactions_pipeline" in dagbag.dags
    assert dagbag.import_errors == {}


def test_dag_has_correct_tags():
    assert set(dag.tags) == {"ebury", "transactions"}


def test_dag_has_three_tasks():
    assert len(dag.tasks) == 3


def test_dag_task_ids():
    task_ids = {t.task_id for t in dag.tasks}
    assert task_ids == {"ingest_csv_to_postgres", "dbt_run", "dbt_test"}


def test_dag_dependencies():
    ingest = dag.get_task("ingest_csv_to_postgres")
    dbt_run = dag.get_task("dbt_run")
    dbt_test = dag.get_task("dbt_test")

    assert "dbt_run" in {t.task_id for t in ingest.downstream_list}
    assert "dbt_test" in {t.task_id for t in dbt_run.downstream_list}
    assert dbt_test.downstream_list == []


def test_dag_default_args():
    assert dag.default_args["owner"] == "data-engineering"
    assert dag.default_args["retries"] == 2
