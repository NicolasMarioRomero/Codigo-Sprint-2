# Guía de Despliegue en AWS — BITE Sprint 2
**Repositorio:** https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git  
**Entorno:** AWS Academy (CloudShell + EC2)

---

## Antes de empezar

Necesitas tener activo el **Lab de AWS Academy**. El lab se cierra después de un tiempo, así que asegúrate de que esté corriendo antes de seguir.

---

## Paso 1 — Iniciar el lab y abrir CloudShell

1. Entra a **AWS Academy** → abre tu curso → **Módulos** → **Learner Lab**.
2. Haz clic en **Start Lab** y espera a que el círculo quede en **verde**.
3. Haz clic en **AWS** (el enlace verde) para abrir la consola de AWS.
4. En la consola de AWS, busca **CloudShell** en la barra de búsqueda superior y ábrelo.

> CloudShell es una terminal en el navegador que ya tiene Python, Git y acceso a tus credenciales de AWS.

---

## Paso 2 — Descargar y subir el archivo `labsuser.pem`

El `.pem` es la llave SSH que permite que el script acceda a la instancia EC2 que va a crear.

**2a. Descarga el .pem desde AWS Academy:**
1. En la pantalla del lab, haz clic en **AWS Details**.
2. Haz clic en **Download PEM** (o "SSH Key").
3. El archivo `labsuser.pem` se descarga a tu computador.

**2b. Súbelo a CloudShell:**
1. En la terminal de CloudShell, haz clic en el ícono de **Acciones** (esquina superior derecha, ícono de engranaje o el menú `⋮`).
2. Selecciona **Upload file**.
3. Escoge el `labsuser.pem` que descargaste.
4. El archivo queda en el directorio home (`~/labsuser.pem`).

**2c. Dale los permisos correctos al .pem:**
```bash
chmod 400 ~/labsuser.pem
```
> SSH requiere que el .pem solo sea legible por ti. Si no haces esto, el script falla.

---

## Paso 3 — Clonar el repositorio

```bash
git clone https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git
cd Codigo-Sprint-2
```

---

## Paso 4 — Instalar Terraform

CloudShell no trae Terraform instalado. El repo incluye un script que lo instala:

```bash
sh install_terraform.sh
```

Espera a que termine. Al final debe decir `Terraform vX.X.X` en verde.

Luego agrega Terraform al PATH de la sesión actual:
```bash
export PATH="$HOME/.tfenv/bin:$PATH"
```

Verifica que funciona:
```bash
terraform --version
```

> **Importante:** Esta exportación solo dura la sesión actual de CloudShell. Si cierras y vuelves a abrir CloudShell, debes correr el `export PATH` otra vez (no el install_terraform.sh, solo el export).

---

## Paso 5 — Configurar credenciales de AWS

Terraform necesita las credenciales para crear recursos en tu cuenta.

1. En AWS Academy, haz clic en **AWS Details** → **Show** (junto a "AWS CLI").
2. Verás tres valores: `aws_access_key_id`, `aws_secret_access_key` y `aws_session_token`.
3. Cópialos y pégalos en CloudShell:

```bash
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```

> **Nota:** Estas credenciales expiran cuando el lab se detiene. Si reinicias el lab, debes repetir este paso con los nuevos valores.

---

## Paso 6 — Dar permisos al script y correr el deploy

```bash
chmod +x deploy.sh
./deploy.sh ~/labsuser.pem
```

El script hace todo automáticamente en este orden:

| Paso | Qué hace | Tiempo aprox. |
|------|----------|---------------|
| Terraform init + apply | Crea la instancia EC2 en AWS | ~2 min |
| Espera SSH | Aguarda a que la instancia arranque | ~2 min |
| Espera PostgreSQL | Verifica que la BD esté lista | ~1-2 min |
| Copia el código | Envía los archivos a EC2 por SSH | ~30 seg |
| Instala dependencias | pip install en la instancia | ~3-4 min |
| Configura servicios | Crea los servicios systemd + nginx | ~30 seg |
| Arranca todo | Inicia backend, extractor, celery | ~30 seg |
| Seed de datos | Carga ~60.000 registros en PostgreSQL | ~1-2 min |
| Health checks | Verifica que todo responda | ~10 seg |

**Tiempo total estimado: 10–15 minutos.**

Al terminar verás algo así:

```
══════════════════════════════════════════════════
  ✅ DESPLIEGUE COMPLETADO (sin Docker)
══════════════════════════════════════════════════

  Frontend / API:   http://54.123.45.67
  API Backend:      http://54.123.45.67/api/v1/
  Extractor:        http://54.123.45.67:8001/docs
  Health check:     http://54.123.45.67/health

  ┌─ JMeter — Actualizar HOST en ambos archivos ─────┐
  │  jmeter_latencia.jmx      → HOST = 54.123.45.67  PORT = 80
  │  jmeter_escalabilidad.jmx → HOST = 54.123.45.67  PORT = 8001
  └──────────────────────────────────────────────────┘
```

Guarda esa **IP pública** — la necesitas para JMeter.

---

## Paso 7 — Verificar que todo funciona

Abre estas URLs en el navegador (reemplaza la IP con la tuya):

| URL | Qué deberías ver |
|-----|-----------------|
| `http://TU_IP` | El frontend de BITE |
| `http://TU_IP/health` | `{"status": "ok", "service": "report-service"}` |
| `http://TU_IP/api/v1/dashboard/1` | JSON con datos del dashboard |
| `http://TU_IP:8001/health` | `{"status": "ok", "service": "extractor-agent"}` |
| `http://TU_IP:8001/docs` | Swagger del Extractor |

---

## Paso 8 — Configurar JMeter con la IP

Abre los archivos `.jmx` en JMeter y actualiza el **HTTP Request Defaults** o la variable `HOST`:

- **`jmeter_latencia.jmx`** → `HOST = TU_IP`, `PORT = 80`
- **`jmeter_escalabilidad.jmx`** → `HOST = TU_IP`, `PORT = 8001`

---

## Problemas frecuentes

### ❌ "No se encontró labsuser.pem"
El script no encontró el archivo. Asegúrate de que esté en `~/labsuser.pem`:
```bash
ls ~/labsuser.pem
./deploy.sh ~/labsuser.pem
```

### ❌ "Terraform no encontrado"
El PATH no tiene Terraform. Ejecuta:
```bash
export PATH="$HOME/.tfenv/bin:$PATH"
```

### ❌ "Error: No valid credential sources found"
Las credenciales de AWS no están configuradas o expiraron. Repite el **Paso 5** con los valores actuales de AWS Details.

### ❌ "Error creating security group: InvalidParameterValue: already exists"
Ya existe un security group de un deploy anterior. Destruye la infraestructura anterior primero:
```bash
cd terraform
terraform destroy -auto-approve -var="private_key_path=~/labsuser.pem"
cd ..
./deploy.sh ~/labsuser.pem
```

### ❌ El health check falla al final pero el deploy termina
La instancia puede tardar unos segundos más. Espera 30 segundos y prueba:
```bash
curl http://TU_IP/health
```

### ❌ Necesito ver los logs de un servicio en EC2
```bash
ssh -i ~/labsuser.pem ubuntu@TU_IP 'sudo journalctl -u bite-backend-1 --no-pager -n 50'
ssh -i ~/labsuser.pem ubuntu@TU_IP 'sudo journalctl -u bite-extractor --no-pager -n 50'
```

---

## Destruir la infraestructura al terminar

Cuando acabes las pruebas, elimina los recursos de AWS para no gastar créditos:

```bash
cd terraform
terraform destroy -auto-approve -var="private_key_path=~/labsuser.pem"
```

---

## Resumen rápido (cheat sheet)

```bash
# 1. Subir labsuser.pem a CloudShell (desde el menú Upload)

# 2. En CloudShell:
chmod 400 ~/labsuser.pem
git clone https://github.com/NicolasMarioRomero/Codigo-Sprint-2.git
cd Codigo-Sprint-2
sh install_terraform.sh
export PATH="$HOME/.tfenv/bin:$PATH"

# 3. Pegar credenciales de AWS Details:
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

# 4. Desplegar:
chmod +x deploy.sh
./deploy.sh ~/labsuser.pem

# 5. Al terminar, anotar la IP y usarla en JMeter.
```
