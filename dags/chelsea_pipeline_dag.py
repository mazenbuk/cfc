from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "chelsea-data-team",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="chelsea_fc_data_pipeline",
    description="Extract - Transform - Load data Chelsea FC dari API-Football ke Postgres",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * 1",
    catchup=False,
    tags=["chelsea", "football", "etl"],
) as dag:

    extract = BashOperator(
        task_id="extract_data",
        bash_command="python /opt/airflow/etl/extract.py",
    )

    transform = BashOperator(
        task_id="transform_data",
        bash_command="python /opt/airflow/etl/transform.py",
    )

    load = BashOperator(
        task_id="load_data",
        bash_command="python /opt/airflow/etl/load.py",
    )

    extract >> transform >> load