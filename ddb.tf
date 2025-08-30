# ddb.tf
resource "aws_dynamodb_table" "processed_keys" {
  name         = "log-object-status"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "object_key"

  attribute {
    name = "object_key"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Optional but helpful for recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "Idempotency Key Store"
    Environment = "dev"
    Project     = "Serverless Log Pipeline"
  }
}
