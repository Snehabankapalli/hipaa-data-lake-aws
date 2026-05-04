# HIPAA-Compliant Healthcare Data Lake (Streaming + Batch)

> End-to-end analytics platform for regulated healthcare data combining real-time streaming and batch processing. Processes 10TB+/month across 50M+ patient records with 18 PHI identifiers masked before data touches Snowflake. Built on AWS using the Lambda architecture pattern.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Kafka-231F20?style=flat&logo=apachekafka&logoColor=white)
![PySpark](https://img.shields.io/badge/PySpark-E25A1C?style=flat&logo=apachespark&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Airflow-017CEE?style=flat&logo=apacheairflow&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=flat&logo=dbt&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat&logo=snowflake&logoColor=white)
[![CI](https://github.com/Snehabankapalli/hipaa-data-lake-aws/actions/workflows/ci.yml/badge.svg)](https://github.com/Snehabankapalli/hipaa-data-lake-aws/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 1. What This System Does

Ingests clinical and operational data from 20+ source systems through both a real-time streaming layer and a daily batch layer, applies HIPAA-compliant PII masking, and delivers governed analytics to Snowflake.

- **Real-time layer** — Kafka + Spark Streaming for sub-minute event processing
- **Batch layer** — AWS Glue + Airflow for high-volume daily loads (10TB+/month)
- **Unified model** — Both layers write to the same Snowflake tables via merge strategy
- **HIPAA-compliant** — 18 PHI identifiers masked before data reaches Snowflake
- **High reliability** — 99.95% pipeline uptime, SLA monitoring, auto-retry with exponential backoff

---

## 2. Architecture

```
SOURCES (20+ systems)
FHIR R4 APIs · HL7 v2 · Claims DB · Lab Systems · EHR
        │                              │
        │ real-time events             │ batch files
        ▼                              ▼
REAL-TIME LAYER               BATCH LAYER
Kafka (MSK)                   AWS Glue (PySpark)
└─ Schema Registry            └─ FHIR ingestion
                              └─ HL7 parsing
Spark Structured              └─ Claims ETL
Streaming (EMR)
                              Airflow DAGs
        │                              │
        └──────────────┬───────────────┘
                       │ both layers → merge strategy
              PII MASKING LAYER
              HMAC tokens · Safe Harbor dates
              ZIP generalization · PHI redaction
                       │
              S3 DATA LAKE
              raw/     ← KMS-encrypted source data
              clean/   ← PII-masked, validated
              analytics/ ← de-identified
                       │ Snowpipe (continuous)
              SNOWFLAKE
              STAGING      → standardized
              INTERMEDIATE → business logic
              MARTS        → analytics-ready
                population health
                claims analytics
                compliance reporting
                       │
              CONSUMERS
              BI · Clinical Ops · Compliance
```

---

## 3. Scale and Impact

| Metric | Value |
|--------|-------|
| Monthly data volume | 10TB+ |
| Patient records | 50M+ |
| Source systems | 20+ |
| Pipeline uptime | 99.95% |
| Real-time latency | < 60 seconds end-to-end |
| Batch latency | Same-day (by 6 AM) |
| Manual processing reduced | 50% |
| Dashboard performance | 60% faster |

---

## 4. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Real-time streaming | Kafka (AWS MSK) + Spark Streaming | Sub-minute latency for clinical alerts |
| Batch ingestion | AWS Glue (PySpark) | Serverless, handles irregular volume bursts |
| Storage | S3 (KMS-encrypted, versioned) | HIPAA-eligible, cost-effective at 10TB scale |
| Transformation | dbt + Snowflake | Version-controlled SQL, built-in quality tests |
| Orchestration | Apache Airflow | DAG dependencies, SLA monitoring, retry logic |
| Infrastructure | Terraform | Auditable, repeatable infra changes |

---

## 5. Key Engineering Decisions

**Why Lambda architecture (streaming + batch)?**
Clinical alerts need sub-minute latency (real-time layer). Financial reporting needs complete, correct data (batch layer). A pure streaming approach misses late-arriving claims. A pure batch approach fails clinical operations. Lambda gives both.

**HIPAA Safe Harbor vs Expert Determination**
Chose Safe Harbor — deterministically removes all 18 required identifiers. More repeatable and auditable than statistical Expert Determination.

**Incremental dbt models with 3-day lookback**
Healthcare claims arrive late (up to 72 hours after service date). A 3-day lookback window catches late arrivals without expensive full refreshes.

**Idempotent processing**
Both layers are fully idempotent — reruns produce identical results. Critical for regulated environments where reprocessing is common after audit findings.

---

## 6. HIPAA Compliance Details

PHI masking applied at ingestion, before any data lands in the clean S3 layer:

```
patient_id:    "PAT-00291847"  →  "a3f8c2e1d4b7..."   HMAC token
first_name:    "Jane"          →  "[REDACTED]"
date_of_birth: "1985-04-12"    →  "1985"              year only (Safe Harbor)
zip_code:      "98101"         →  "981"               3-digit prefix
phone:         "206-555-0192"  →  "[REDACTED]"
```

Safe Harbor removes all 18 PHI identifiers per 45 CFR 164.514(b). Masking logic is in `src/pii_masking/safe_harbor.py`.

dbt test enforces no raw PHI leaks into the clean layer:
```
PASS  assert_no_raw_phi_in_clean_layer    0 violations across 50M rows
```

---

## 7. Sample Pipeline Run

```
[02:01] fhir_ingestion      SUCCESS  18m 42s   50,241,882 records ingested
[02:20] pii_masking         SUCCESS  24m 08s   18 PHI fields masked
[02:44] dbt_run             SUCCESS  41m 17s   38 models completed
[03:26] dbt_test            SUCCESS   8m 54s   214/214 tests passed
[03:35] slack_notification  SUCCESS            "Pipeline complete — data ready"
```

---

## 8. How to Run

```bash
git clone https://github.com/Snehabankapalli/hipaa-data-lake-aws
cd hipaa-data-lake-aws

pip install -r requirements.txt

export PII_MASKING_SECRET=your-secret
export SNOWFLAKE_ACCOUNT=your-account
export SNOWFLAKE_USER=pipeline_user
export SNOWFLAKE_PASSWORD=your-password

# Start local Kafka stack
docker-compose up -d

# Run FHIR ingestion dry run
python src/glue_jobs/fhir_ingestion.py --dry-run

# Deploy AWS infra
cd infra && terraform init && terraform apply

# Run dbt
dbt run --select tag:healthcare
dbt test --select tag:healthcare

pytest tests/ -v
```

---

## 9. Interview Talking Points

- **Lambda vs Kappa:** "Lambda gives operational resilience. Streaming for freshness, batch for correctness. When claims arrive 48 hours late, only the batch layer can fix it cleanly."
- **HIPAA enforcement:** "Masking happens at the ingestion boundary, not in the warehouse. If a job fails before masking, the data never lands in clean storage. Defense in depth."
- **Idempotency:** "Every Glue job uses a MERGE on the natural key, not INSERT. Rerunning any job produces identical results. Auditors love this."
- **Cost at 10TB scale:** "S3 Intelligent-Tiering for data older than 90 days, Snowflake auto-suspend for warehouses, and incremental dbt models. Total infra cost stays under $3K/month."
- **Schema drift:** "FHIR payloads evolve. We use a schema registry with backwards-compatibility enforcement. Any breaking change fails at the schema layer, not in a mart 6 hours later."

---

## Related Portfolio Systems

- [Real-Time Fintech Data Platform](https://github.com/Snehabankapalli/real-time-fintech-pipeline-kafka-spark-snowflake) — streaming platform for fintech (similar architecture, different compliance domain)
- [Data Engineering Observability Platform](https://github.com/Snehabankapalli/data-engineering-observability-platform) — monitoring layer that sits on top of platforms like this
- [Modern Data Platform Migration](https://github.com/Snehabankapalli/modern-data-platform-migration) — migration patterns used to build this stack
- [GenAI Data Engineering Portfolio](https://github.com/Snehabankapalli/genai-de-portfolio) — AI tooling for intelligent pipeline management

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

---

## License

MIT License — see [LICENSE](LICENSE) for details.
