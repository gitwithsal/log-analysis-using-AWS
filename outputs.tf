output "raw_bucket" {
  value = aws_s3_bucket.raw_bucket.bucket
}

output "clean_bucket" {
  value = aws_s3_bucket.clean_bucket.bucket
}

output "glue_job_name" {
  value = aws_glue_job.log_etl.name
}

output "lambda_name" {
  value = aws_lambda_function.trigger_glue.function_name
}

output "catalog_db" {
  value = aws_glue_catalog_database.logs_db.name
}

output "clean_crawler" {
  value = aws_glue_crawler.logs_clean_crawler.name
}

output "alerts_topic_arn" {
  value = aws_sns_topic.ops_alerts.arn
}

output "lambda_errors_alb" {
  value = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}

output "lambda_throttles_alb" {
  value = aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name
}
