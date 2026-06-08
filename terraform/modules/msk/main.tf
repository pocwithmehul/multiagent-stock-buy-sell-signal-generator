# MSK Module for Stock Signal API
# ================================
# Creates Amazon MSK (Managed Streaming for Apache Kafka) cluster.

locals {
  tags = merge(var.tags, {
    Module = "msk"
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# Security Group
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_security_group" "msk" {
  name_prefix = "${var.name}-msk-"
  description = "Security group for MSK cluster"
  vpc_id      = var.vpc_id

  tags = merge(local.tags, {
    Name = "${var.name}-msk-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "msk_ingress_kafka" {
  type              = "ingress"
  from_port         = 9092
  to_port           = 9098
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.msk.id
  description       = "Kafka ports from VPC"
}

resource "aws_security_group_rule" "msk_ingress_zookeeper" {
  type              = "ingress"
  from_port         = 2181
  to_port           = 2181
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.msk.id
  description       = "Zookeeper from VPC"
}

resource "aws_security_group_rule" "msk_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.msk.id
  description       = "Allow all outbound"
}

# ─────────────────────────────────────────────────────────────────────────────
# CloudWatch Log Group
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/${var.name}"
  retention_in_days = var.log_retention_days

  tags = local.tags
}

# ─────────────────────────────────────────────────────────────────────────────
# MSK Configuration
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_msk_configuration" "main" {
  name              = "${var.name}-config"
  kafka_versions    = [var.kafka_version]
  description       = "MSK configuration for ${var.name}"

  server_properties = <<PROPERTIES
auto.create.topics.enable=true
delete.topic.enable=true
default.replication.factor=${var.broker_count > 2 ? 3 : 2}
min.insync.replicas=${var.broker_count > 2 ? 2 : 1}
num.partitions=3
log.retention.hours=168
log.segment.bytes=1073741824
PROPERTIES
}

# ─────────────────────────────────────────────────────────────────────────────
# MSK Cluster
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_msk_cluster" "main" {
  cluster_name           = var.name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.private_subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.broker_volume_size
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.main.arn
    revision = aws_msk_configuration.main.latest_revision
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }

    encryption_at_rest_kms_key_arn = var.kms_key_arn
  }

  client_authentication {
    sasl {
      iam   = true
      scram = false
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = var.enable_monitoring
      }
      node_exporter {
        enabled_in_broker = var.enable_monitoring
      }
    }
  }

  tags = local.tags
}
