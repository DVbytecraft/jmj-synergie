# Deploiement Render - JMJ Synergie

Ce projet est prepare pour un deploiement mono-entreprise, mono-compte:

- entreprise unique: `JMJ Synergie`
- compte principal unique
- backend FastAPI
- frontend Next.js
- PostgreSQL Render
- Key Value Render

## Services attendus

Le blueprint `render.yaml` cree:

- `jmj-db`
- `jmj-cache`
- `jmj-backend`
- `jmj-frontend`

## Variables a renseigner manuellement

### Backend

- `ALLOWED_ORIGINS`
- `TRUSTED_HOSTS`
- `FRONTEND_URL`
- `COMPANY_PHONE`
- `COMPANY_EMAIL`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `SENTRY_DSN` si utilise
- `METRICS_TOKEN` si utilise

### Frontend

- `BACKEND_URL`
  - optionnel si le reseau prive `BACKEND_HOSTPORT` suffit
  - utile comme secours explicite
- `RENDER_BACKEND_URL`
  - URL publique du backend, pour la CSP
- `KEEPALIVE_SECRET`

## Valeurs metier recommandees

- `COMPANY_NAME=JMJ Synergie`
- `COMPANY_ADDRESS=Lome, Togo`
- `COMPANY_CITY=Lome`
- `COMPANY_COUNTRY=Togo`
- `COMPANY_TAX_ID=1001701669`

## Sequence de mise en ligne

1. Importer le repo dans Render Blueprints.
2. Verifier que les 4 services proposes correspondent bien au blueprint.
3. Renseigner toutes les variables `sync: false`.
4. Lancer le deploiement.
5. Ouvrir le frontend et tester la connexion avec le compte admin unique.
6. Aller dans `Parametres > Visuels et signature`.
7. Importer:
   - le logo officiel
   - le cachet officiel
   - la signature officielle
8. Generer une facture de test.
9. Verifier:
   - apercu inline
   - PDF telecharge
   - presence du cachet et de la signature
   - identite JMJ Synergie

## Validation finale

Avant ouverture aux operations, verifier au minimum:

- connexion / deconnexion
- creation client
- creation devis
- creation commande
- generation facture
- apercu document
- telechargement PDF
- paiement manuel
- recu de paiement

## Important

Le deploiement peut etre considere comme pret techniquement, mais il n'est pas
complet tant que les assets visuels officiels de JMJ Synergie ne sont pas
importes dans l'application apres connexion.
