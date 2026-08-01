## Production Readiness

Etat au 1 aout 2026.

### Valide dans ce repo

- Build frontend de production OK: `npm.cmd run build`
- Type-check frontend OK: `npm.cmd run type-check`
- Suite backend `unit` OK: `536 passed`
- Tests integration critiques OK:
  - `auth`, `users`, `documents`
  - mode entreprise unique et mode paiement manuel
- Garde-fous de configuration production actifs:
  - refus de `ALLOWED_ORIGINS=*`
  - refus de `TRUSTED_HOSTS=*`
  - refus de `FRONTEND_URL` non HTTPS
  - refus de secrets / emails placeholder en production
  - echec du seed admin en production = demarrage bloque
  - inscriptions et creation de nouveaux utilisateurs desactivees
  - application verrouillee pour une seule entreprise: `JMJ Synergie`
  - profil emetteur force en mode `Entreprise`
  - nom de l'entreprise verrouille sur `JMJ Synergie`
  - deploiement Render prepare pour backend + frontend + Postgres + Key Value

### A renseigner avant go-live

Dans l'environnement de production, remplacer toutes les valeurs de demonstration:

- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `ALLOWED_ORIGINS`
- `TRUSTED_HOSTS`
- `FRONTEND_URL`
- `COMPANY_*`
- `CLOUDINARY_*`
- `SENTRY_DSN`
- `METRICS_TOKEN`
- `KEEPALIVE_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

### Prerequis metier definitifs

- Une seule entreprise utilise l'application: `JMJ Synergie`
- Un seul compte principal de connexion
- Aucun paiement n'est initie dans l'application
- Les paiements saisis sont des enregistrements manuels
- Les documents doivent embarquer le vrai logo, le vrai cachet et la vraie signature de JMJ Synergie
- La devise de reference recommandee pour le Togo est `XOF`

### Verifications go-live

1. Creer les services Render via `render.yaml`
2. Renseigner toutes les variables `sync: false`
3. Verifier `/health` cote backend et `/api/health` cote frontend
4. Tester connexion admin avec l'identifiant unique JMJ Synergie
5. Tester creation client
6. Tester creation devis puis conversion / generation documentaire
7. Tester creation commande
8. Tester generation pro forma, facture, bon de livraison
9. Tester l'apercu inline des documents sans telechargement obligatoire
10. Tester enregistrement paiement manuel + recu
11. Importer le vrai logo, le vrai cachet et la vraie signature dans `Parametres > Visuels et signature`
12. Reouvrir une facture et verifier le rendu final dans l'apercu et dans le PDF telecharge
13. Valider deconnexion / reconnexion
14. Sauvegarder la base avant ouverture a l'exploitation

### Decision

Le code et les tests sont a un niveau compatible production pour un usage
mono-entreprise, mono-compte JMJ Synergie.
Le passage en production reste conditionne au remplissage correct des secrets,
au deploiement Render reel et a l'import des assets officiels JMJ Synergie.
