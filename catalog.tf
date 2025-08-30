############################################
# Glue Data Catalog: Database + Crawler + Trigger
############################################

# Logical container for your tables
resource "aws_glue_catalog_database" "logs_db" {
  name = "logs_db"
}

# Crawler over your clean Parquet output
resource "aws_glue_crawler" "logs_clean_crawler" {
  name          = "logs-clean-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.logs_db.name

  # s3_target  
  s3_target {
    path       = "s3://${aws_s3_bucket.clean_bucket.bucket}/clean/"
    exclusions = ["_bad_records/*", "tmp/*"]
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DELETE_FROM_DATABASE"
  }

  # Crawls everything initially; switch to CRAWL_NEW_FOLDERS_ONLY for speed later
  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"
  }

  configuration = jsonencode({
    Version = 1.0,
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })
}

# auto-run the crawler when the ETL job succeeds
resource "aws_glue_trigger" "after_etl_crawl" {
  name    = "after-etl-crawl"
  type    = "CONDITIONAL"
  enabled = true

  actions {
    crawler_name = aws_glue_crawler.logs_clean_crawler.name
  }

  predicate {
    conditions {
      job_name = aws_glue_job.log_etl.name
      state    = "SUCCEEDED"
    }
  }
}
