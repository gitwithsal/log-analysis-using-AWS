## Serverless Log Analytics Pipeline (AWS + Terraform)
A log analysis pipeline where raw JSON logs land in an S3 raw bucket and an S3 event notification invokes a Lambda. The Lambda starts an AWS Glue ETL job. Glue reads the raw files, transforms and partitions them (e.g., by date/hour), writes curated outputs to S3 clean/, and updates the Glue Data Catalog so the data is queryable. CloudWatch captures logs/metrics. All resources (S3, Lambda, IAM, Glue job & Catalog, notifications, basic monitoring) are defined in this repo’s Terraform.

# Repo Layout
.
├─ build/                         # packaged artifacts (e.g., trigger_glue.zip)
├─ .gitattributes
├─ .terraform.lock.hcl            # provider lock (commit this)
├─ catalog.tf                     # Glue Data Catalog DB/Tables
├─ ddb.tf                         # DynamoDB table for Lambda de-duplication
├─ git_ignore.gitignore           # rename to .gitignore (see note below)
├─ glue_job.tf                    # Glue job definition
├─ glue_scripts_etl_transform.py  # Glue ETL script (source)
├─ iam.tf                         # IAM roles & policies (Lambda, Glue, etc.)
├─ lambda_src_trigger_glue.py     # Lambda handler (source)
├─ lambda.tf                      # Lambda function, permissions, packaging
├─ log_gen.py                     # (optional) local log generator for testing
├─ monitoring.tf                  # CloudWatch: log groups/alarms (if any)
├─ outputs.tf                     # Terraform outputs
├─ providers.tf                   # Terraform providers & backends
├─ s3_notifications.tf            # S3 → event → Lambda (or EventBridge) wiring
├─ S3.tf                          # S3 buckets (raw, clean, code)
└─ variables.tf                   # all configurable inputs

# Prerequisites
- Terraform ≥ 1.5
- AWS credentials with permissions to create S3, Lambda, Glue, EventBridge/S3 notifications, DynamoDB, CloudWatch, IAM
- A region selected in providers.tf or via TF variables

# 🧩 Components

- S3 (Raw & Clean): Versioned buckets with server-side encryption and lifecycle rules. Raw receives raw/*.json.gz (or JSON). Clean stores partitioned outputs.
- EventBridge Rule: source=aws.s3, detail-type=Object Created, filters by bucket and key prefix/suffix.
- Lambda (s3-raw-start-glue)
- Glue Job:
  Reads from S3 raw, transforms/validates, writes to S3 clean with partitioning (dt, hr, optional other keys).
  Updates Glue Data Catalog (database + table).
- CloudWatch: Logs for Lambda & Glue, metrics, and optional alarms.

# What Happens After Deploy
- New objects landing in S3 (raw) under your configured prefix/suffix emit an event.
- Lambda receives the event, de-dupes via DynamoDB, and starts the Glue job once per unique object.
- Glue reads from raw, transforms, and writes to S3 (clean) (typically partitioned by date/hour).
- Glue Data Catalog is updated so the curated data is queryable (e.g., via Athena).
- CloudWatch holds logs for Lambda and Glue.

# 🔍 Observability Checklist
- Lambda logs: /aws/lambda/s3-raw-start-glue
- Glue job runs: look for latest SUCCEEDED/FAILED run and arguments
- EventBridge metrics: matched events and target invocations
- S3: verify new files appear in clean/ partitions after a raw drop
