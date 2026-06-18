# Biloz — Gestion Commerciale

Plateforme de gestion commerciale multi-organisation : clients, commandes, paiements, documents PDF et scan OCR de factures.

---

## Stack

| Couche | Technologie |
|---|---|
| Backend | FastAPI 0.115 + Python 3.12 |
| Base de données | PostgreSQL 16 |
| Cache | Redis 7 |
| Frontend | Next.js 15 + React 19 + TailwindCSS |
| State | Zustand + TanStack Query |
| OCR | Tesseract 5 + OpenCV 4 (local, sans cloud) |
| Stockage fichiers | Cloudinary (optionnel) ou système local |
| Reverse proxy | Nginx 1.25 |
| Conteneurs | Docker + Docker Compose |
| Migrations | Alembic (async) |

---

## Démarrage rapide (développement)

### Prérequis

- Docker Desktop ≥ 4.x
- Docker Compose V2

### 1. Cloner et configurer

```bash
git clone <repo-url>
cd jmj-synergie
cp .env.example .env
```

Éditer `.env` — les variables minimales pour le dev :

```env
POSTGRES_PASSWORD=devpassword
SECRET_KEY=dev_secret_key_64_chars_minimum_aaaaaaaaaaaaaaaaaaa
```

> `NEXT_PUBLIC_API_URL` n'a pas besoin d'être défini en dev : le `docker-compose.dev.yml` le force à `/api/v1` (URL relative) et Next.js proxifie automatiquement vers le backend via ses rewrites.

### 2. Lancer les services

```bash
docker compose -f docker-compose.dev.yml up -d
```

Ports exposés :

| Service | URL |
|---|---|
| Frontend | http://localhost:3001 |
| Backend (API) | http://localhost:8001 |
| API Docs (Swagger) | http://localhost:8001/api/docs |
| API Docs (ReDoc) | http://localhost:8001/api/redoc |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Migrations base de données

```bash
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

### 4. Créer le premier super admin

```bash
docker compose -f docker-compose.dev.yml exec backend python scripts/seed.py
```

Ce script crée un compte `super_admin` avec les identifiants suivants (à changer immédiatement) :
- Email : `admin@jmjsynergie.com`
- Mot de passe : `ChangeMe@2024!`

---

## Structure du projet

```
jmj-synergie/
├── backend/               FastAPI + Clean Architecture
│   ├── app/
│   │   ├── api/v1/        Endpoints REST
│   │   ├── application/   Use cases + DTOs
│   │   ├── domain/        Entités + interfaces repositories
│   │   ├── infrastructure/ SQLAlchemy + OCR + PDF + stockage
│   │   ├── core/          Config + sécurité + exceptions
│   │   └── middleware/    Security headers + rate limiting
│   ├── alembic/           Migrations
│   └── scripts/           Seed + utilitaires
├── frontend/              Next.js 15
│   └── src/
│       ├── app/           Pages (App Router)
│       ├── components/    Composants réutilisables
│       ├── lib/           API client + hooks
│       └── store/         Zustand (auth)
├── infrastructure/
│   ├── nginx/             Configuration Nginx (dev + prod)
│   ├── postgres/          Init SQL + migrations raw
│   └── monitoring/        Prometheus + Grafana
├── docs/
│   ├── architecture/      ARCHITECTURE.md + DATABASE.md
│   └── api/               API.md (référence complète)
└── scripts/               backup.sh + gen-certs.sh
```

---

## Rôles utilisateurs (RBAC)

| Rôle | Accès |
|---|---|
| `super_admin` | Tout, y compris panneau admin multi-org |
| `admin` | Toute l'organisation (users, commandes, produits, paiements) |
| `manager` | Commandes, clients, produits, paiements |
| `operator` | Ses propres commandes uniquement |

---

## Pages frontend

| Route | Description | Rôles |
|---|---|---|
| `/dashboard` | KPI et graphiques | Tous |
| `/clients` | Liste et gestion clients | Tous |
| `/commandes` | Commandes + statuts | Tous |
| `/produits` | Catalogue produits | admin+ |
| `/paiements` | Transactions | Tous |
| `/journal/paiements` | Journal comptable paiements | Tous |
| `/journal/remboursements` | Journal remboursements | Tous |
| `/documents` | Documents PDF générés | Tous |
| `/scan` | Scan OCR de factures fournisseurs | Tous |
| `/settings` | Paramètres compte + organisation | Tous |
| `/admin/users` | Panneau super-admin | super_admin uniquement |

---

## Commandes utiles

```bash
# Logs en temps réel
docker compose -f docker-compose.dev.yml logs -f

# Redémarrer un service
docker compose -f docker-compose.dev.yml restart backend

# Reconstruire après changement de dépendances
docker compose -f docker-compose.dev.yml up --build -d backend

# Lancer les tests backend
docker compose -f docker-compose.dev.yml exec backend pytest

# Shell PostgreSQL
docker compose -f docker-compose.dev.yml exec postgres psql -U biloz_admin -d biloz

# Nouvelle migration Alembic
docker compose -f docker-compose.dev.yml exec backend alembic revision --autogenerate -m "description"
```

---

## Documentation complète

- [Architecture technique](docs/architecture/ARCHITECTURE.md)
- [Schéma base de données](docs/architecture/DATABASE.md)
- [Référence API](docs/api/API.md)
- [Guide de déploiement production](docs/DEPLOYMENT.md)
