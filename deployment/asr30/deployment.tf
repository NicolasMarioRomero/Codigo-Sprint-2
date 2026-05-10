# deployment/asr30/deployment.tf
# Infraestructura para el experimento ASR30 — Enmascaramiento de logs
# 6 EC2: 2 App + 1 RabbitMQ + 1 LogStore + 1 Kong + 1 Producer

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

variable "aws_region"    { default = "us-east-1" }
variable "key_name"      { description = "Nombre del key pair EC2" }
variable "ami_id"        { default = "ami-0fc5d935ebf8bc3bc" }
variable "instance_type" { default = "t2.medium" }
variable "db_password"   { description = "Contraseña RDS" }
variable "vault_key"     { description = "Fernet key" }
variable "auth0_domain"  { description = "Dominio Auth0" }
variable "auth0_client_id" {}

locals {
  project = "bite-asr30"
  tags    = { Project = local.project, Experiment = "ASR30" }
}

resource "aws_security_group" "asr30_sg" {
  name = "${local.project}-sg"
  tags = local.tags

  ingress { from_port = 22;    to_port = 22;    protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 80;    to_port = 80;    protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 8000;  to_port = 8001;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 5432;  to_port = 5432;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 5672;  to_port = 5672;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 15672; to_port = 15672; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0;     to_port = 0;     protocol = "-1";  cidr_blocks = ["0.0.0.0/0"] }
}

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
  vpc_security_group_ids = [aws_security_group.asr30_sg.id]
  tags                   = local.tags
}

resource "aws_instance" "rabbitmq" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr30_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-rabbitmq" })
  user_data              = file("${path.module}/../asr29/user_data_rabbit.sh")
}

resource "aws_instance" "app1" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr30_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-app1" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_app.sh", {
    DB_HOST     = aws_db_instance.postgres.address
    DB_PASSWORD = var.db_password
    RABBIT_HOST = aws_instance.rabbitmq.private_ip
    VAULT_KEY   = var.vault_key
    AUTH0_DOMAIN   = var.auth0_domain
    AUTH0_CLIENT   = var.auth0_client_id
    APP_PORT    = 8000
  })
}

resource "aws_instance" "app2" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr30_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-app2" })
  depends_on             = [aws_instance.rabbitmq, aws_db_instance.postgres]

  user_data = templatefile("${path.module}/user_data_app.sh", {
    DB_HOST     = aws_db_instance.postgres.address
    DB_PASSWORD = var.db_password
    RABBIT_HOST = aws_instance.rabbitmq.private_ip
    VAULT_KEY   = var.vault_key
    AUTH0_DOMAIN   = var.auth0_domain
    AUTH0_CLIENT   = var.auth0_client_id
    APP_PORT    = 8000
  })
}

resource "aws_instance" "log_store" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.asr30_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-logstore" })
  depends_on             = [aws_instance.rabbitmq]

  user_data = templatefile("${path.module}/user_data_log_store.sh", {
    RABBIT_HOST = aws_instance.rabbitmq.private_ip
    DB_HOST     = aws_db_instance.postgres.address
    DB_PASSWORD = var.db_password
    VAULT_KEY   = var.vault_key
  })
}

output "app1_public_ip"     { value = aws_instance.app1.public_ip }
output "app2_public_ip"     { value = aws_instance.app2.public_ip }
output "rabbitmq_public_ip" { value = aws_instance.rabbitmq.public_ip }
output "log_store_public_ip" { value = aws_instance.log_store.public_ip }
output "rds_endpoint"       { value = aws_db_instance.postgres.address }
