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

# ── AMI: Ubuntu 24.04 LTS ─────────────────────────────────────
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Security Group ─────────────────────────────────────────────
resource "aws_security_group" "bite_sg" {
  name        = "${var.project_prefix}-sg"
  description = "BITE Sprint 3 - ASR Latencia, Escalabilidad, Seguridad, Disponibilidad"

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # nginx — JMeter Latencia (puerto 80)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Extractor directo — JMeter Escalabilidad (puerto 8001)
  ingress {
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # MongoDB cluster — puertos shard + configsvr + mongos
  # Solo accesible entre instancias del mismo Security Group
  ingress {
    from_port       = 27017
    to_port         = 27021
    protocol        = "tcp"
    self            = true   # solo entre instancias de este mismo SG
  }

  # Todo el trafico saliente
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_prefix}-sg"
    Project = var.project_prefix
  }
}

# ── EC2 Principal — App + ConfigSvr + Mongos ──────────────────
resource "aws_instance" "bite_app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.app_instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.bite_sg.id]
  user_data              = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  tags = {
    Name    = "${var.project_prefix}-app"
    Project = var.project_prefix
    Role    = "app"
  }
}

# ── EC2 Shards MongoDB (3 instancias) ─────────────────────────
resource "aws_instance" "bite_shard" {
  count                  = 3
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.shard_instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.bite_sg.id]
  user_data              = file("${path.module}/user_data_shard.sh")

  root_block_device {
    volume_size = 15
    volume_type = "gp3"
  }

  tags = {
    Name     = "${var.project_prefix}-shard${count.index + 1}"
    Project  = var.project_prefix
    Role     = "mongodb-shard"
    ShardNum = tostring(count.index + 1)
  }
}
