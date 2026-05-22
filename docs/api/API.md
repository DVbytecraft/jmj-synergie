# Biloz — Référence API v1

Base URL : `https://yourdomain.com/api/v1`  
Dev URL  : `http://localhost:8001/api/v1`

Swagger interactif disponible à `/api/docs`.

---

## Authentification

Toutes les routes protégées nécessitent le header :

```
Authorization: Bearer <access_token>
```

Le token expire après **30 minutes**. Utiliser `/auth/refresh` pour le renouveler silencieusement.

---

## Auth — `/auth`

### `POST /auth/login`
Connexion. Corps en `application/x-www-form-urlencoded`.

**Body**
```
username=email@exemple.com&password=motdepasse
```

**Réponse 200**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Erreurs**
- `401` — Identifiants incorrects
- `403 EMAIL_NOT_VERIFIED` — Email non vérifié
- `403 ACCOUNT_SUSPENDED` — Compte suspendu

---

### `POST /auth/register-organization`
Crée une nouvelle organisation avec son premier compte admin.

**Body JSON**
```json
{
  "org_name": "JMJ Synergie",
  "org_email": "contact@jmj.com",
  "org_phone": "+237 6XX XXX XXX",
  "org_country": "Cameroun",
  "org_city": "Yaoundé",
  "admin_full_name": "Jean Dupont",
  "admin_email": "jean@jmj.com",
  "admin_password": "motdepasse8chars"
}
```

**Réponse 201** — Objet utilisateur + email de vérification envoyé.

---

### `POST /auth/verify-email`
Vérifie l'email avec le code reçu par mail.

```json
{ "email": "jean@jmj.com", "code": "123456" }
```

**Réponse 200** — Tokens JWT (connexion automatique après vérification).

---

### `POST /auth/resend-verification`
Renvoie le code de vérification.

```json
{ "email": "jean@jmj.com" }
```

---

### `POST /auth/forgot-password`
Envoie un lien de réinitialisation par email.

```json
{ "email": "jean@jmj.com" }
```

---

### `POST /auth/reset-password`
Réinitialise le mot de passe avec le token reçu par email.

```json
{
  "token": "...",
  "new_password": "nouveauMotdepasse"
}
```

---

### `POST /auth/refresh`
Renouvelle l'access token.

```json
{ "refresh_token": "eyJ..." }
```

**Réponse 200** — Nouveaux tokens JWT.

---

## Utilisateurs — `/users`

### `GET /users/me`
Profil de l'utilisateur connecté.

**Réponse 200**
```json
{
  "id": "uuid",
  "email": "jean@jmj.com",
  "full_name": "Jean Dupont",
  "role": "admin",
  "status": "active",
  "organization_id": "uuid"
}
```

---

### `GET /users/me/profile`
Profil étendu : signature, cachet, logo pour les PDFs.

---

### `PUT /users/me/profile`
Met à jour les informations du profil (nom, fonction, téléphone, adresse…).

---

### `PUT /users/me/signature-text`
Met à jour le texte de signature apparaissant sur les documents.

```json
{ "signature_text": "Jean Dupont — Directeur Commercial" }
```

---

### `POST /users/me/profile/assets/{asset_type}`
Upload d'un asset (logo, cachet, signature image).

`asset_type` : `logo` | `stamp` | `signature`

**Corps** : `multipart/form-data` avec champ `file`.

---

### `GET /users/me/profile/assets/{asset_type}`
Récupère l'URL ou le contenu d'un asset.

---

### `GET /users`
Liste les utilisateurs de l'organisation.  
**Rôles** : admin+

---

### `POST /users`
Crée un utilisateur dans l'organisation.  
**Rôles** : admin+

```json
{
  "email": "employe@jmj.com",
  "full_name": "Marie Leclerc",
  "role": "operator",
  "password": "motdepasse8"
}
```

---

### `DELETE /users/{user_id}`
Soft-delete d'un utilisateur.  
**Rôles** : admin+

---

## Organisation — `/organizations`

### `GET /organizations/me`
Informations de l'organisation courante.

**Réponse 200**
```json
{
  "id": "uuid",
  "name": "JMJ Synergie",
  "email": "contact@jmj.com",
  "phone": "+237 6XX XXX XXX",
  "city": "Yaoundé",
  "country": "Cameroun",
  "tax_id": "M123456",
  "rccm": "RC/YAO/2020/B/12345",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### `PUT /organizations/me`
Met à jour les informations de l'organisation.  
**Rôles** : admin+

---

### `POST /organizations/me/logo`
Upload du logo de l'organisation.  
**Corps** : `multipart/form-data`, champ `file`.

---

## Clients — `/clients`

### `POST /clients`
Crée un client.

```json
{
  "full_name": "Société ABC",
  "client_type": "company",
  "email": "abc@exemple.com",
  "phone": "+237 6XX XXX XXX",
  "address": "Rue de la Paix, Douala",
  "city": "Douala",
  "country": "Cameroun",
  "tax_id": "M654321"
}
```

`client_type` : `individual` | `company`

---

### `GET /clients`
Liste les clients (avec pagination et recherche).

**Query params**
| Paramètre | Type | Description |
|---|---|---|
| `search` | string | Recherche par nom / email / téléphone |
| `skip` | int | Offset (défaut 0) |
| `limit` | int | Taille de page (défaut 20, max 100) |

---

### `GET /clients/{client_id}`
Détail d'un client.

---

### `PATCH /clients/{client_id}`
Mise à jour partielle d'un client.

---

### `DELETE /clients/{client_id}`
Soft-delete d'un client.

---

## Commandes — `/orders`

### Statuts de commande

```
draft → confirmed → in_progress → delivered
                 ↘ cancelled
```

### `POST /orders`
Crée une commande.

```json
{
  "client_id": "uuid",
  "title": "Commande matériel bureau",
  "notes": "Livraison urgente",
  "items": [
    {
      "product_id": "uuid",
      "quantity": 2,
      "unit_price_cents": 1500000
    }
  ]
}
```

**Réponse 201** — Commande complète avec totaux calculés.

---

### `GET /orders`
Liste les commandes.

**Query params** : `skip`, `limit`, `status`, `client_id`, `search`

---

### `GET /orders/{order_id}`
Détail d'une commande.

---

### `PATCH /orders/{order_id}`
Mise à jour d'une commande (draft seulement).

---

### `DELETE /orders/{order_id}`
Soft-delete (draft seulement).

---

### `POST /orders/{order_id}/confirm`
Confirme une commande (draft → confirmed).  
**Rôles** : manager+

---

### `POST /orders/{order_id}/cancel`
Annule une commande.  
**Rôles** : manager+

---

### `POST /orders/{order_id}/deliveries`
Marque comme livrée (in_progress → delivered).  
**Rôles** : manager+

---

### `POST /orders/{order_id}/items`
Ajoute une ligne à une commande (draft seulement).

---

### `DELETE /orders/{order_id}/items/{item_id}`
Supprime une ligne de commande.

---

## Produits — `/products`

### `POST /products`
Crée un produit.  
**Rôles** : manager+

```json
{
  "name": "Ramette A4",
  "description": "500 feuilles 80g",
  "unit_price_cents": 350000,
  "unit": "ramette",
  "sku": "PAP-A4-80G",
  "stock_quantity": 100
}
```

---

### `GET /products`
Liste les produits. **Query params** : `search`, `skip`, `limit`

---

### `GET /products/{product_id}`
Détail d'un produit.

---

### `PATCH /products/{product_id}`
Mise à jour partielle.  
**Rôles** : manager+

---

### `DELETE /products/{product_id}`
Soft-delete.  
**Rôles** : admin+

---

### `POST /products/{product_id}/stock/add`
Ajoute du stock.

```json
{ "quantity": 50 }
```

---

### `POST /products/{product_id}/stock/remove`
Retire du stock (vérifie la disponibilité).

---

## Paiements — `/payments`

Les montants sont toujours en **centimes** (XAF × 100).

### `POST /payments`
Enregistre un paiement.

```json
{
  "order_id": "uuid",
  "amount_cents": 5000000,
  "payment_method": "mobile_money",
  "reference": "REF-2024-001",
  "notes": "Paiement partiel"
}
```

`payment_method` : `cash` | `bank_transfer` | `mobile_money` | `check` | `other`

---

### `GET /payments`
Liste les paiements.

**Query params** : `order_id`, `skip`, `limit`, `date_from`, `date_to`

---

### `GET /payments/{payment_id}`
Détail d'un paiement.

---

## Remboursements — `/refunds`

### `POST /refunds`
Crée une demande de remboursement.

```json
{
  "payment_id": "uuid",
  "amount_cents": 2500000,
  "reason": "Produit non conforme"
}
```

---

### `GET /refunds`
Liste les remboursements.

---

### `GET /refunds/{refund_id}`
Détail d'un remboursement.

---

### `POST /refunds/{refund_id}/approve`
Approuve un remboursement.  
**Rôles** : admin+

---

### `POST /refunds/{refund_id}/reject`
Rejette un remboursement.  
**Rôles** : admin+

---

## Documents — `/documents`

### Types de documents

| Type | Description |
|---|---|
| `purchase_order` | Bon de commande |
| `pro_forma` | Facture pro forma |
| `delivery_note` | Bon de livraison |
| `invoice` | Facture définitive |
| `payment_receipt` | Reçu de paiement |
| `scanned` | Facture fournisseur scannée (OCR) |

---

### `GET /documents`
Liste les documents de l'organisation.

**Query params** : `order_id`, `document_type`, `skip`, `limit`

---

### `POST /documents/purchase-order/{order_id}`
Génère un bon de commande PDF.

---

### `POST /documents/pro-forma/{order_id}`
Génère une facture pro forma PDF.

---

### `POST /documents/delivery-note/{order_id}`
Génère un bon de livraison PDF.

---

### `POST /documents/invoice/{order_id}`
Génère une facture définitive PDF.

---

### `POST /documents/payment-receipt/{order_id}/{payment_id}`
Génère un reçu de paiement PDF.

---

### `POST /documents/{document_id}/sign`
Appose une signature et un cachet sur un document PDF.

```json
{
  "signer_name": "Jean Dupont",
  "signer_title": "Directeur Commercial"
}
```

---

### `POST /documents/{document_id}/send-email`
Envoie le document par email.

```json
{
  "to_email": "client@exemple.com",
  "subject": "Votre facture n°INV-2024-001",
  "message": "Veuillez trouver ci-joint votre facture."
}
```

---

### `POST /documents/scan-invoice`
**OCR local — aucune donnée envoyée en ligne.**

Analyse une image de facture fournisseur par Tesseract + OpenCV.

**Corps** : `multipart/form-data`, champ `file` (JPEG, PNG, PDF acceptés).

**Réponse 201**
```json
{
  "id": "uuid",
  "document_type": "scanned",
  "extracted_data": {
    "vendor_name": "Fournisseur XYZ",
    "invoice_number": "FAC-2024-0042",
    "invoice_date": "2024-03-15",
    "due_date": "2024-04-15",
    "subtotal": 150000.0,
    "tax_rate": 19.25,
    "tax_amount": 28875.0,
    "total": 178875.0,
    "currency": "XAF",
    "items": [
      {
        "description": "Papier A4",
        "quantity": 10,
        "unit_price": 15000.0,
        "total": 150000.0
      }
    ],
    "confidence": 0.87,
    "needs_review": false
  },
  "file_url": "https://..."
}
```

`needs_review: true` indique une incohérence mathématique détectée (Σ lignes ≠ HT ou HT + TVA ≠ TTC).

---

### `GET /documents/{document_id}/download`
Télécharge le fichier PDF.

---

### `GET /documents/orders/{order_id}`
Liste les documents d'une commande spécifique.

---

## Panneau Admin — `/admin`

> Accès exclusif : rôle `super_admin`

### `GET /admin/stats`
KPI globaux toutes organisations.

**Réponse 200**
```json
{
  "total_users": 42,
  "total_organizations": 8,
  "users_online_today": 12,
  "orgs_online_today": 5,
  "new_users_this_week": 3,
  "new_orgs_this_month": 1
}
```

---

### `GET /admin/organizations`
Toutes les organisations avec statistiques.

**Réponse 200** — Tableau d'objets :
```json
[
  {
    "id": "uuid",
    "name": "JMJ Synergie",
    "email": "contact@jmj.com",
    "phone": "+237 6XX XXX XXX",
    "city": "Yaoundé",
    "country": "Cameroun",
    "tax_id": null,
    "rccm": null,
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "user_count": 5,
    "active_user_count": 2
  }
]
```

`active_user_count` = utilisateurs connectés dans les dernières 24h.

---

### `POST /admin/organizations`
Crée une organisation avec son premier compte admin.

```json
{
  "org_name": "Nouvelle Société",
  "org_email": "contact@nouvelle.com",
  "org_phone": "+237 6XX XXX XXX",
  "org_country": "Cameroun",
  "org_city": "Douala",
  "admin_full_name": "Admin Société",
  "admin_email": "admin@nouvelle.com",
  "admin_password": "motdepasse8"
}
```

**Réponse 201** — Organisation créée + compte admin avec `is_email_verified: true`.

---

### `DELETE /admin/organizations/{org_id}`
Soft-delete de l'organisation et de tous ses utilisateurs.  
**Réponse** : 204 No Content

---

### `GET /admin/users`
Tous les utilisateurs toutes organisations confondues.

**Réponse 200** — Tableau avec `organization_name` joint.

---

### `PUT /admin/users/{user_id}/status`
Suspend ou réactive un compte.

```json
{ "suspend": true }
```

**Réponse 200**
```json
{ "id": "uuid", "status": "suspended" }
```

---

### `DELETE /admin/users/{user_id}`
Soft-delete définitif d'un utilisateur.  
**Réponse** : 204 No Content

---

## Codes d'erreur communs

| Code | Signification |
|---|---|
| `400` | Requête invalide (validation Pydantic) |
| `401` | Token absent ou expiré |
| `403` | Permission insuffisante (rôle) |
| `404` | Ressource introuvable |
| `409` | Conflit (email déjà utilisé, etc.) |
| `422` | Erreur de validation du corps JSON |
| `429` | Rate limit dépassé |
| `500` | Erreur interne serveur |

Le champ `detail` de la réponse d'erreur contient le message en français.

---

## Pagination

Toutes les listes supportent :

| Paramètre | Défaut | Max |
|---|---|---|
| `skip` | 0 | — |
| `limit` | 20 | 100 |

---

## Montants

Tous les montants en base de données sont en **centimes entiers** (`BIGINT`).  
L'API retourne les montants en **unités monétaires** (XAF) via les DTOs.

Exemple : 150 000 XAF stockés comme `15000000` centimes, retournés comme `150000.0`.
