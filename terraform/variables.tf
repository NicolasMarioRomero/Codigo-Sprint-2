variable "aws_region" {
  description = "Region de AWS"
  type        = string
  default     = "us-east-1"
}

variable "app_instance_type" {
  description = "EC2 principal (app + configsvr + mongos). t3.large recomendado para JMeter con 5000 usuarios."
  type        = string
  default     = "t3.large"   # 2 vCPU, 8 GB RAM
}

variable "shard_instance_type" {
  description = "EC2 para cada shard MongoDB (3 nodos por instancia via Docker)."
  type        = string
  default     = "t3.medium"  # 2 vCPU, 4 GB RAM
}

variable "key_name" {
  description = "Nombre del Key Pair en AWS. En AWS Academy usar 'vockey'."
  type        = string
  default     = "vockey"
}

variable "private_key_path" {
  description = "Ruta local al .pem del Key Pair (para SSH en deploy.sh)."
  type        = string
  default     = "~/.ssh/labsuser.pem"
}

variable "project_prefix" {
  description = "Prefijo para nombrar recursos AWS."
  type        = string
  default     = "bite-sprint3"
}
