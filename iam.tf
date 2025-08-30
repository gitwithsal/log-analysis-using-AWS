# Lambda role
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "lambda-trigger-glue-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_policy" {
  statement { # CloudWatch logs
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }

  statement { # Start Glue job
    actions   = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns"]
    resources = [aws_glue_job.log_etl.arn]
  }

  statement { # Read raw object metadata
    actions = ["s3:GetObject", "s3:GetObjectTagging", "s3:HeadObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.raw_bucket.arn,
      "${aws_s3_bucket.raw_bucket.arn}/*",
    ]
  }

  statement { # DynamoDB idempotency
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.processed_keys.arn]
  }
}

resource "aws_iam_policy" "lambda_inline" {
  name   = "lambda-trigger-glue-policy"
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_inline.arn
}

# Glue job role
data "aws_iam_policy_document" "glue_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_role" {
  name               = "AWSGlueServiceRole-LogETL"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

data "aws_iam_policy_document" "glue_policy" {
  statement { # Read raw
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.raw_bucket.arn,
      "${aws_s3_bucket.raw_bucket.arn}/*",
    ]
  }

  # Read/Write clean (now includes GetObject so Glue can download the script)
  statement {
    sid = "ReadWriteCleanBucket"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:AbortMultipartUpload",
      "s3:ListBucketMultipartUploads"
    ]
    resources = [
      aws_s3_bucket.clean_bucket.arn,
      "${aws_s3_bucket.clean_bucket.arn}/*",
    ]
  }

  # Logs and Glue basics
  statement {
    sid       = "LogsAndGlueBasics"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "glue:*"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "glue_inline" {
  name   = "glue-log-etl-policy"
  policy = data.aws_iam_policy_document.glue_policy.json
}

resource "aws_iam_role_policy_attachment" "glue_attach" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_inline.arn
}
