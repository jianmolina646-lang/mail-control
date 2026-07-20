# Mail Control — TEAM JHELIZ

Dashboard web privado para gestión **masiva** de bandejas de correo (Outlook,
Hotmail, Gmail) vía IMAP, con **radar de suscripciones de streaming** que genera
alertas automáticas de caídas/pagos. Sin logins manuales, sin extracción de
códigos OTP: se enfoca 100% en la estabilidad del visor.

Diseñado para correr en un **VPS chico (1 vCPU / 2 GB RAM)** sin quedarse sin
memoria, y escalar a miles de cuentas.

---

## Stack

| Capa            | Tecnología                                   |
|-----------------|----------------------------------------------|
| Backend         | Python + **FastAPI**                         |
| Tareas async    | **Celery + Redis**                           |
| Base de datos   | **PostgreSQL** (App Passwords **encriptadas** con Fernet) |
| Frontend        | **React + Vite + TailwindCSS** (dark, virtualizado) |
| Despliegue      | **Docker Compose** + Nginx + Certbot         |

---

## Estructura

```
mail-control/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app + creación de admin inicial
│   │   ├── api/routes.py         # Endpoints (auth, cuentas, mensajes, alertas, stats)
│   │   ├── core/
│   │   │   ├── config.py         # Settings (límites de hardware incluidos)
│   │   │   ├── crypto.py         # Encriptación Fernet de las App Passwords
│   │   │   ├── db.py             # SQLAlchemy (pool chico)
│   │   │   └── security.py       # JWT + bcrypt
│   │   ├── models/models.py      # User, MailAccount, Message, Alert
│   │   ├── schemas/schemas.py    # Pydantic
│   │   ├── services/
│   │   │   ├── imap_service.py   # Lectura IMAP (abre/cierra por cuenta)
│   │   │   └── radar.py          # Detección de alertas de streaming
│   │   └── workers/
│   │       ├── celery_app.py     # Celery afinado para 2 GB RAM
│   │       └── tasks.py          # Escaneo en chunks + semáforo IMAP
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                # Login, Inbox (virtualizado), Alerts, Accounts
│   │   ├── components/           # Layout, MessageView
│   │   └── lib/api.js            # Cliente HTTP
│   ├── Dockerfile                # build Vite -> nginx
│   └── nginx.conf
├── deploy/
│   ├── nginx/app.conf            # Proxy público + SSL para ecormecejhelizstore.com
│   └── init-ssl.sh               # Emite el certificado inicial de Certbot
├── docker-compose.yml            # mem_limit en TODOS los servicios
└── .env.example
```

---

## 🚨 Control de recursos (anti Out-of-Memory)

- **Semáforo IMAP global en Redis**: nunca hay más de `IMAP_MAX_CONCURRENCY` (50)
  conexiones IMAP abiertas en todo el sistema, sin importar cuántos workers haya.
- **Chunks chicos**: cada tarea Celery procesa `IMAP_CHUNK_SIZE` (10) cuentas
  **en serie**, abriendo y cerrando cada conexión de inmediato.
- **Celery afinado**: `concurrency=2`, `prefetch=1`, `max-tasks-per-child=50` y
  `max_memory_per_child≈300MB` (recicla el proceso y libera RAM).
- **`mem_limit` en Docker** para Postgres (512m), Redis (160m, `maxmemory 128mb`),
  backend/worker (512m), beat/frontend/proxy (≤128m).
- **Limpieza automática**: se borran correos > 30 días **sin alerta** (cuida disco).

---

## Guía de instalación en Ubuntu (paso a paso)

### 1. Crear 2 GB de memoria Swap (OBLIGATORIO antes de Docker)

```bash
# Verificar que no exista ya swap
sudo swapon --show

# Crear archivo swap de 2 GB
sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Hacerlo persistente al reiniciar
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Afinar el uso de swap (menos agresivo)
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Confirmar
free -h
```

### 2. Instalar Docker + Docker Compose

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER   # cerrá y volvé a abrir sesión después
```

### 3. Clonar y configurar

```bash
git clone https://github.com/jianmolina646-lang/mail-control.git
cd mail-control
cp .env.example .env

# Generar los secretos y pegarlos en .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('CREDENTIALS_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

nano .env   # completar SECRET_KEY, CREDENTIALS_ENCRYPTION_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD
```

> ⚠️ Guardá `CREDENTIALS_ENCRYPTION_KEY` en un lugar seguro. Si la perdés, no se
> pueden desencriptar las App Passwords ya guardadas.

### 4. Apuntar el dominio

En tu DNS, apuntá `ecormecejhelizstore.com` (y `www`) al IP del VPS (registro A).

### 5. Levantar

```bash
# Build + arranque (la primera vez tarda unos minutos)
docker compose build
docker compose up -d db redis backend worker beat frontend

# Ver estado
docker compose ps
```

### 6. SSL (HTTPS con Certbot)

```bash
# Emite el certificado real y deja el proxy con HTTPS
CERTBOT_EMAIL=tucorreo@dominio.com ./deploy/init-ssl.sh

# El contenedor certbot renueva solo cada 12h; para forzar:
docker compose run --rm certbot renew
docker compose exec proxy nginx -s reload
```

Listo: entrá a **https://ecormecejhelizstore.com** y logueate con
`ADMIN_EMAIL` / `ADMIN_PASSWORD`.

---

## Uso

1. **Cuentas** → agregá casillas (email + App Password). La contraseña se guarda
   encriptada. "Probar" valida la conexión IMAP al instante.
2. **Bandeja** → visor global de todos los correos, con búsqueda y scroll
   virtualizado (lista de miles de correos sin trabar el navegador).
3. **Alertas críticas** → correos de streaming (@netflix, @hbomax, @primevideo…)
   con palabras de problema (pago, rechazado, caducada, cancelada…). Marcá como
   resueltas cuando las atiendas.

### App Passwords

- **Gmail**: activá verificación en 2 pasos → creá una "Contraseña de aplicación".
- **Outlook/Hotmail**: puede requerir App Password si tenés 2FA. Host IMAP:
  `outlook.office365.com:993`.

---

## Comandos útiles

```bash
docker compose logs -f worker      # ver el escaneo IMAP
docker compose logs -f backend
docker stats                       # confirmar que la RAM no se dispara
docker compose restart worker
```

---

## Notas de seguridad

- Las App Passwords se cifran con Fernet; en la DB solo hay texto cifrado.
- El panel es privado (login JWT) y `noindex`.
- **No** se extraen códigos OTP/PIN por diseño.
