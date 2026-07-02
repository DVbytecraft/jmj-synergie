# JMJ Synergie — Architecture Technique

## Vue d'ensemble

Application de gestion commerciale multi-organisation construite avec une **Clean Architecture** stricte.

---

## Stack Technique

| Couche | Technologie |
|---|---|
| Backend | FastAPI 0.115 + Python 3.12 |
| Base de données | PostgreSQL 16 |
| Cache/Session | Redis 7 |
| Frontend | Next.js 15 + React 19 |
| State | Zustand + TanStack Query v5 |
| Reverse Proxy | Nginx 1.25 |
| Conteneurs | Docker + Docker Compose |
| Migrations | Alembic (async) |
| CI/CD | GitHub Actions |

---

## Architecture Backend — Clean Architecture

```
backend/app/
├── api/                   ← Couche Présentation
│   └── v1/
│       ├── endpoints/     ← Contrôleurs HTTP (thin)
│       │   ├── admin.py         Routes super_admin (cross-org)
│       │   ├── auth.py          Authentification + inscription
│       │   ├── clients.py       CRUD clients
│       │   ├── documents.py     Génération PDF + OCR scan
│       │   ├── orders.py        Commandes + workflow statuts
│       │   ├── organizations.py Paramètres organisation courante
│       │   ├── payments.py      Paiements
│       │   ├── permissions.py   Permissions RBAC
│       │   ├── products.py      Catalogue produits
│       │   ├── refunds.py       Remboursements
│       │   └── users.py         Profils utilisateurs + assets
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
│   │   ├── models.py      ← ORM SQLAlchemy (OrganizationModel, UserModel…)
│   │   └── session.py     ← Engine async + session factory
│   ├── repositories/      ← Implémentations SQLAlchemy des dépôts
│   └── external/
│       ├── pdf/           ← Génération PDF (ReportLab + pypdf)
│       ├── ocr/           ← Pipeline OCR (Tesseract + OpenCV)
│       └── storage/       ← Cloudinary ou stockage local
│
├── core/                  ← Transversal
│   ├── config.py          ← Settings Pydantic (variables d'env)
│   ├── security.py        ← JWT + bcrypt
│   └── exceptions.py      ← Exceptions domaine
│
└── middleware/            ← Middleware Starlette
    ├── security_headers.py ← En-têtes OWASP (CSP, HSTS…)
    ├── logging.py          ← Logs structurés JSON
    └── rate_limiter.py     ← Rate limiting Redis sliding window
```

---

## Architecture Frontend — Next.js 15 App Router

```
frontend/src/
├── app/
│   ├── (auth)/            ← Pages publiques
│   │   ├── login/
│   │   ├── register/
│   │   ├── verify-email/
│   │   ├── forgot-password/
│   │   └── reset-password/
│   └── (dashboard)/       ← Pages protégées (AuthGuard)
│       ├── layout.tsx           Sidebar + TopBar + AuthGuard
│       ├── dashboard/           KPI + graphiques
│       ├── clients/             CRUD clients
│       ├── commandes/           Commandes + workflow
│       ├── produits/            Catalogue
│       ├── paiements/           Transactions
│       ├── journal/             Journaux comptables
│       ├── documents/           Documents PDF
│       ├── scan/                Scan OCR factures
│       ├── settings/            Paramètres compte + org
│       └── admin/users/         Panneau super_admin
│
├── components/
│   ├── layout/
│   │   ├── AuthGuard.tsx        Garde + refresh silencieux
│   │   ├── Sidebar.tsx          Navigation (RBAC-aware)
│   │   ├── TopBar.tsx           Barre supérieure
│   │   ├── Providers.tsx        QueryClient + error boundary
│   │   └── sidebar-context.tsx  État ouvert/fermé sidebar mobile
│   └── ui/                      Composants partagés
│
├── lib/
│   ├── api/client.ts            Axios + intercepteurs JWT + refresh
│   └── hooks/                   Hooks TanStack Query par domaine
│
├── store/
│   └── auth.store.ts            Zustand persist (tokens + user)
│
└── middleware.ts                 Next.js middleware RBAC (SSR)
```

---

## Flux de données

```
HTTP Request
    ↓
Nginx (SSL termination, gzip, cache statiques)
    ↓
FastAPI Middleware (security headers, logs, rate limit)
    ↓
Next.js Middleware (vérif cookie access_token, RBAC routes)
    ↓  [dashboard routes seulement]
AuthGuard (refresh silencieux si token expiré)
    ↓
API Endpoint (validation Pydantic)
    ↓
Dependency Injection (CurrentUser, DB session)
    ↓
Use Case (logique application)
    ↓
Domain Entity (règles métier)
    ↓
Repository Interface
    ↓
Repository Implementation (SQLAlchemy async)
    ↓
PostgreSQL
```

---

## Système d'authentification

### Tokens JWT

| Token | Durée | Stockage |
|---|---|---|
| `access_token` | 30 minutes | Zustand (mémoire) + cookie `access_token` |
| `refresh_token` | 7 jours | Zustand (mémoire) + localStorage |

Le cookie `access_token` est en `SameSite=Lax` (non HttpOnly) pour que le middleware Next.js puisse le lire côté serveur sans JS.

### Flux de refresh

1. Requête API → 401
2. Intercepteur Axios détecte le 401
3. Si `refresh_token` présent → appel `POST /auth/refresh`
4. Si succès → nouveaux tokens, rejoue la requête originale
5. Si échec → `clearAuth()` → `useAuthStore.subscribe()` dans `AuthGuard` détecte le changement → `router.replace("/login")`

### RBAC (Rôles)

```python
# deps.py
require_roles("super_admin")           # super_admin uniquement
require_roles("super_admin", "admin")  # admin+
require_roles("super_admin", "admin", "manager")  # manager+
# CurrentUser = tous les rôles authentifiés
```

Le middleware Next.js applique le RBAC au niveau des routes :
- `/admin/*` → `super_admin` uniquement
- `/commandes/new`, `/clients/new`, `/produits/new` → manager+

---

## Pipeline OCR — Tesseract + OpenCV

**100% local — aucune donnée envoyée à un service cloud.**

### Étapes de traitement (`ocr_service.py`)

```
Image / PDF
    ↓
pdf2image (si PDF) → PIL Image
    ↓
OpenCV Preprocessing
  ├── RGB → Niveaux de gris
  ├── Redimensionnement (1500px largeur max)
  ├── CLAHE (amélioration contraste adaptatif)
  ├── Seuillage adaptatif (blockSize=11, C=2)
  ├── Fermeture morphologique (élimination bruit)
  └── Deskew (correction inclinaison via minAreaRect, seuil 0.3°)
    ↓
Tesseract image_to_string (--oem 3 --psm 6, fra+eng)
    ↓
Tesseract image_to_data (mots avec coordonnées x/y/w/h + confiance)
    ↓
Extraction positionnelle des lignes de tableau
  ├── Détection en-tête (mots-clés: Désignation, Qté, Prix, Montant…)
  ├── Identification colonnes par position X
  └── Arrêt aux mots-clés de pied (Total, TVA, HT, TTC…)
    ↓
Extraction regex fallback (si extraction positionnelle insuffisante)
    ↓
Validation mathématique
  ├── Σ(quantité × prix unitaire) ≈ sous-total (tolérance: ±2 XAF)
  └── sous-total + TVA ≈ total → needs_review: bool
    ↓
Format de sortie JSON unifié + confidence score
    ↓
Stockage Cloudinary + enregistrement Document en base
```

---

## Génération PDF

### Documents supportés

| Document | Contenu |
|---|---|
| Bon de commande | En-tête org, tableau articles, totaux, conditions |
| Pro forma | Idem + mention "Pro Forma" |
| Bon de livraison | Articles livrés, signature réception |
| Facture | Numérotation auto, TVA détaillée, mentions légales |
| Reçu de paiement | Référence paiement, mode, montant, solde restant |

### Signature PDF

- Overlay visuel de la signature (image PNG uploadée)
- Cachet/tampon de l'organisation
- Métadonnées : signataire, date, fonction

---

## Modèle de données — Entités principales

| Entité | Description |
|---|---|
| `Organization` | Société cliente (multi-tenant) |
| `User` | Utilisateur (lié à une org, RBAC 4 rôles) |
| `Client` | Client de l'organisation (particulier ou société) |
| `Order` | Commande avec workflow statuts |
| `OrderItem` | Ligne de commande |
| `PaymentTransaction` | Paiement (immutable une fois completed) |
| `Refund` | Demande de remboursement avec workflow |
| `Document` | PDF généré ou scanné (URL Cloudinary) |
| `Product` | Produit du catalogue avec stock |

**Convention montants** : tous en **centimes entiers** (`BIGINT`). Exemple : 150 000 XAF = `15_000_000` centimes.

**Soft delete** : aucune donnée n'est supprimée physiquement. Champs `is_deleted`, `deleted_at`.

---

## Sécurité

| Mécanisme | Implémentation |
|---|---|
| Authentification | JWT (access 30min + refresh 7j) |
| Hachage passwords | bcrypt (12 rounds) |
| Autorisation | RBAC 4 rôles (backend + middleware Next.js) |
| Rate limiting | Redis sliding window (par IP + par user) |
| En-têtes HTTP | OWASP : CSP, HSTS, X-Frame-Options, X-Content-Type |
| Transport | TLS 1.2/1.3 via Nginx |
| Isolation réseau | Docker networks internes (backend/db non exposés) |
| Soft delete | Données jamais supprimées physiquement |
| Sessions Admin | Refresh token révocable via `user_sessions` table |

---

## Multi-organisation (isolation des données)

Chaque ressource (client, commande, paiement, document, produit) est liée à une `organization_id`. Les repositories filtrent systématiquement par l'organisation de l'utilisateur connecté. Un `operator` voit seulement ses propres commandes (Row Level Security PostgreSQL).

Le `super_admin` est le seul rôle cross-organisation — il accède aux endpoints `/admin/*` qui ignorent le filtre d'organisation.
