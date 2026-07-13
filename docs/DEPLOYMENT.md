# JMJ Synergie — Guide de Déploiement Production

## Prérequis serveur

- Ubuntu 22.04 LTS (ou Debian 12)
- Docker Engine ≥ 24 + Docker Compose V2
- 2 vCPU / 4 Go RAM minimum
- 20 Go disque SSD
- Nom de domaine pointant vers le serveur

---

## 1. Préparation du serveur

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Vérifier
docker --version
docker compose version
```

---

## 2. Cloner le projet

```bash
git clone <repo-url> /opt/jmj-synergie
cd /opt/jmj-synergie
```

---

## 3. Certificats SSL

### Option A — Let's Encrypt (recommandé)

```bash
sudo apt install certbot -y
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

Les certificats sont générés dans `/etc/letsencrypt/live/yourdomain.com/`.

Mettre à jour `infrastructure/nginx/nginx.conf` :
```nginx
ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

### Option B — Certificats auto-signés (dev/test uniquement)

```bash
bash scripts/gen-certs.sh
```

---

## 4. Variables d'environnement

```bash
cp .env.example .env
nano .env
```

### Variables obligatoires

| Variable | Description | Exemple |
|---|---|---|
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | Chaîne aléatoire 32 chars |
| `REDIS_PASSWORD` | Mot de passe Redis | Chaîne aléatoire 32 chars |
| `SECRET_KEY` | Clé JWT (HMAC-SHA256) | Chaîne aléatoire **64 chars minimum** |
| `NEXT_PUBLIC_API_URL` | URL publique de l'API | `https://yourdomain.com/api/v1` |
| `NEXTAUTH_URL` | URL publique du frontend | `https://yourdomain.com` |
| `NEXTAUTH_SECRET` | Secret NextAuth | Chaîne aléatoire 32 chars |
| `ALLOWED_ORIGINS` | CORS origines autorisées | `https://yourdomain.com` |

### Génération de clés sécurisées

```bash
# SECRET_KEY (64 chars)
openssl rand -hex 32

# Mots de passe (32 chars)
openssl rand -base64 24
```

### Variables email (choisir une option)

**Option A — Brevo (recommandé, gratuit jusqu'à 300 emails/jour)**

```env
BREVO_API_KEY=xkeysib-...
BREVO_SENDER_EMAIL=noreply@yourdomain.com
BREVO_SENDER_NAME=JMJ Synergie
```

**Option B — SMTP standard**

```env
SMTP_HOST=smtp.yourdomain.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=motdepasse
SMTP_FROM=noreply@yourdomain.com
```

### Variables stockage fichiers

**Option A — Cloudinary (recommandé pour production)**

```env
USE_CLOUDINARY=true
CLOUDINARY_CLOUD_NAME=votre-cloud
CLOUDINARY_API_KEY=123456789
CLOUDINARY_API_SECRET=secret
```

**Option B — Stockage local**

```env
USE_CLOUDINARY=false
```

Les fichiers seront dans `backend/storage/` (monté en volume Docker).

### Variables PDF (en-tête documents)

```env
COMPANY_NAME=JMJ Synergie
COMPANY_ADDRESS=Yaoundé, Cameroun
COMPANY_PHONE=+237 6XX XXX XXX
COMPANY_EMAIL=contact@jmj.com
COMPANY_LOGO_PATH=/app/storage/assets/logo.png
COMPANY_STAMP_PATH=/app/storage/assets/stamp.png
```

---

## 5. Démarrage des services

```bash
# Premier démarrage (construit les images)
docker compose up -d --build

# Vérifier que tous les services sont healthy
docker compose ps
```

Tous les services doivent être en état `healthy` ou `running` :

| Service | Port interne | Rôle |
|---|---|---|
| `nginx` | 80, 443 | Point d'entrée HTTPS |
| `frontend` | 3000 | Next.js |
| `backend` | 8000 | FastAPI |
| `postgres` | 5432 | Base de données |
| `redis` | 6379 | Cache + sessions |

---

## 6. Migrations base de données

```bash
docker compose exec backend alembic upgrade head
```

---

## 7. Créer le premier super admin

```bash
docker compose exec backend python scripts/seed.py
```

Le compte créé a les identifiants suivants — **à changer immédiatement après la première connexion** :
- Email : `admin@jmjsynergie.com`
- Mot de passe : `ChangeMe@2024!`

Si un super admin existe déjà, le script affiche "Super admin already exists, skipping seed." et ne fait rien.

---

## 8. Vérification

```bash
# Santé de l'API
curl https://yourdomain.com/health

# Logs des services
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f backend
```

---

## Mises à jour

```bash
# Récupérer les changements
git pull origin main

# Reconstruire et redémarrer (zéro downtime avec plusieurs replicas)
docker compose up -d --build

# Appliquer les nouvelles migrations
docker compose exec backend alembic upgrade head
```

---

## Sauvegardes

### Sauvegarde manuelle

```bash
bash scripts/backup.sh
```

Crée un dump PostgreSQL compressé dans `./backups/`.

### Sauvegarde automatique (cron)

```bash
# Éditer le crontab
crontab -e

# Sauvegarde quotidienne à 3h00
0 3 * * * /opt/jmj-synergie/scripts/backup.sh >> /var/log/jmj-synergie-backup.log 2>&1
```

### Restauration

```bash
# Lister les sauvegardes disponibles
ls -la ./backups/

# Restaurer
gunzip -c backups/jmj_2024-01-15_03-00.sql.gz | \
  docker compose exec -T postgres \
  psql -U jmj_admin -d jmj
```

### Rétention

Par défaut, les sauvegardes sont conservées **30 jours** (configurable via `BACKUP_RETENTION_DAYS` dans `.env`).

---

## Renouvellement SSL automatique

```bash
# Tester le renouvellement
sudo certbot renew --dry-run

# Ajouter au cron (renouvellement toutes les semaines)
crontab -e
0 2 * * 1 certbot renew --quiet && docker compose exec nginx nginx -s reload
```

---

## Monitoring

### Prometheus + Grafana

Prometheus et Grafana démarrent automatiquement avec `docker compose up -d` (pas de profil séparé).

| Interface | URL |
|---|---|
| Grafana | https://yourdomain.com/grafana/ (via Nginx, sous-chemin `/grafana/`) |
| Prometheus | Interne seulement (pas exposé publiquement) |

Identifiants Grafana configurés via `GRAFANA_USER` et `GRAFANA_PASSWORD` dans `.env`.

### Alertes

Configurer `infrastructure/monitoring/alerts.yml` avec vos canaux (email, Slack…).

---

## Logs applicatifs

Les logs sont en JSON structuré. Exemple avec `jq` :

```bash
# Erreurs des dernières 24h
docker compose logs backend | jq 'select(.level == "ERROR")'

# Requêtes lentes (> 1s)
docker compose logs backend | jq 'select(.duration_ms > 1000)'
```

---

## Checklist avant mise en production

- [ ] `SECRET_KEY` : 64 caractères aléatoires (jamais la valeur d'exemple)
- [ ] `POSTGRES_PASSWORD` : mot de passe fort (jamais `CHANGE_ME`)
- [ ] `REDIS_PASSWORD` : mot de passe fort
- [ ] `ENVIRONMENT=production` dans `.env`
- [ ] `ALLOWED_ORIGINS` : uniquement votre domaine (pas `*`)
- [ ] SSL activé et HSTS configuré dans Nginx
- [ ] Sauvegardes testées et automatisées
- [ ] Migrations appliquées : `alembic upgrade head`
- [ ] Super admin créé et mot de passe changé
- [ ] Email configuré et testé (envoi de vérification)
- [ ] Cloudinary configuré si `USE_CLOUDINARY=true`
- [ ] `DEBUG=false` (comportement par défaut en production)
- [ ] Ports `5432` (PostgreSQL) et `6379` (Redis) non exposés publiquement
- [ ] Firewall : seuls les ports 80 et 443 ouverts en entrée

---

## Dépannage fréquent

### Le backend ne démarre pas

```bash
docker compose logs backend
# Souvent : variable d'env manquante ou mauvais mot de passe PostgreSQL
```

### Erreur de migration Alembic

```bash
# Voir l'état des migrations
docker compose exec backend alembic history
docker compose exec backend alembic current

# En cas de conflit, réinitialiser (ATTENTION : perte de données)
docker compose exec backend alembic downgrade base
docker compose exec backend alembic upgrade head
```

### Le frontend ne peut pas joindre le backend

Vérifier `NEXT_PUBLIC_API_URL` dans `.env` — doit être l'URL publique HTTPS, pas l'URL Docker interne.

### OCR ne fonctionne pas

```bash
# Vérifier que Tesseract est installé dans le conteneur
docker compose exec backend tesseract --version
docker compose exec backend python -c "import cv2; print(cv2.__version__)"
```

Si manquant, reconstruire l'image : `docker compose up --build -d backend`.
