"""
AWS Glue job: FHIR R4 API → S3 raw layer.
Ingests patient and clinical resources from FHIR-compliant healthcare APIs.
Writes encrypted, partitioned Parquet to the S3 raw zone.
"""

import json
import logging
import os
from datetime import datetime, date
from typing import Iterator

import boto3
import requests
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

FHIR_RESOURCES = ["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"]
PAGE_SIZE = 200
S3_RAW_PREFIX = "s3://{bucket}/raw/fhir/{resource}/{year}/{month}/{day}/"


def get_fhir_token(secret_name: str, region: str) -> str:
    """Fetch FHIR API bearer token from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    return secret["bearer_token"]


def paginate_fhir_resource(
    base_url: str,
    resource: str,
    token: str,
    page_size: int = PAGE_SIZE,
    last_updated_since: str = None,
) -> Iterator[list[dict]]:
    """
    Paginate a FHIR bundle resource using next-page links.
    Yields pages of entries as lists of dicts.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/fhir+json",
    }
    params = {"_count": page_size}
    if last_updated_since:
        params["_lastUpdated"] = f"gt{last_updated_since}"

    url = f"{base_url}/{resource}"

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        bundle = response.json()

        entries = bundle.get("entry", [])
        if entries:
            yield [e["resource"] for e in entries if "resource" in e]

        next_link = next(
            (link["url"] for link in bundle.get("link", []) if link["rel"] == "next"),
            None,
        )
        url = next_link
        params = {}  # next URL already contains params


def write_to_s3_raw(
    spark: SparkSession,
    records: list[dict],
    resource_type: str,
    bucket: str,
    run_date: date,
) -> int:
    """
    Write FHIR resource records to S3 raw zone as partitioned Parquet.
    Returns the number of records written.
    """
    if not records:
        logger.warning("No records to write for resource %s", resource_type)
        return 0

    s3_path = S3_RAW_PREFIX.format(
        bucket=bucket,
        resource=resource_type.lower(),
        year=run_date.year,
        month=str(run_date.month).zfill(2),
        day=str(run_date.day).zfill(2),
    )

    schema = StructType([
        StructField("resource_type", StringType(), nullable=False),
        StructField("resource_id",   StringType(), nullable=False),
        StructField("payload",       StringType(), nullable=False),
        StructField("ingested_at",   StringType(), nullable=False),
    ])

    rows = [
        {
            "resource_type": resource_type,
            "resource_id":   r.get("id", ""),
            "payload":       json.dumps(r),
            "ingested_at":   datetime.utcnow().isoformat(),
        }
        for r in records
    ]

    df = spark.createDataFrame(rows, schema=schema)
    df.write.mode("overwrite").parquet(s3_path)

    logger.info("Wrote %d %s records to %s", len(rows), resource_type, s3_path)
    return len(rows)


def run(args: dict) -> None:
    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    fhir_token = get_fhir_token(
        secret_name=args["FHIR_SECRET_NAME"],
        region=args["AWS_REGION"],
    )

    run_date = date.today()
    total_written = 0

    for resource in FHIR_RESOURCES:
        resource_count = 0
        for page in paginate_fhir_resource(
            base_url=args["FHIR_BASE_URL"],
            resource=resource,
            token=fhir_token,
            last_updated_since=args.get("LAST_UPDATED_SINCE"),
        ):
            resource_count += write_to_s3_raw(
                spark=spark,
                records=page,
                resource_type=resource,
                bucket=args["S3_RAW_BUCKET"],
                run_date=run_date,
            )

        logger.info("Resource %s complete: %d records", resource, resource_count)
        total_written += resource_count

    logger.info("FHIR ingestion complete. Total records: %d", total_written)
    job.commit()


if __name__ == "__main__":
    import sys
    args = getResolvedOptions(sys.argv, [
        "JOB_NAME",
        "FHIR_BASE_URL",
        "FHIR_SECRET_NAME",
        "S3_RAW_BUCKET",
        "AWS_REGION",
    ])
    run(args)
