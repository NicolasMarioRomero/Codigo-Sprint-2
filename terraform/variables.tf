variable "aws_region" {
  description = "Region de AWS donde se despliega la instancia"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Tipo de instancia EC2. t3.large recomendado para experimento con 5000 usuarios."
  type        = string
  default     = "t3.large"  # 2 vCPU, 8 GB RAM
}

variable "key_name" {
  description = "Nombre del Key Pair en AWS para acceso SSH. En AWS Academy usar 'vockey'."
  type        = string
  default     = "vockey"
}

variable "private_key_path" {
  description = "Ruta local al archivo .pem del Key Pair (para SSH/rsync en deploy.sh)."
  type        = string
  default     = "~/.ssh/labsuser.pem"
}

variable "project_prefix" {
  description = "Prefijo para nombrar los recursos AWS creados por Terraform."
  type        = string
  default     = "bite-sprint3"
}
