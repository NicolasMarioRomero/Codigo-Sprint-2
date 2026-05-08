#!/bin/bash
# install_terraform.sh — Instala Terraform en AWS CloudShell
# Igual que el patron del Laboratorio 7 - Circuit Breaker
#
# Uso (desde AWS CloudShell):
#   git clone <tu-repo>
#   cd <tu-repo>
#   sh ./install_terraform.sh

set -e

TERRAFORM_VERSION="1.13.3"

echo "=== Instalando Terraform ${TERRAFORM_VERSION} ==="

# Descargar tfenv (gestor de versiones de Terraform)
git clone --depth=1 https://github.com/tfutils/tfenv.git ~/.tfenv 2>/dev/null \
    || (cd ~/.tfenv && git pull)

# Agregar al PATH de la sesion actual
export PATH="$HOME/.tfenv/bin:$PATH"

# Instalar la version de Terraform
tfenv install "${TERRAFORM_VERSION}"
tfenv use "${TERRAFORM_VERSION}"

echo ""
echo "=== Terraform instalado correctamente ==="
terraform --version
echo ""
echo "Ahora puedes ejecutar:"
echo "  ./deploy.sh ~/.ssh/labsuser.pem"
echo ""
echo "O manualmente:"
echo "  cd terraform"
echo "  terraform init"
echo "  terraform plan"
echo "  terraform apply"
