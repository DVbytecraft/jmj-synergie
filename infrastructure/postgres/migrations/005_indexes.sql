-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 005 : Indexes stratégiques
--
--  Stratégie :
--  1. Index partiels (WHERE is_deleted = FALSE) — exclut les lignes soft-deleted
--  2. Index composites — pour les filtres fréquents combinés
--  3. Index BRIN — pour les colonnes temporelles (append-only, très compressés)
--  4. Index GIN — pour JSONB et full-text search
--  5. Index GiST — pour les recherches trigram (pg_trgm)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_users_email_active
    ON users (email)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_users_role_status
    ON users (role, status)
    WHERE is_deleted = FALSE;

-- ---------------------------------------------------------------------------
-- USER_SESSIONS
-- ---------------------------------------------------------------------------
CREATE INDEX idx_sessions_user_active
    ON user_sessions (user_id, expires_at)
    WHERE revoked = FALSE;

CREATE INDEX idx_sessions_token_hash
    ON user_sessions (token_hash);

-- Nettoyage automatique des sessions expirées (hint pour pg_partman si utilisé)
CREATE INDEX idx_sessions_expires
    ON user_sessions (expires_at)
    WHERE revoked = FALSE;

-- ---------------------------------------------------------------------------
-- CLIENTS
-- ---------------------------------------------------------------------------
-- Recherche texte sur le nom du client (trigram — supporte ILIKE)
CREATE INDEX idx_clients_fullname_trgm
    ON clients USING GIN (full_name gin_trgm_ops)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_clients_company_trgm
    ON clients USING GIN (company_name gin_trgm_ops)
    WHERE is_deleted = FALSE AND company_name IS NOT NULL;

-- Lookup rapide par code
CREATE UNIQUE INDEX idx_clients_code_active
    ON clients (code)
    WHERE is_deleted = FALSE;

-- Filtre par statut et type
CREATE INDEX idx_clients_status_type
    ON clients (status, client_type)
    WHERE is_deleted = FALSE;

-- Assignation commerciale
CREATE INDEX idx_clients_assigned_to
    ON clients (assigned_to)
    WHERE assigned_to IS NOT NULL AND is_deleted = FALSE;

-- Recherche par pays pour reporting régional
CREATE INDEX idx_clients_country
    ON clients (country)
    WHERE is_deleted = FALSE;

-- Tags (recherche dans un tableau)
CREATE INDEX idx_clients_tags
    ON clients USING GIN (tags)
    WHERE is_deleted = FALSE;

-- ---------------------------------------------------------------------------
-- ORDERS
-- ---------------------------------------------------------------------------
-- Index le plus utilisé : liste des commandes actives d'un client
CREATE INDEX idx_orders_client_status
    ON orders (client_id, status, created_at DESC)
    WHERE is_deleted = FALSE;

-- Dashboard : commandes récentes par statut
CREATE INDEX idx_orders_status_created
    ON orders (status, created_at DESC)
    WHERE is_deleted = FALSE;

-- Commandes avec solde impayé (relances)
CREATE INDEX idx_orders_unpaid
    ON orders (client_id, payment_status, due_date)
    WHERE is_deleted = FALSE
      AND payment_status IN ('pending', 'partial', 'overdue');

-- Recherche par numéro de commande
CREATE UNIQUE INDEX idx_orders_number_active
    ON orders (order_number)
    WHERE is_deleted = FALSE;

-- Commandes par opérateur
CREATE INDEX idx_orders_created_by
    ON orders (created_by, created_at DESC)
    WHERE is_deleted = FALSE;

-- Index BRIN sur created_at pour les requêtes de reporting par période
CREATE INDEX idx_orders_created_brin
    ON orders USING BRIN (created_at)
    WITH (pages_per_range = 128);

-- Filtrage par devise pour reporting multi-devises
CREATE INDEX idx_orders_currency
    ON orders (currency, status)
    WHERE is_deleted = FALSE;

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS
-- ---------------------------------------------------------------------------
CREATE INDEX idx_order_items_order
    ON order_items (order_id, sort_order);

-- Recherche par référence article
CREATE INDEX idx_order_items_code
    ON order_items (item_code)
    WHERE item_code IS NOT NULL;

-- ---------------------------------------------------------------------------
-- INVOICES
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_invoices_number_active
    ON invoices (invoice_number)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_invoices_client_status
    ON invoices (client_id, status)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_invoices_order
    ON invoices (order_id)
    WHERE order_id IS NOT NULL AND is_deleted = FALSE;

-- Factures échues (utile pour les relances automatiques)
CREATE INDEX idx_invoices_overdue
    ON invoices (due_date, client_id)
    WHERE is_deleted = FALSE
      AND status IN ('issued', 'sent', 'partially_paid', 'overdue');

CREATE INDEX idx_invoices_issue_date_brin
    ON invoices USING BRIN (issue_date)
    WITH (pages_per_range = 128);

-- ---------------------------------------------------------------------------
-- PRO_FORMAS
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_pro_formas_number_active
    ON pro_formas (pro_forma_number)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_pro_formas_client
    ON pro_formas (client_id, created_at DESC)
    WHERE is_deleted = FALSE;

-- Pro forma non converties en commande
CREATE INDEX idx_pro_formas_pending
    ON pro_formas (validity_date, client_id)
    WHERE is_deleted = FALSE
      AND order_id IS NULL
      AND status NOT IN ('cancelled', 'archived');

-- ---------------------------------------------------------------------------
-- PAYMENT_TRANSACTIONS
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_txn_number
    ON payment_transactions (transaction_number);

CREATE INDEX idx_txn_order
    ON payment_transactions (order_id, transaction_date DESC)
    WHERE order_id IS NOT NULL;

CREATE INDEX idx_txn_invoice
    ON payment_transactions (invoice_id, transaction_date DESC)
    WHERE invoice_id IS NOT NULL;

CREATE INDEX idx_txn_client_method
    ON payment_transactions (client_id, method, transaction_date DESC);

-- Transactions en attente (processing queue)
CREATE INDEX idx_txn_pending
    ON payment_transactions (status, transaction_date)
    WHERE status IN ('pending', 'processing');

-- Référence externe (réconciliation bancaire)
CREATE INDEX idx_txn_external_ref
    ON payment_transactions (external_reference)
    WHERE external_reference IS NOT NULL;

CREATE INDEX idx_txn_date_brin
    ON payment_transactions USING BRIN (transaction_date)
    WITH (pages_per_range = 128);

-- ---------------------------------------------------------------------------
-- REFUNDS
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_refunds_number
    ON refunds (refund_number);

CREATE INDEX idx_refunds_order
    ON refunds (order_id)
    WHERE order_id IS NOT NULL;

CREATE INDEX idx_refunds_client_status
    ON refunds (client_id, status);

-- Remboursements en attente d'approbation
CREATE INDEX idx_refunds_pending_approval
    ON refunds (status, requested_at)
    WHERE status IN ('requested', 'under_review');

-- ---------------------------------------------------------------------------
-- DOCUMENTS
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_documents_number
    ON documents (document_number)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_documents_order
    ON documents (order_id, created_at DESC)
    WHERE order_id IS NOT NULL AND is_deleted = FALSE;

CREATE INDEX idx_documents_invoice
    ON documents (invoice_id)
    WHERE invoice_id IS NOT NULL AND is_deleted = FALSE;

CREATE INDEX idx_documents_type_status
    ON documents (document_type, status)
    WHERE is_deleted = FALSE;

-- Documents non signés en attente
CREATE INDEX idx_documents_unsigned
    ON documents (document_type, created_at)
    WHERE is_deleted = FALSE AND is_signed = FALSE
      AND document_type IN ('invoice', 'pro_forma');

-- Tags GIN pour recherche par étiquette
CREATE INDEX idx_documents_tags
    ON documents USING GIN (tags)
    WHERE is_deleted = FALSE;

-- ---------------------------------------------------------------------------
-- ORDER_STATUS_HISTORY
-- ---------------------------------------------------------------------------
CREATE INDEX idx_status_history_order
    ON order_status_history (order_id, changed_at DESC);

-- ---------------------------------------------------------------------------
-- AUDIT LOGS
-- ---------------------------------------------------------------------------
-- Les partitions ont leurs propres index créés automatiquement
-- Index supplémentaires sur les colonnes de recherche fréquentes

CREATE INDEX idx_audit_user
    ON audit.audit_logs (user_id, occurred_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX idx_audit_entity
    ON audit.audit_logs (entity_type, entity_id, occurred_at DESC);

CREATE INDEX idx_audit_action
    ON audit.audit_logs (action, occurred_at DESC);

CREATE INDEX idx_audit_severity
    ON audit.audit_logs (severity, occurred_at DESC)
    WHERE severity IN ('warning', 'error', 'critical');

-- ---------------------------------------------------------------------------
-- NOTIFICATIONS
-- ---------------------------------------------------------------------------
CREATE INDEX idx_notif_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE user_id IS NOT NULL AND is_read = FALSE;

CREATE INDEX idx_notif_client
    ON notifications (client_id, created_at DESC)
    WHERE client_id IS NOT NULL;
