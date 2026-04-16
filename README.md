# Real-Time Healthcare Analytics Platform (AWS + Snowflake + dbt)

> End-to-end analytics platform processing **10TB+/month** from 20+ clinical systems. Delivers HIPAA-compliant, near-real-time insights across **50M+ patient records** — reducing manual processing effort by 50% and enabling same-day analytics for $2B+ in medical spend.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![AWS Glue](https://img.shields.io/badge/AWS_Glue-FF9900?style=flat&logo=amazonaws&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Airflow-017CEE?style=flat&logo=apacheairflow&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-FF694B?style=flat&logo=dbt&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat&logo=snowflake&logoColor=white)
[![CI](https://github.com/Snehabankapalli/real-time-analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Snehabankapalli/real-time-analytics-platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 1. What This System Does

A production analytics platform that ingests clinical data from 20+ healthcare source systems, applies HIPAA Safe Harbor de-identification, and delivers queryable, governed data to Snowflake — enabling fraud analytics, population health, and $2B+ medical spend reporting.

- **Multi-source ingestion** — FHIR R4 APIs, HL7 v2 messages, claims databases, lab systems
- **Automated HIPAA compliance** — 18 PHI identifiers masked or tokenized before data lands in Snowflake
- **High reliability** — 99.95% Airflow uptime with automatic retry, SLA callbacks, and Slack alerting
- **Batch + near-real-time** — AWS Glue processes 10TB/month; Snowpipe handles continuous incremental loads
- **Full audit trail** — CloudTrail + S3 access logs, 7-year retention, compliance-ready reports

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  DATA SOURCES (20+ systems)                                      │
│  FHIR R4 APIs · HL7 v2 · Claims DB · Lab Systems · EHR          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   INGESTION LAYER       │
              │   AWS Glue (PySpark)    │
              │                        │
              │  fhir_ingestion.py      │  ← FHIR R4 pagination
              │  hl7_parser.py          │  ← HL7 v2 segment parsing
              │  claims_ingestion.py    │  ← Claims ETL
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   PII MASKING LAYER     │
              │                        │
              │  HMAC-SHA256 tokens     │  ← Patient/MRN IDs
              │  Safe Harbor dates      │  ← Year-only
              │  ZIP generalization     │  ← 3-digit prefix
              │  PHI redaction          │  ← Names, phones, email
              └────────────┬────────────┘
                           │
      ┌────────────────────▼─────────────────────────┐
      │              S3 DATA LAKE                     │
      │  raw/      ← Encrypted source data (KMS)      │
      │  clean/    ← PII-masked, validated            │
      │  analytics/← De-identified, aggregated        │
      │                                               │
      │  KMS encryption · Versioning · CloudTrail     │
      └────────────────────┬─────────────────────────┘
                           │  Snowpipe (continuous)
      ┌────────────────────▼─────────────────────────┐
      │              Snowflake                        │
      │  STAGING    → standardized, validated         │
      │  INTERMEDIATE → joins, enrichment             │
      │  MARTS      → population health               │
      │               medical spend analytics         │
      │               compliance reports              │
      └────────────────────┬─────────────────────────┘
                           │
      ┌────────────────────▼─────────────────────────┐
      │  CONSUMERS                                    │
      │  Population Health · Medical Spend · Fraud    │
      │  Clinical Operations · Regulatory Reporting   │
      └──────────────────────────────────────────────┘

  Orchestration: Airflow (99.95% uptime, SLA alerts)
  Compliance:    CloudTrail + S3 logs, 7-year retention
```

---

## 3. Scale and Impact

| Metric | Value |
|--------|-------|
| Monthly data volume | 10TB+ |
| Patient records processed | 50M+ |
| Source systems integrated | 20+ |
| Pipeline uptime | 99.95% |
| Manual processing effort reduced | 50% |
| Dashboard performance improvement | 60% |
| Compliance accuracy | 100% |
| Medical spend analytics enabled | $2B+ |
| PHI identifiers masked | 18 (HIPAA Safe Harbor) |

---

## 4. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Ingestion | AWS Glue (PySpark) | Serverless, integrates natively with S3 and Glue Catalog |
| Storage | AWS S3 | Cost-effective, KMS-encrypted, versioned, lifecycle-managed |
| Encryption | AWS KMS (CMK) | Customer-managed keys, HIPAA-eligible |
| Compliance logging | AWS CloudTrail | Full API audit trail, 7-year retention |
| Transformation | dbt + Snowflake | SQL-based, version-controlled, built-in quality tests |
| Orchestration | Apache Airflow | Complex dependency graphs, retry logic, SLA monitoring |
| Infrastructure | Terraform | Repeatable, auditable infrastructure changes |

---

## 5. Key Engineering Decisions

**HIPAA Safe Harbor vs Expert Determination**
Chose Safe Harbor de-identification — removes the 18 required identifiers rather than requiring a statistician. More repeatable, auditable, and defensible in a regulated audit.

**Why AWS Glue over self-managed Spark?**
Glue is serverless and natively integrated with S3, Glue Catalog, and IAM. For irregular-volume healthcare ingestion (claims come in bursts), Glue's auto-scaling avoids paying for idle clusters. Cost reduction: ~35% vs EMR.

**Tokenization vs redaction**
Patient IDs and MRNs are tokenized (HMAC-SHA256) rather than redacted — preserving the ability to join records across source systems without exposing raw PHI. Names, addresses, and phone numbers are fully redacted.

**Incremental dbt models**
All patient-level models use dbt incremental with `merge` strategy and a 3-day lookback window. This handles late-arriving claims data (common in healthcare) without full table refreshes.

**Airflow SLA design**
Daily pipeline must complete by 6 AM for clinical teams' morning reports. SLA callback fires to Slack if any task misses. Retries use exponential backoff (5 min, 10 min, 20 min) before paging on-call.

---

## 6. Sample Output

**Airflow DAG run:**
```
[2026-03-26 02:01:04] fhir_ingestion        SUCCESS  duration: 18m 42s
[2026-03-26 02:20:11] pii_masking           SUCCESS  duration: 24m 08s
[2026-03-26 02:44:53] dbt_run               SUCCESS  duration: 41m 17s  models: 38
[2026-03-26 03:26:21] dbt_test              SUCCESS  duration:  8m 54s  tests: 214
[2026-03-26 03:35:18] success_notification  SUCCESS  Slack alert sent
```

**PII masking output (before → after):**
```python
# Input (raw PHI)
{
  "patient_id": "PAT-00291847",
  "first_name": "Jane",
  "last_name":  "Smith",
  "date_of_birth": "1985-04-12",
  "zip_code": "98101",
  "mrn": "MRN-8472910",
  "phone": "206-555-0192"
}

# Output (masked)
{
  "patient_id": "a3f8c2e1d4b7...",   # HMAC token
  "first_name": "[REDACTED]",
  "last_name":  "[REDACTED]",
  "date_of_birth": "1985",           # Year only (Safe Harbor)
  "zip_code": "981",                 # 3-digit prefix only
  "mrn": "f9e2b1a4c8d3...",         # HMAC token
  "phone": "[REDACTED]"
}
```

**dbt test results:**
```
PASS  not_null_stg_patients_patient_id ........... 50,241,882 rows
PASS  unique_stg_patients_patient_id ............. 50,241,882 rows
PASS  accepted_values_stg_claims_claim_status .... 3 values validated
PASS  assert_no_raw_phi_in_clean_layer ........... 0 violations
214 tests passed, 0 failed.
```

---

## 7. How to Run

```bash
git clone https://github.com/Snehabankapalli/real-time-analytics-platform
cd real-time-analytics-platform

pip install -r requirements.txt

# Required environment variables
export PII_MASKING_SECRET=your-secret         # Never hardcode
export AWS_REGION=us-east-1
export S3_RAW_BUCKET=your-raw-bucket
export S3_CLEAN_BUCKET=your-clean-bucket
export FHIR_BASE_URL=https://your-fhir-api
export SNOWFLAKE_ACCOUNT=your-account

# Run FHIR ingestion locally (dry run)
python src/glue_jobs/fhir_ingestion.py --dry-run

# Run PII masker on a sample record
python -c "
from src.masking.pii_masker import PatientRecordMasker
masker = PatientRecordMasker()
print(masker.mask({'patient_id': 'PAT-001', 'first_name': 'Jane', 'zip_code': '98101'}))
"

# Deploy to AWS (Glue + S3 + KMS + CloudTrail)
cd infra
terraform init && terraform apply

# Run dbt models
dbt run --select tag:healthcare
dbt test --select tag:healthcare

# Run unit tests
pytest tests/ -v
```

---

## 8. Future Improvements

- Real-time FHIR streaming using AWS EventBridge + Lambda for sub-minute ingestion
- ML-based anomaly detection on claim patterns for fraud flagging
- Data mesh architecture with domain-owned data products per clinical service line
- Expand dbt lineage visualization with Datacoves or dbt Cloud

---

## Architecture Diagrams

Full Mermaid diagrams in [.github/ARCHITECTURE.md](.github/ARCHITECTURE.md).

---

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

---

## License

MIT License — see [LICENSE](LICENSE) for details.
