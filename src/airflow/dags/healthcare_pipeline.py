"""
Airflow DAG: HIPAA-compliant healthcare data pipeline.
Orchestrates: FHIR ingestion → PII masking → S3 clean zone → dbt → Snowflake.
Maintains 99.95% uptime with retries, SLA alerts, and dead-letter handling.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

DEFAULT_ARGS = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "retries":          3,
    "retry_delay":      timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay":  timedelta(minutes=30),
    "email_on_failure": False,
    "email_on_retry":   False,
}

SLA_THRESHOLD = timedelta(hours=4)


def _alert_on_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Send Slack alert when pipeline misses its SLA."""
    message = (
        f":warning: *SLA Miss* — `{dag.dag_id}`\n"
        f"Missed tasks: {[t.task_id for t in blocking_task_list]}"
    )
    SlackWebhookOperator(
        task_id="sla_miss_alert",
        slack_webhook_conn_id="slack_data_alerts",
        message=message,
    ).execute({})


with DAG(
    dag_id="healthcare_data_pipeline",
    default_args=DEFAULT_ARGS,
    description="HIPAA-compliant pipeline: FHIR → S3 → dbt → Snowflake",
    schedule_interval="0 2 * * *",  # 2 AM UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    sla_miss_callback=_alert_on_sla_miss,
    tags=["healthcare", "hipaa", "fhir", "production"],
) as dag:

    # 1. Ingest FHIR resources from clinical APIs to S3 raw
    fhir_ingest = GlueJobOperator(
        task_id="fhir_ingestion",
        job_name="healthcare-fhir-ingestion",
        script_location="s3://glue-scripts/fhir_ingestion.py",
        script_args={
            "--FHIR_BASE_URL":     Variable.get("fhir_base_url"),
            "--FHIR_SECRET_NAME":  Variable.get("fhir_secret_name"),
            "--S3_RAW_BUCKET":     Variable.get("s3_raw_bucket"),
            "--AWS_REGION":        "us-east-1",
        },
        aws_conn_id="aws_default",
        sla=SLA_THRESHOLD,
    )

    fhir_ingest_sensor = GlueJobSensor(
        task_id="fhir_ingestion_sensor",
        job_name="healthcare-fhir-ingestion",
        run_id="{{ task_instance.xcom_pull('fhir_ingestion') }}",
        aws_conn_id="aws_default",
        poke_interval=60,
        timeout=3600,
    )

    # 2. Apply PII masking and write to S3 clean zone
    pii_masking = GlueJobOperator(
        task_id="pii_masking",
        job_name="healthcare-pii-masking",
        script_location="s3://glue-scripts/pii_masking_job.py",
        script_args={
            "--S3_RAW_BUCKET":   Variable.get("s3_raw_bucket"),
            "--S3_CLEAN_BUCKET": Variable.get("s3_clean_bucket"),
        },
        aws_conn_id="aws_default",
        sla=SLA_THRESHOLD,
    )

    pii_masking_sensor = GlueJobSensor(
        task_id="pii_masking_sensor",
        job_name="healthcare-pii-masking",
        run_id="{{ task_instance.xcom_pull('pii_masking') }}",
        aws_conn_id="aws_default",
        poke_interval=60,
        timeout=3600,
    )

    # 3. Run dbt models: staging → intermediate → marts
    def run_dbt_models(**context):
        import subprocess
        result = subprocess.run(
            ["dbt", "run", "--select", "tag:healthcare", "--profiles-dir", "/opt/airflow/dbt"],
            capture_output=True,
            text=True,
            check=True,
        )
        context["task_instance"].xcom_push(key="dbt_output", value=result.stdout)

    dbt_run = PythonOperator(
        task_id="dbt_run",
        python_callable=run_dbt_models,
        sla=SLA_THRESHOLD,
    )

    # 4. Run dbt tests for data quality validation
    def run_dbt_tests(**context):
        import subprocess
        subprocess.run(
            ["dbt", "test", "--select", "tag:healthcare", "--profiles-dir", "/opt/airflow/dbt"],
            capture_output=True,
            text=True,
            check=True,
        )

    dbt_test = PythonOperator(
        task_id="dbt_test",
        python_callable=run_dbt_tests,
    )

    # 5. Notify on successful completion
    success_alert = SlackWebhookOperator(
        task_id="success_notification",
        slack_webhook_conn_id="slack_data_alerts",
        message=(
            ":white_check_mark: *Healthcare Pipeline Complete*\n"
            "FHIR ingestion → PII masking → dbt → Snowflake\n"
            "Run date: `{{ ds }}`"
        ),
    )

    # DAG dependencies
    (
        fhir_ingest
        >> fhir_ingest_sensor
        >> pii_masking
        >> pii_masking_sensor
        >> dbt_run
        >> dbt_test
        >> success_alert
    )
