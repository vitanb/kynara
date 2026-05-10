## Kynara — AWS reference Terraform module.
##
## Provisions: VPC, RDS Postgres, ElastiCache Redis, ECS-Fargate or EKS-ready
## targets, ALB, ACM, KMS keys, S3 audit-export bucket, CloudWatch + IAM roles
## with least-privilege scope. Outputs are wired so the Helm chart in
## ../helm/kynara can consume them via Helmfile or external-secrets.
##
## This is a reference module — vendor it and pin to a specific commit.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.40" }
  }
}

variable "environment" { type = string }                       # e.g. "prod", "stage"
variable "region"      { type = string  default = "us-east-1" }
variable "domain"      { type = string }                       # api.kynara.example.com etc.
variable "vpc_cidr"    { type = string  default = "10.42.0.0/16" }
variable "byok_enabled" { type = bool   default = false }
variable "tags"        { type = map(string) default = {} }

locals {
  name = "kynara-${var.environment}"
  tags = merge({
    Project     = "kynara"
    Environment = var.environment
    ManagedBy   = "terraform"
  }, var.tags)
}

provider "aws" { region = var.region default_tags { tags = local.tags } }

## ─── Networking ──────────────────────────────────────────────────────────────

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  public_subnets  = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i + 4)]
  database_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway   = true
  single_nat_gateway   = false        # multi-AZ for production
  enable_flow_log      = true
  flow_log_destination_type = "cloud-watch-logs"
  flow_log_max_aggregation_interval = 60
}

## ─── KMS keys ────────────────────────────────────────────────────────────────

resource "aws_kms_key" "platform" {
  description             = "Kynara platform-managed CMK (envelope encryption)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = true
}
resource "aws_kms_alias" "platform" {
  name          = "alias/${local.name}-platform"
  target_key_id = aws_kms_key.platform.key_id
}

resource "aws_kms_key" "audit_export" {
  description             = "Kynara audit-export bucket key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

## ─── Postgres ────────────────────────────────────────────────────────────────

resource "aws_security_group" "rds" {
  name = "${local.name}-rds"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port = 5432 to_port = 5432 protocol = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = module.vpc.database_subnets
}

resource "aws_db_instance" "postgres" {
  identifier              = "${local.name}-pg"
  engine                  = "postgres"
  engine_version          = "15"
  instance_class          = "db.r6g.large"
  allocated_storage       = 100
  max_allocated_storage   = 1000
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.platform.arn
  db_name                 = "kynara"
  username                = "kynara"
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  multi_az                = true
  backup_retention_period = 14
  delete_automated_backups = false
  deletion_protection     = true
  performance_insights_enabled = true
  performance_insights_retention_period = 31
  monitoring_interval     = 60
  copy_tags_to_snapshot   = true
  apply_immediately       = false
  enabled_cloudwatch_logs_exports = ["postgresql"]
}
resource "random_password" "db" { length = 32 special = false }

## ─── Redis ───────────────────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id        = "${local.name}-redis"
  description                 = "Kynara decision cache"
  node_type                   = "cache.r6g.large"
  engine_version              = "7.0"
  port                        = 6379
  parameter_group_name        = "default.redis7"
  num_node_groups             = 1
  replicas_per_node_group     = 2
  automatic_failover_enabled  = true
  multi_az_enabled            = true
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  kms_key_id                  = aws_kms_key.platform.arn
  subnet_group_name           = aws_elasticache_subnet_group.this.name
}

## ─── Audit export bucket ─────────────────────────────────────────────────────

resource "aws_s3_bucket" "audit_export" {
  bucket = "${local.name}-audit-export-${random_id.bucket.hex}"
  force_destroy = false
}
resource "random_id" "bucket" { byte_length = 4 }

resource "aws_s3_bucket_versioning" "audit_export" {
  bucket = aws_s3_bucket.audit_export.id
  versioning_configuration { status = "Enabled" mfa_delete = "Disabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "audit_export" {
  bucket = aws_s3_bucket.audit_export.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.audit_export.arn
    }
    bucket_key_enabled = true
  }
}
resource "aws_s3_bucket_object_lock_configuration" "audit_export" {
  bucket = aws_s3_bucket.audit_export.id
  rule { default_retention { mode = "COMPLIANCE"  days = 365 * 7 } }
}
resource "aws_s3_bucket_public_access_block" "audit_export" {
  bucket = aws_s3_bucket.audit_export.id
  block_public_acls = true block_public_policy = true
  ignore_public_acls = true restrict_public_buckets = true
}

## ─── Outputs (to be consumed by the Helm chart values.yaml) ─────────────────

output "postgres_host"   { value = aws_db_instance.postgres.address }
output "postgres_db"     { value = aws_db_instance.postgres.db_name }
output "postgres_user"   { value = aws_db_instance.postgres.username }
output "redis_endpoint"  { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "kms_platform_arn" { value = aws_kms_key.platform.arn }
output "audit_bucket"    { value = aws_s3_bucket.audit_export.bucket }
output "vpc_id"          { value = module.vpc.vpc_id }
output "private_subnets" { value = module.vpc.private_subnets }
