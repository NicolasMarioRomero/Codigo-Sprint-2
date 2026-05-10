output "public_ip" {
  description = "IP publica de la instancia EC2"
  value       = aws_instance.bite_server.public_ip
}

output "public_dns" {
  description = "DNS publico de la instancia EC2"
  value       = aws_instance.bite_server.public_dns
}

output "instance_id" {
  description = "ID de la instancia EC2"
  value       = aws_instance.bite_server.id
}

output "ssh_command" {
  description = "Comando SSH para conectarse a la instancia"
  value       = "ssh -i ${var.private_key_path} ubuntu@${aws_instance.bite_server.public_ip}"
}

output "app_url" {
  description = "URL del frontend y API"
  value       = "http://${aws_instance.bite_server.public_ip}"
}

output "extractor_url" {
  description = "URL directa del Extractor (para JMeter ASR Escalabilidad)"
  value       = "http://${aws_instance.bite_server.public_ip}:8001"
}

output "jmeter_latencia_host" {
  description = "Valor del HOST para el JMeter de Latencia"
  value       = aws_instance.bite_server.public_ip
}

output "jmeter_escalabilidad_host" {
  description = "Valor del HOST para el JMeter de Escalabilidad"
  value       = aws_instance.bite_server.public_ip
}
