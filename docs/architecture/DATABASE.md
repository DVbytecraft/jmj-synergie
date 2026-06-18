# JMJ Synergie — Documentation Base de Données PostgreSQL

## Schéma global

```
public schema
├── users                    Utilisateurs & authentification
├── user_sessions            Sessions / refresh tokens
├── clients                  Clients (particulier ou entreprise)
├── client_contacts          Contacts supplémentaires par client
├── orders                   Commandes
├── order_items              Lignes de commande
├── order_status_history     Historique des transitions de statut
├── invoices                 Factures définitives
├── invoice_items            Lignes de facture
├── pro_formas               Factures pro forma / devis
├── pro_forma_items          Lignes pro forma
├── payment_transactions     Paiements & remboursements (immutables)
├── refunds                  Demandes de remboursement (workflow)
├── documents                Fichiers (PDF signés, scans OCR...)
├── document_access_log      Log d'accès aux documents (partitionné)
├── notifications            Notifications in-app / email / SMS
└── app_settings             Configuration applicative

audit schema
└── audit_logs               Journal d'audit complet (partitionné par mois)

reporting schema
├── v_orders                 Vue commandes enrichies
├── v_client_balances        Vue soldes clients
├── v_invoices               Vue factures avec statut paiement
├── v_transactions           Vue transactions financières
├── v_refunds                Vue remboursements
├── v_dashboard_kpi          KPI mensuels
└── mv_monthly_summary       Vue matérialisée résumé mensuel (refresh périodique)
```

## Règles critiques

### 1. Montants financiers
- Tous en **centimes entiers** (`BIGINT`) — jamais de `FLOAT` ou `DECIMAL` pour les calculs
- Exemple : 15 000 XAF = `1500000` centimes
- `balance_due_cents` est une **colonne générée** (`GENERATED ALWAYS AS ... STORED`)

### 2. Immutabilité des transactions
- Le trigger `trg_transactions_immutable` bloque toute modification d'une transaction `completed` ou `reversed`
- Pour corriger : créer une transaction de type `adjustment`

### 3. Soft Delete
- Aucune donnée n'est jamais supprimée physiquement
- Champs : `is_deleted BOOLEAN`, `deleted_at TIMESTAMPTZ`, `deleted_by UUID`
- Tous les index actifs utilisent `WHERE is_deleted = FALSE`

### 4. Audit automatique
- Trigger `audit_trigger_func()` sur toutes les tables critiques
- Masque automatiquement : `hashed_password`, `mfa_secret`
- Stocke : valeurs avant/après, liste des champs modifiés

### 5. Row Level Security
- Activé sur 7 tables critiques
- L'application définit `SET LOCAL app.current_user_role` et `app.current_user_id` par session
- Les operators ne voient que leurs propres commandes

## Index stratégiques

| Table         | Index clé                          | Type   | Usage |
|---------------|------------------------------------|--------|-------|
| clients       | full_name gin_trgm_ops             | GIN    | Recherche texte (ILIKE) |
| orders        | (client_id, status, created_at)    | B-tree | Liste commandes d'un client |
| orders        | (payment_status, due_date)         | B-tree | Relances impayées |
| orders        | created_at BRIN                    | BRIN   | Reporting par période |
| payment_trans | (order_id, transaction_date)       | B-tree | Historique paiements |
| audit_logs    | Partitionné par mois               | —      | Gestion du volume |

## Partitionnement

| Table                    | Stratégie        | Raison |
|--------------------------|------------------|--------|
| `audit.audit_logs`       | RANGE par mois   | Volume élevé, TTL par mois |
| `document_access_log`    | RANGE par trimestre | Volume élevé |

## Fonctions métier

| Fonction                          | Description |
|-----------------------------------|-------------|
| `generate_sequence_number()`      | Numérotation thread-safe (CMD-YYYYMM-NNNN) |
| `recalculate_order_totals()`      | Recalcul automatique après modification d'une ligne |
| `update_order_payment_status()`   | Mise à jour du statut paiement après transaction |
| `lock_account_on_failed_login()`  | Verrouillage après 5 échecs (anti brute-force) |
| `get_client_balance()`            | Solde total dû par un client |
| `verify_financial_integrity()`    | Vérification de cohérence comptable |
| `soft_delete_order()`             | Suppression logique en cascade |

## Commandes utiles

```sql
-- Vérifier l'intégrité financière
SELECT * FROM verify_financial_integrity();

-- Solde d'un client
SELECT * FROM get_client_balance('uuid-du-client');

-- Refresh du tableau de bord mensuel
REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.mv_monthly_summary;

-- Commandes avec retard de paiement
SELECT order_number, client_name, balance_due, days_overdue
FROM reporting.v_orders
WHERE days_overdue > 0
ORDER BY days_overdue DESC;

-- Transactions du jour
SELECT * FROM reporting.v_transactions
WHERE transaction_date >= CURRENT_DATE;
```
