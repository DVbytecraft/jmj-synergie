# JMJ Synergie — Architecture Technique

## Vue d'ensemble

Application de gestion de commandes professionnelle construite avec une **Clean Architecture** stricte.

---

## Stack Technique

| Couche         | Technologie              |
|----------------|--------------------------|
| Backend        | FastAPI 0.115 + Python 3.12 |
| Base de données| PostgreSQL 16            |
| Cache/Session  | Redis 7                  |
| Frontend       | Next.js 15 + React 19    |
| State          | Zustand + React Query    |
| Reverse Proxy  | Nginx 1.25               |
| Conteneurs     | Docker + Docker Compose  |
| Migrations     | Alembic (async)          |
| CI/CD          | GitHub Actions           |

---

## Architecture Backend — Clean Architecture

```
backend/app/
├── api/                   ← Couche Présentation
│   └── v1/
│       ├── endpoints/     ← Contrôleurs HTTP (thin)
│       ├── deps.py        ← Dépendances FastAPI (auth, RBAC)
│       └── router.py      ← Assemblage des routes
│
├── application/           ← Couche Application
│   ├── use_cases/         ← Orchestration des cas d'usage
│   ├── dto/               ← Data Transfer Objects (Pydantic)
│   └── mappers/           ← Conversion entity ↔ DTO
│
├── domain/                ← Couche Domaine (ZERO dépendance externe)
│   ├── entities/          ← Entités métier (dataclasses pures)
│   ├── repositories/      ← Interfaces (ABC) des dépôts
│   └── services/          ← Services domaine
│
├── infrastructure/        ← Couche Infrastructure
│   ├── database/
│   │   └── models.py      ← ORM SQLAlchemy
│   ├── repositories/      ← Implémentations SQLAlchemy des dépôts
│   └── external/
│       ├── pdf/           ← ReportLab + PyHanko
│       ├── ocr/           ← Tesseract + OpenCV
│       └── storage/       ← Gestion fichiers
│
├── core/                  ← Transversal
│   ├── config.py          ← Settings Pydantic
│   ├── database.py        ← Engine async SQLAlchemy
│   ├── security.py        ← JWT + bcrypt
│   └── exceptions.py      ← Exceptions domaine
│
└── middleware/            ← Middleware Starlette
    ├── security_headers.py ← En-têtes OWASP
    ├── logging.py          ← Logs structurés
    └── rate_limiter.py     ← Rate limiting Redis
```

---

## Flux de données

```
HTTP Request
    ↓
Nginx (SSL termination, rate limiting)
    ↓
FastAPI Middleware (security headers, logging, rate limit)
    ↓
API Endpoint (validation Pydantic)
    ↓
Dependency Injection (auth, DB session)
    ↓
Use Case (logique application)
    ↓
Domain Entity (règles métier)
    ↓
Repository Interface
    ↓
Repository Implementation (SQLAlchemy)
    ↓
PostgreSQL
```

---

## Modèle de données

### Entités principales

- **User** — Utilisateurs système (RBAC: super_admin, admin, manager, operator)
- **Client** — Clients (particulier ou entreprise)
- **Order** — Commandes avec états (draft → confirmed → in_progress → delivered)
- **OrderItem** — Lignes de commande
- **PaymentTransaction** — Paiements partiels + remboursements
- **Document** — PDFs générés (pro forma, factures, scans OCR)
- **AuditLog** — Traçabilité complète

### Convention montants
Tous les montants sont stockés en **centimes entiers** (BigInteger) pour éviter les erreurs de virgule flottante.
Exemple: 150 000 XAF = `15000000` centimes.

---

## Sécurité

| Mécanisme             | Implémentation                          |
|-----------------------|-----------------------------------------|
| Authentification      | JWT (access 30min + refresh 7j)         |
| Hachage passwords     | bcrypt (12 rounds)                      |
| Autorisation          | RBAC 4 rôles                            |
| Rate limiting         | Redis sliding window                    |
| En-têtes HTTP         | OWASP (CSP, HSTS, X-Frame-Options...)   |
| Transport             | TLS 1.2/1.3 via Nginx                   |
| Isolation réseau      | Docker networks internes                |
| Soft delete           | Données jamais supprimées physiquement  |
| Audit trail           | Toutes les actions tracées              |

---

## Fonctionnalités PDF

### Pro Forma
- Génération ReportLab avec en-tête société, logo, tableau des articles
- Numérotation automatique, devise configurable

### Signature PDF
- Overlay visuel de la signature (image PNG)
- Cachet/tampon de la société
- Métadonnées de signature (qui, quand)
- Basé sur pypdf merge + reportlab canvas

### Scan Facture (OCR)
- Conversion PDF→image avec pdf2image
- OCR Tesseract multilingue (fr+en)
- Extraction automatique: numéro facture, date, total, TVA, fournisseur
- Score de confiance par extraction

---

## Démarrage rapide

```bash
# 1. Copier et configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs sécurisées

# 2. Démarrer les services
docker-compose up -d

# 3. Migrations base de données
docker-compose exec backend alembic upgrade head

# 4. Créer le premier admin
docker-compose exec backend python scripts/seed.py

# 5. Accéder à l'application
# Frontend: https://yourdomain.com
# API docs (dev): http://localhost:8000/api/docs
```
