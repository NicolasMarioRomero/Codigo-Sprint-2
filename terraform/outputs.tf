output "app_public_ip" {
  description = "IP publica del servidor principal (Django + servicios)"
  value       = aws_instance.bite_app.public_ip
}

output "app_public_dns" {
  description = "DNS publico del servidor principal"
  value       = aws_instance.bite_app.public_dns
}

output "app_private_ip" {
  description = "IP privada del servidor principal (usada por los shards para conectar al mongos)"
  value       = aws_instance.bite_app.private_ip
}

output "shard_public_ips" {
  description = "IPs publicas de las 3 EC2 de shards MongoDB"
  value       = aws_instance.bite_shard[*].public_ip
}

output "shard_private_ips" {
  description = "IPs privadas de los shards (comunicacion interna del cluster)"
  value       = aws_instance.bite_shard[*].private_ip
}

output "ssh_app" {
  description = "Comando SSH al servidor principal"
  value       = "ssh -i ${var.private_key_path} ubuntu@${aws_instance.bite_app.public_ip}"
}

output "ssh_shard1" {
  description = "Comando SSH al shard 1"
  value       = "ssh -i ${var.private_key_path} ubuntu@${aws_instance.bite_shard[0].public_ip}"
}

output "ssh_shard2" {
  description = "Comando SSH al shard 2"
  value       = "ssh -i ${var.private_key_path} ubuntu@${aws_instance.bite_shard[1].public_ip}"
}

output "ssh_shard3" {
  description = "Comando SSH al shard 3"
  value       = "ssh -i ${var.private_key_path} ubuntu@${aws_instance.bite_shard[2].public_ip}"
}

output "app_url" {
  description = "URL del frontend y API (JMeter Latencia)"
  value       = "http://${aws_instance.bite_app.public_ip}"
}

output "extractor_url" {
  description = "URL directa del Extractor (JMeter Escalabilidad)"
  value       = "http://${aws_instance.bite_app.public_ip}:8001"
}

output "jmeter_latencia_host" {
  value = aws_instance.bite_app.public_ip
}

output "jmeter_escalabilidad_host" {
  value = aws_instance.bite_app.public_ip
}
