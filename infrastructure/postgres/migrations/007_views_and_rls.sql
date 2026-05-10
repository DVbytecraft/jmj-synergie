-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 007 : Views, Row Level Security & Reporting
-- =============================================================================

-- ---------------------------------------------------------------------------
-- SCHEMA reporting : Vues métier
-- ---------------------------------------------------------------------------

-- ── Vue : commandes enrichies ─────────────────────────────────────────────
CREATE VIEW reporting.v_orders AS
SELECT
    o.id,
    o.order_number,
    o.status,
    o.payment_status,
    o.currency,

    -- Client
    c.id              AS client_id,
    c.code            AS client_code,
    c.full_name       AS client_name,
    c.company_name,
    c.phone           AS client_phone,
    c.email           AS client_email,
    c.country         AS client_country,

    -- Amounts (centimes)
    o.subtotal_cents,
    o.tax_rate,
    o.tax_cents,
    o.discount_cents,
    o.shipping_cents,
    o.total_cents,
    o.paid_cents,
    o.refunded_cents,
    o.balance_due_cents,

    -- Amounts (unités monétaires — pour affichage)
    ROUND(o.subtotal_cents   / 100.0, 2)    AS subtotal,
    ROUND(o.total_cents      / 100.0, 2)    AS total,
    ROUND(o.paid_cents       / 100.0, 2)    AS paid,
    ROUND(o.balance_due_cents/ 100.0, 2)    AS balance_due,

    -- Items
    (SELECT COUNT(*) FROM order_items WHERE order_id = o.id)::INT AS items_count,

    -- Dates
    o.ordered_at,
    o.confirmed_at,
    o.due_date,
    o.delivery_date,
    o.delivered_at,

    -- Retard de paiement
    CASE
        WHEN o.due_date IS NOT NULL AND o.due_date < CURRENT_DATE
             AND o.payment_status NOT IN ('paid','refunded')
        THEN CURRENT_DATE - o.due_date
        ELSE 0
    END AS days_overdue,

    -- Opérateur
    u.full_name AS created_by_name,
    o.created_at,
    o.updated_at

FROM orders o
JOIN clients c ON c.id = o.client_id
JOIN users   u ON u.id = o.created_by
WHERE o.is_deleted = FALSE;

-- ── Vue : dashboard KPI ───────────────────────────────────────────────────
CREATE VIEW reporting.v_dashboard_kpi AS
WITH base AS (
    SELECT
        date_trunc('month', ordered_at)         AS month,
        COUNT(*)                                 AS total_orders,
        COUNT(*) FILTER (WHERE status = 'delivered')   AS delivered,
        COUNT(*) FILTER (WHERE status = 'cancelled')   AS cancelled,
        SUM(total_cents)                         AS revenue_cents,
        SUM(paid_cents)                          AS collected_cents,
        SUM(balance_due_cents)                   AS outstanding_cents,
        COUNT(DISTINCT client_id)                AS unique_clients
    FROM orders
    WHERE is_deleted = FALSE
      AND status NOT IN ('draft', 'archived')
    GROUP BY 1
)
SELECT
    month,
    total_orders,
    delivered,
    cancelled,
    ROUND(delivered::NUMERIC / NULLIF(total_orders,0) * 100, 1)  AS delivery_rate_pct,
    ROUND(revenue_cents     / 100.0, 2)                           AS revenue,
    ROUND(collected_cents   / 100.0, 2)                           AS collected,
    ROUND(outstanding_cents / 100.0, 2)                           AS outstanding,
    unique_clients
FROM base
ORDER BY month DESC;

-- ── Vue : clients avec soldes ──────────────────────────────────────────────
CREATE VIEW reporting.v_client_balances AS
SELECT
    c.id,
    c.code,
    c.client_type,
    c.status,
    c.full_name,
    c.company_name,
    c.phone,
    c.email,
    c.country,
    c.currency,

    COUNT(o.id)::INT                                              AS total_orders,
    COUNT(o.id) FILTER (WHERE o.status = 'delivered')::INT        AS completed_orders,
    COALESCE(SUM(o.total_cents),  0)::BIGINT                      AS lifetime_value_cents,
    COALESCE(SUM(o.paid_cents),   0)::BIGINT                      AS total_paid_cents,
    COALESCE(SUM(o.balance_due_cents), 0)::BIGINT                 AS outstanding_cents,
    COALESCE(SUM(
        CASE WHEN o.due_date < CURRENT_DATE
             AND o.payment_status NOT IN ('paid','refunded')
        THEN o.balance_due_cents ELSE 0 END
    ), 0)::BIGINT                                                  AS overdue_cents,
    MAX(o.ordered_at)                                              AS last_order_at

FROM clients c
LEFT JOIN orders o
    ON o.client_id = c.id
    AND o.is_deleted = FALSE
    AND o.status NOT IN ('cancelled','archived')
WHERE c.is_deleted = FALSE
GROUP BY c.id, c.code, c.client_type, c.status, c.full_name,
         c.company_name, c.phone, c.email, c.country, c.currency;

-- ── Vue : factures avec statut de paiement ────────────────────────────────
CREATE VIEW reporting.v_invoices AS
SELECT
    i.id,
    i.invoice_number,
    i.status,
    i.currency,

    c.id           AS client_id,
    c.full_name    AS client_name,
    c.company_name,

    o.order_number,

    -- Amounts
    ROUND(i.total_cents         / 100.0, 2) AS total,
    ROUND(i.paid_cents          / 100.0, 2) AS paid,
    ROUND(i.balance_due_cents   / 100.0, 2) AS balance_due,

    i.issue_date,
    i.due_date,
    i.sent_at,
    i.paid_at,
    i.is_signed,
    i.is_stamped,

    -- Jours de retard
    CASE
        WHEN i.due_date < CURRENT_DATE AND i.status NOT IN ('paid','cancelled','written_off')
        THEN (CURRENT_DATE - i.due_date)
        ELSE 0
    END AS days_overdue,

    u.full_name AS created_by_name,
    i.created_at

FROM invoices i
JOIN clients  c ON c.id = i.client_id
LEFT JOIN orders o ON o.id = i.order_id
JOIN users    u ON u.id = i.created_by
WHERE i.is_deleted = FALSE;

-- ── Vue : transactions financières complètes ──────────────────────────────
CREATE VIEW reporting.v_transactions AS
SELECT
    t.id,
    t.transaction_number,
    t.transaction_type,
    t.status,
    t.method,
    t.currency,

    c.full_name     AS client_name,
    o.order_number,
    i.invoice_number,

    ROUND(t.amount_cents      / 100.0, 2) AS amount,
    ROUND(t.amount_base_cents / 100.0, 2) AS amount_base,
    ROUND(t.fees_cents        / 100.0, 2) AS fees,

    t.external_reference,
    t.transaction_date,
    t.completed_at,

    u.full_name     AS recorded_by_name

FROM payment_transactions t
JOIN clients  c ON c.id = t.client_id
LEFT JOIN orders   o ON o.id = t.order_id
LEFT JOIN invoices i ON i.id = t.invoice_id
JOIN users    u ON u.id = t.recorded_by;

-- ── Vue : remboursements ──────────────────────────────────────────────────
CREATE VIEW reporting.v_refunds AS
SELECT
    r.id,
    r.refund_number,
    r.status,
    r.reason,
    r.currency,

    c.full_name     AS client_name,
    o.order_number,
    i.invoice_number,

    ROUND(r.requested_amount_cents / 100.0, 2) AS requested_amount,
    ROUND(r.approved_amount_cents  / 100.0, 2) AS approved_amount,
    ROUND(r.refunded_amount_cents  / 100.0, 2) AS refunded_amount,

    r.requested_at,
    r.approved_at,
    r.completed_at,
    r.rejection_reason,

    req.full_name   AS requested_by_name,
    apr.full_name   AS approved_by_name

FROM refunds r
JOIN clients  c ON c.id = r.client_id
LEFT JOIN orders   o   ON o.id   = r.order_id
LEFT JOIN invoices i   ON i.id   = r.invoice_id
JOIN users    req ON req.id = r.requested_by
LEFT JOIN users apr ON apr.id = r.approved_by;

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- Isolation des données par rôle utilisateur
-- ---------------------------------------------------------------------------
-- NOTE : RLS s'active avec un role PostgreSQL applicatif distinct du superuser.
-- L'application se connecte via le role 'jmj_app' (non superuser).

-- Créer le rôle applicatif
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jmj_app') THEN
        CREATE ROLE jmj_app LOGIN;
    END IF;
END $$;

-- Permissions minimales (least privilege)
GRANT USAGE ON SCHEMA public    TO jmj_app;
GRANT USAGE ON SCHEMA reporting TO jmj_app;
GRANT USAGE ON SCHEMA audit     TO jmj_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public    TO jmj_app;
GRANT SELECT                          ON ALL TABLES IN SCHEMA reporting TO jmj_app;
GRANT SELECT, INSERT                  ON ALL TABLES IN SCHEMA audit     TO jmj_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jmj_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO jmj_app;

-- Activer RLS
ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients              ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders               ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices             ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE refunds              ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents            ENABLE ROW LEVEL SECURITY;

-- Variable de session : rôle de l'utilisateur courant
-- L'application doit appeler : SET LOCAL app.current_user_role = 'operator';
--                              SET LOCAL app.current_user_id   = 'uuid';

-- ── Politique orders : les operators ne voient que leurs propres commandes ──
CREATE POLICY orders_operator_policy ON orders
    FOR ALL
    TO jmj_app
    USING (
        current_setting('app.current_user_role', TRUE) IN ('super_admin','admin','manager')
        OR
        created_by = current_setting('app.current_user_id', TRUE)::UUID
    );

-- ── Politique clients : tous les rôles actifs voient tous les clients actifs
CREATE POLICY clients_read_policy ON clients
    FOR SELECT
    TO jmj_app
    USING (is_deleted = FALSE);

-- ── Politique clients : seuls admin+ peuvent supprimer (soft) ─────────────
CREATE POLICY clients_delete_policy ON clients
    FOR UPDATE
    TO jmj_app
    USING (
        current_setting('app.current_user_role', TRUE) IN ('super_admin','admin')
        OR is_deleted = FALSE
    );

-- ── Politique transactions : en lecture seule pour les operators ──────────
CREATE POLICY txn_read_policy ON payment_transactions
    FOR SELECT
    TO jmj_app
    USING (TRUE);  -- Tous lisent, mais la création est contrôlée applicativement

CREATE POLICY txn_write_policy ON payment_transactions
    FOR INSERT
    TO jmj_app
    WITH CHECK (
        current_setting('app.current_user_role', TRUE) IN ('super_admin','admin','manager')
    );

-- ── Politique remboursements : lecture pour tous, approbation pour manager+
CREATE POLICY refund_read_policy ON refunds
    FOR SELECT TO jmj_app USING (TRUE);

CREATE POLICY refund_approve_policy ON refunds
    FOR UPDATE TO jmj_app
    USING (
        current_setting('app.current_user_role', TRUE) IN ('super_admin','admin','manager')
    );

-- ── Politique documents ───────────────────────────────────────────────────
CREATE POLICY documents_policy ON documents
    FOR ALL TO jmj_app
    USING (is_deleted = FALSE);

-- ── Politique users : chaque utilisateur voit son propre profil + les admins voient tous ──
CREATE POLICY users_policy ON users
    FOR SELECT TO jmj_app
    USING (
        id = current_setting('app.current_user_id', TRUE)::UUID
        OR current_setting('app.current_user_role', TRUE) IN ('super_admin','admin')
    );

-- ---------------------------------------------------------------------------
-- MATERIALIZED VIEW : tableau de bord mensuel (refresh périodique)
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW reporting.mv_monthly_summary AS
SELECT
    DATE_TRUNC('month', o.ordered_at)::DATE                         AS month,
    o.currency,
    COUNT(*)                                                         AS order_count,
    COUNT(*) FILTER (WHERE o.status = 'delivered')                   AS delivered_count,
    COUNT(*) FILTER (WHERE o.payment_status = 'paid')               AS paid_count,
    SUM(o.total_cents)                                               AS revenue_cents,
    SUM(o.paid_cents)                                                AS collected_cents,
    SUM(o.balance_due_cents)                                         AS outstanding_cents,
    COUNT(DISTINCT o.client_id)                                      AS unique_clients,
    AVG(o.total_cents)::BIGINT                                       AS avg_order_cents,
    MAX(o.total_cents)                                               AS max_order_cents
FROM orders o
WHERE o.is_deleted = FALSE
  AND o.status NOT IN ('draft','cancelled','archived')
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- Index sur la vue matérialisée
CREATE UNIQUE INDEX idx_mv_monthly_summary
    ON reporting.mv_monthly_summary (month, currency);

-- Refresh la vue (à planifier via pg_cron ou cron externe)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY reporting.mv_monthly_summary;

-- ---------------------------------------------------------------------------
-- CONSTRAINTS DIFFÉRÉES : cohérence globale
-- ---------------------------------------------------------------------------
-- Assure que order.paid_cents = SUM(transactions completed pour cet order)
-- Vérification d'intégrité (à appeler manuellement ou via pg_cron)
CREATE OR REPLACE FUNCTION verify_financial_integrity()
RETURNS TABLE (issue TEXT, entity_id UUID, detail TEXT) AS $$
BEGIN
    -- Commandes dont le paid_cents ne correspond pas aux transactions
    RETURN QUERY
    SELECT
        'order_paid_mismatch'::TEXT,
        o.id,
        FORMAT('order.paid_cents=%s, SUM(txn)=%s',
               o.paid_cents,
               COALESCE(SUM(t.amount_cents),0))::TEXT
    FROM orders o
    LEFT JOIN payment_transactions t
        ON t.order_id = o.id
        AND t.transaction_type = 'payment'
        AND t.status = 'completed'
    WHERE o.is_deleted = FALSE
    GROUP BY o.id, o.paid_cents
    HAVING o.paid_cents != COALESCE(SUM(t.amount_cents), 0);

    -- Factures dont le statut ne correspond pas au solde
    RETURN QUERY
    SELECT
        'invoice_status_mismatch'::TEXT,
        i.id,
        FORMAT('status=%s, paid=%s, total=%s',
               i.status, i.paid_cents, i.total_cents)::TEXT
    FROM invoices i
    WHERE i.is_deleted = FALSE
      AND (
          (i.paid_cents >= i.total_cents AND i.status NOT IN ('paid','cancelled','written_off'))
          OR
          (i.paid_cents < i.total_cents AND i.status = 'paid')
      );
END;
$$ LANGUAGE plpgsql STABLE;
