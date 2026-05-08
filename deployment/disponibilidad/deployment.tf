# deployment/disponibilidad/deployment.tf
# Infraestructura para el experimento de Disponibilidad
# MongoDB Sharded Cluster + Replica Sets + Kong + App Django
#
# EC2 instances:
#   1 × Config Server (3 mongod en puertos 27019-27021)
#   3 × Shard (1 Replica Set por shard, 3 nodos cada uno)
#   1 × mongos (query router)
#   1 × App Django
#   1 × Kong API Gateway

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

variable "aws_region"    { default = "us-east-1" }
variable "key_name"      { description = "Key pair EC2" }
variable "ami_id"        { default = "ami-0fc5d935ebf8bc3bc" }
variable "instance_type" { default = "t2.medium" }
variable "db_password"   {}
variable "vault_key"     {}
variable "auth0_domain"  {}
variable "auth0_client_id" {}

locals {
  project = "bite-disponibilidad"
  tags    = { Project = local.project, Experiment = "Disponibilidad" }
}

resource "aws_security_group" "disp_sg" {
  name = "${local.project}-sg"
  tags = local.tags

  ingress { from_port = 22;    to_port = 22;    protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 80;    to_port = 80;    protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 8000;  to_port = 8001;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  # MongoDB ports
  ingress { from_port = 27017; to_port = 27021; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 27100; to_port = 27399; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  # Kong
  ingress { from_port = 8080;  to_port = 8080;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 8444;  to_port = 8444;  protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0;     to_port = 0;     protocol = "-1";  cidr_blocks = ["0.0.0.0/0"] }
}

# ── Config Server ─────────────────────────────────────────────────────────────
resource "aws_instance" "configsvr" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-configsvr" })
  user_data              = file("${path.module}/user_data_configsvr.sh")
}

# ── Shards ────────────────────────────────────────────────────────────────────
resource "aws_instance" "shard1" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-shard1" })
  user_data = templatefile("${path.module}/user_data_shard.sh", {
    SHARD_ID   = "1"
    PORT_START = 27101
  })
}

resource "aws_instance" "shard2" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-shard2" })
  user_data = templatefile("${path.module}/user_data_shard.sh", {
    SHARD_ID   = "2"
    PORT_START = 27201
  })
}

resource "aws_instance" "shard3" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-shard3" })
  user_data = templatefile("${path.module}/user_data_shard.sh", {
    SHARD_ID   = "3"
    PORT_START = 27301
  })
}

# ── mongos ────────────────────────────────────────────────────────────────────
resource "aws_instance" "mongos" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-mongos" })
  depends_on             = [aws_instance.configsvr]

  user_data = templatefile("${path.module}/user_data_mongos.sh", {
    CONFIGSVR_HOST = aws_instance.configsvr.private_ip
    SHARD1_HOST    = aws_instance.shard1.private_ip
    SHARD2_HOST    = aws_instance.shard2.private_ip
    SHARD3_HOST    = aws_instance.shard3.private_ip
  })
}

# ── App Django ────────────────────────────────────────────────────────────────
resource "aws_instance" "app" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-app" })
  depends_on             = [aws_instance.mongos]

  user_data = templatefile("${path.module}/user_data_app.sh", {
    MONGOS_HOST    = aws_instance.mongos.private_ip
    VAULT_KEY      = var.vault_key
    AUTH0_DOMAIN   = var.auth0_domain
    AUTH0_CLIENT   = var.auth0_client_id
    DB_HOST        = ""
    DB_PASSWORD    = var.db_password
    RABBIT_HOST    = ""
  })
}

# ── Kong ──────────────────────────────────────────────────────────────────────
resource "aws_instance" "kong" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.disp_sg.id]
  tags                   = merge(local.tags, { Name = "${local.project}-kong" })
  depends_on             = [aws_instance.app]

  user_data = templatefile("${path.module}/user_data_kong.sh", {
    APP_HOST = aws_instance.app.private_ip
  })
}

# ── Outputs ───────────────────────────────────────────────────────────────────
output "app_public_ip"      { value = aws_instance.app.public_ip }
output "kong_public_ip"     { value = aws_instance.kong.public_ip }
output "mongos_public_ip"   { value = aws_instance.mongos.public_ip }
output "configsvr_public_ip" { value = aws_instance.configsvr.public_ip }
output "shard1_public_ip"   { value = aws_instance.shard1.public_ip }
output "shard2_public_ip"   { value = aws_instance.shard2.public_ip }
output "shard3_public_ip"   { value = aws_instance.shard3.public_ip }
