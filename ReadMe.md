## Serverless Log Analytics Pipeline (AWS + Terraform)
A log analysis pipeline where raw JSON logs land in an S3 raw bucket and an S3 event notification invokes a Lambda. The Lambda starts an AWS Glue ETL job. Glue reads the raw files, transforms and partitions them (e.g., by date/hour), writes curated outputs to S3 clean/, and updates the Glue Data Catalog so the data is queryable. CloudWatch captures logs/metrics. All resources (S3, Lambda, IAM, Glue job & Catalog, notifications, basic monitoring) are defined in this repo’s Terraform.

# Repo Layout
Repo Layout

build/ — Packaged artifacts (e.g., trigger_glue.zip). Usually git-ignored.

.gitattributes — Optional text/line-ending settings.

.terraform.lock.hcl — Provider lock file (commit this).

catalog.tf — Glue Data Catalog database and tables.

ddb.tf — DynamoDB table for Lambda de-duplication.

git_ignore.gitignore — Rename to .gitignore so Git respects it.

glue_job.tf — AWS Glue job definition.

glue_scripts_etl_transform.py — Glue ETL script (source).

iam.tf — IAM roles and policies for Lambda/Glue/etc.

lambda_src_trigger_glue.py — Lambda handler (source).

lambda.tf — Lambda function, permissions, and packaging.

log_gen.py — Optional local log generator for testing.

monitoring.tf — CloudWatch log groups and optional alarms.

outputs.tf — Terraform outputs.

providers.tf — Terraform provider (and optional backend) config.

s3_notifications.tf — S3 event/EventBridge wiring to trigger Lambda.

S3.tf — S3 buckets (raw, clean, code).

variables.tf — Configurable input variables.

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
