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

# ── AMI: Ubuntu 24.04 LTS (igual que Lab 7 Circuit Breaker) ──
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

# ── Security Group ────────────────────────────────────────────
resource "aws_security_group" "bite_sg" {
  name        = "${var.project_prefix}-sg"
  description = "BITE Sprint 3 - Puertos para experimentos ASR Latencia y Escalabilidad"

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Nginx / Frontend + API Backend (ASR Latencia — JMeter PORT 80)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Extractor directo (ASR Escalabilidad — JMeter PORT 8001)
  ingress {
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
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

# ── EC2 Instance ──────────────────────────────────────────────
resource "aws_instance" "bite_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.bite_sg.id]

  # Script de arranque: instala Docker y dependencias del sistema
  user_data = file("${path.module}/user_data.sh")

  root_block_device {
    volume_size = 20  # GB — suficiente para Docker images + PostgreSQL data
    volume_type = "gp3"
  }

  tags = {
    Name    = "${var.project_prefix}-server"
    Project = var.project_prefix
    ASR     = "Latencia-Escalabilidad"
  }
}
