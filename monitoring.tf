############################################
# Monitoring: CloudWatch Alarms + EventBridge → SNS
############################################

# SNS topic for alerts
resource "aws_sns_topic" "ops_alerts" {
  name = "ops-alerts"
}

# (Optional) subscribe your email; replace with your address
# resource "aws_sns_topic_subscription" "ops_email" {
#   topic_arn = aws_sns_topic.ops_alerts.arn
#   protocol  = "email"
#   endpoint  = "you@example.com"
# }

# Lambda Errors alarm (fires if any errors in 5 minutes)
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "lambda-s3-raw-start-glue-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda reported errors"
  dimensions = {
    FunctionName = aws_lambda_function.trigger_glue.function_name
  }
  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]
}

# Lambda Throttles alarm (helps catch surges/limits)
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "lambda-s3-raw-start-glue-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda throttles detected"
  dimensions = {
    FunctionName = aws_lambda_function.trigger_glue.function_name
  }
  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]
}

# Glue job failure notifications via EventBridge → SNS
resource "aws_cloudwatch_event_rule" "glue_job_failed" {
  name        = "glue-job-failed"
  description = "Notify on Glue job failures"
  event_pattern = jsonencode({
    "source" : ["aws.glue"],
    "detail-type" : ["Glue Job State Change"],
    "detail" : {
      "jobName" : [aws_glue_job.log_etl.name],
      "state" : ["FAILED", "TIMEOUT", "ERROR", "STOPPED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "glue_job_failed_to_sns" {
  rule      = aws_cloudwatch_event_rule.glue_job_failed.name
  target_id = "sns"
  arn       = aws_sns_topic.ops_alerts.arn
}
