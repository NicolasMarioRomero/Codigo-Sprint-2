# deployment/asr29/deployment.tf
# Infraestructura para el experimento ASR29 — Vault de credenciales seguro
# 7 EC2 + 1 RDS PostgreSQL en AWS Academy
#
# Instancias:
#   1 × App Django    (API + auth)
#   1 × RabbitMQ      (broker)
#   1 × Detector      (consumidor de usos → reglas de anomalía)
#   1 × Revoker       (consumidor de anomalías → revocación)
#   1 × Notifier      (consumidor de anomalías → alertas)
#   1 × Producer      (simulador de tráfico)
#   1 × Kong          (API Gateway)
#   1 × RDS PostgreSQL (base de datos gestionada)

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region"    { default = "us-east-1" }
variable "key_name"      { description = "Nombre del key pair EC2" }
variable "ami_id"        { default = "ami-0fc5d935ebf8bc3bc" }  # Ubuntu 22.04 us-east-1
variable "instance_type" { default = "t2.medium" }
variable "db_password"   { description = "Contraseña para RDS PostgreSQL" }
variable "vault_key"     { description = "Fernet key para VAULT_KEY" }
variable "auth0_domain"  { description = "Dominio Auth0" }
variable "auth0_client_id" { description = "Client ID Auth0" }

locals {
  project = "bite-asr29"
  tags    = { Project = local.project, Experiment = "ASR29" }
}

# ── VPC y Security Group ──────────────────────────────────────────────────────

resource "aws_security_group" "asr29_sg" {
  name        = "${local.project}-sg"
  description = "ASR29 - Credenciales seguras"
  tags        = local.tags

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 8000
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 5672
    to_port     = 5672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── RDS PostgreSQL ────────────────────────────────────────────────────────────

resource "aws_db_instance" "postgres" {
  identifier             = "${local.project}-db"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = "bite_db"
  username               = "postgres"
  password               = var.db_password
  skip_final_snapshot    = true
  publicly_accessible    = true
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = local.tags
}

# ── EC2: RabbitMQ ─────────────────────────────────────────────────────────────

resource "aws_instance" "rabbitmq" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-rabbitmq" })

  user_data = file("${path.module}/user_data_rabbit.sh")
}

# ── EC2: App Django ───────────────────────────────────────────────────────────

resource "aws_instance" "app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-app" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_app.sh", {
    DB_HOST       = aws_db_instance.postgres.address
    DB_PASSWORD   = var.db_password
    RABBIT_HOST   = aws_instance.rabbitmq.private_ip
    VAULT_KEY     = var.vault_key
    AUTH0_DOMAIN  = var.auth0_domain
    AUTH0_CLIENT  = var.auth0_client_id
  })
}

# ── EC2: Detector ─────────────────────────────────────────────────────────────

resource "aws_instance" "detector" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-detector" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_detector.sh", {
    DB_HOST     = aws_db_instance.postgres.address
    DB_PASSWORD = var.db_password
    RABBIT_HOST = aws_instance.rabbitmq.private_ip
    VAULT_KEY   = var.vault_key
  })
}

# ── EC2: Revoker ──────────────────────────────────────────────────────────────

resource "aws_instance" "revoker" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-revoker" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_revoker.sh", {
    DB_HOST     = aws_db_instance.postgres.address
    DB_PASSWORD = var.db_password
    RABBIT_HOST = aws_instance.rabbitmq.private_ip
    VAULT_KEY   = var.vault_key
  })
}

# ── EC2: Notifier ─────────────────────────────────────────────────────────────

resource "aws_instance" "notifier" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr29_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-notifier" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_notifier.sh", {
    DB_HOST          = aws_db_instance.postgres.address
    DB_PASSWORD      = var.db_password
    RABBIT_HOST      = aws_instance.rabbitmq.private_ip
    VAULT_KEY        = var.vault_key
    AUTH0_DOMAIN     = var.auth0_domain
    AUTH0_MGMT_TOKEN = ""
  })
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "app_public_ip"      { value = aws_instance.app.public_ip }
output "rabbitmq_public_ip" { value = aws_instance.rabbitmq.public_ip }
output "detector_public_ip" { value = aws_instance.detector.public_ip }
output "revoker_public_ip"  { value = aws_instance.revoker.public_ip }
output "notifier_public_ip" { value = aws_instance.notifier.public_ip }
output "rds_endpoint"       { value = aws_db_instance.postgres.address }
