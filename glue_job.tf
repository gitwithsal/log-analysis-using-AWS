# Upload the ETL script from local repo to clean bucket
resource "aws_s3_object" "glue_script" {
  bucket       = aws_s3_bucket.clean_bucket.id
  key          = "scripts/etl_transform.py"
  source       = "${path.module}/glue_scripts_etl_transform.py"
  content_type = "text/x-python"
  etag         = filemd5("${path.module}/glue_scripts_etl_transform.py")
}

resource "aws_glue_job" "log_etl" {
  name              = "log-etl-job"
  role_arn          = aws_iam_role.glue_role.arn
  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.clean_bucket.bucket}/${aws_s3_object.glue_script.key}"
  }

  default_arguments = {
    "--job-language"                          = "python"
    "--enable-metrics"                        = ""
    "--enable-continuous-cloudwatch-log"      = "true"
    "--enable-glue-datacatalog"               = ""
    "--TempDir"                               = "s3://${aws_s3_bucket.clean_bucket.bucket}/tmp/"
    "--enable-s3-parquet-optimized-committer" = "true"
    "--conf"                                  = "spark.sql.sources.partitionOverwriteMode=dynamic"
  }

  depends_on = [aws_s3_object.glue_script]
}
