############################################
# Buckets
############################################

resource "aws_s3_bucket" "raw_bucket" {
  bucket        = var.raw_bucket_name
  force_destroy = true
  tags = {
    Name        = "sal-raw-log"
    Environment = "dev"
    Project     = "Serverless Log Pipeline"
  }
}

resource "aws_s3_bucket" "clean_bucket" {
  bucket        = var.clean_bucket_name
  force_destroy = true
  tags = {
    Name        = "sal-clean-log"
    Environment = "dev"
    Project     = "Serverless Log Pipeline"
  }
}

############################################
# Public access blocks
############################################

resource "aws_s3_bucket_public_access_block" "raw_pab" {
  bucket                  = aws_s3_bucket.raw_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "clean_pab" {
  bucket                  = aws_s3_bucket.clean_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

############################################
# Default encryption (SSE-S3)
############################################

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_enc" {
  bucket = aws_s3_bucket.raw_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clean_enc" {
  bucket = aws_s3_bucket.clean_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

############################################
# Prefixes (folders)
############################################

resource "aws_s3_object" "clean_tmp_prefix" {
  bucket  = aws_s3_bucket.clean_bucket.id
  key     = "tmp/"
  content = "" # create empty placeholder
}

resource "aws_s3_object" "clean_scripts_prefix" {
  bucket  = aws_s3_bucket.clean_bucket.id
  key     = "scripts/"
  content = "" # create empty placeholder
}
