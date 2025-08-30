# Package a single file into the ZIP (OS-safe absolute paths)
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = abspath("${path.module}/lambda_src_trigger_glue.py") # <-- your file
  output_path = abspath("${path.module}/build/trigger_glue.zip")
}

resource "aws_lambda_function" "trigger_glue" {
  function_name = "s3-raw-start-glue"
  role          = aws_iam_role.lambda_exec.arn

  # For a single-file zip named lambda_src_trigger_glue.py:
  # handler must match the module name (file basename without .py)
  handler = "lambda_src_trigger_glue.handler"
  runtime = "python3.12"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      GLUE_JOB_NAME = aws_glue_job.log_etl.name
      OUTPUT_PREFIX = "s3://${aws_s3_bucket.clean_bucket.bucket}/clean/"
      USE_DDB       = "true"
      DDB_TABLE     = aws_dynamodb_table.processed_keys.name
    }
  }

  # Removed reserved_concurrent_executions to avoid Unreserved < 10 error
}
