-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 006 : Business Functions & Triggers
-- =============================================================================

-- ---------------------------------------------------------------------------
-- FUNCTION : generate_sequence_number
-- Génère les numéros séquentiels thread-safe (CMD-202604-0001)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION generate_sequence_number(
    p_prefix    TEXT,
    p_setting   TEXT   -- clé dans app_settings
)
RETURNS TEXT AS $$
DECLARE
    v_next  INTEGER;
    v_year  TEXT  := TO_CHAR(CURRENT_DATE, 'YYYY');
    v_month TEXT  := TO_CHAR(CURRENT_DATE, 'MM');
BEGIN
    -- FOR UPDATE : verrou row-level pour éviter les doublons sous charge
    UPDATE app_settings
    SET value = (value::INTEGER + 1)::TEXT::JSONB
    WHERE key = p_setting
    RETURNING value::INTEGER - 1 INTO v_next;

    IF v_next IS NULL THEN
        RAISE EXCEPTION 'Setting % not found', p_setting;
    END IF;

    RETURN p_prefix || '-' || v_year || v_month || '-' || LPAD(v_next::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- FUNCTION : recalculate_order_totals
-- Recalcule les totaux d'une commande à partir de ses lignes
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION recalculate_order_totals(p_order_id UUID)
RETURNS VOID AS $$
DECLARE
    v_subtotal  BIGINT;
    v_tax_rate  NUMERIC(5,2);
    v_tax       BIGINT;
    v_discount  BIGINT;
    v_shipping  BIGINT;
    v_total     BIGINT;
BEGIN
    SELECT
        COALESCE(SUM(line_total_cents), 0),
        tax_rate,
        discount_cents,
        shipping_cents
    INTO v_subtotal, v_tax_rate, v_discount, v_shipping
    FROM order_items
    JOIN orders ON orders.id = p_order_id
    WHERE order_items.order_id = p_order_id
    GROUP BY orders.tax_rate, orders.discount_cents, orders.shipping_cents;

    v_subtotal := COALESCE(v_subtotal, 0);
    v_tax      := ROUND(v_subtotal * v_tax_rate / 100)::BIGINT;
    v_discount := COALESCE(v_discount, 0);
    v_shipping := COALESCE(v_shipping, 0);
    v_total    := v_subtotal + v_tax + v_shipping - v_discount;

    UPDATE orders SET
        subtotal_cents = v_subtotal,
        tax_cents      = v_tax,
        total_cents    = GREATEST(v_total, 0),
        updated_at     = CURRENT_TIMESTAMP
    WHERE id = p_order_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger : recalcul automatique après chaque modification d'une ligne
CREATE OR REPLACE FUNCTION trg_recalculate_on_item_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM recalculate_order_totals(OLD.order_id);
    ELSE
        PERFORM recalculate_order_totals(NEW.order_id);
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_items_recalc
    AFTER INSERT OR UPDATE OR DELETE ON order_items
    FOR EACH ROW EXECUTE FUNCTION trg_recalculate_on_item_change();

-- ---------------------------------------------------------------------------
-- FUNCTION : update_order_payment_status
-- Met à jour le payment_status de la commande après chaque transaction
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_order_payment_status(p_order_id UUID)
RETURNS VOID AS $$
DECLARE
    v_total         BIGINT;
    v_paid          BIGINT;
    v_refunded      BIGINT;
    v_new_status    payment_status;
BEGIN
    SELECT total_cents, paid_cents, refunded_cents
    INTO v_total, v_paid, v_refunded
    FROM orders
    WHERE id = p_order_id;

    v_new_status := CASE
        WHEN v_refunded >= v_total                      THEN 'refunded'::payment_status
        WHEN v_paid     >= v_total                      THEN 'paid'::payment_status
        WHEN v_paid > 0 AND v_refunded > 0              THEN 'partial_refund'::payment_status
        WHEN v_paid > 0                                 THEN 'partial'::payment_status
        WHEN CURRENT_DATE > (SELECT due_date FROM orders WHERE id = p_order_id)
             AND (SELECT due_date FROM orders WHERE id = p_order_id) IS NOT NULL
                                                        THEN 'overdue'::payment_status
        ELSE                                                 'pending'::payment_status
    END;

    UPDATE orders
    SET payment_status = v_new_status,
        updated_at     = CURRENT_TIMESTAMP
    WHERE id = p_order_id AND payment_status != v_new_status;
END;
$$ LANGUAGE plpgsql;

-- Trigger : appliquer le paiement à la commande après transaction complétée
CREATE OR REPLACE FUNCTION trg_apply_transaction_to_order()
RETURNS TRIGGER AS $$
BEGIN
    -- Seulement quand le statut passe à 'completed'
    IF NEW.status = 'completed' AND (OLD.status IS DISTINCT FROM 'completed') THEN
        IF NEW.order_id IS NOT NULL THEN
            IF NEW.transaction_type = 'payment' THEN
                UPDATE orders
                SET paid_cents = paid_cents + NEW.amount_cents,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.order_id;
            ELSIF NEW.transaction_type = 'refund' THEN
                UPDATE orders
                SET refunded_cents = refunded_cents + NEW.amount_cents,
                    paid_cents     = GREATEST(paid_cents - NEW.amount_cents, 0),
                    updated_at     = CURRENT_TIMESTAMP
                WHERE id = NEW.order_id;
            END IF;
            PERFORM update_order_payment_status(NEW.order_id);
        END IF;

        IF NEW.invoice_id IS NOT NULL THEN
            IF NEW.transaction_type = 'payment' THEN
                UPDATE invoices
                SET paid_cents = paid_cents + NEW.amount_cents,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.invoice_id;
            END IF;
            -- Mettre à jour le statut de la facture
            UPDATE invoices SET
                status = CASE
                    WHEN paid_cents >= total_cents THEN 'paid'::invoice_status
                    WHEN paid_cents > 0            THEN 'partially_paid'::invoice_status
                    ELSE status
                END,
                paid_at = CASE
                    WHEN paid_cents >= total_cents AND paid_at IS NULL THEN CURRENT_TIMESTAMP
                    ELSE paid_at
                END
            WHERE id = NEW.invoice_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_transaction_apply
    AFTER UPDATE ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION trg_apply_transaction_to_order();

-- ---------------------------------------------------------------------------
-- FUNCTION : record_order_status_change (trigger)
-- Journalise chaque transition de statut de commande
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_record_order_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO order_status_history
            (order_id, from_status, to_status, changed_by, changed_at)
        VALUES
            (NEW.id, OLD.status, NEW.status, NEW.confirmed_by, CURRENT_TIMESTAMP);

        -- Mettre à jour les dates spécifiques
        IF NEW.status = 'confirmed' THEN
            NEW.confirmed_at := CURRENT_TIMESTAMP;
        ELSIF NEW.status = 'delivered' THEN
            NEW.delivered_at := CURRENT_TIMESTAMP;
        ELSIF NEW.status = 'cancelled' THEN
            NEW.cancelled_at := CURRENT_TIMESTAMP;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_status_history
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION trg_record_order_status_change();

-- ---------------------------------------------------------------------------
-- FUNCTION : lock_account_on_failed_login
-- Verrouille le compte après 5 échecs consécutifs (protection brute-force)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION lock_account_on_failed_login(p_user_id UUID)
RETURNS VOID AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE users
    SET failed_login_count = failed_login_count + 1
    WHERE id = p_user_id
    RETURNING failed_login_count INTO v_count;

    IF v_count >= 5 THEN
        UPDATE users
        SET locked_until = CURRENT_TIMESTAMP + INTERVAL '15 minutes',
            status       = 'suspended'
        WHERE id = p_user_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION reset_login_count(p_user_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET failed_login_count = 0,
        locked_until       = NULL,
        last_login_at      = CURRENT_TIMESTAMP
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ---------------------------------------------------------------------------
-- FUNCTION : soft_delete_cascade
-- Marque une entité comme supprimée et propage si nécessaire
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION soft_delete_order(p_order_id UUID, p_deleted_by UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE orders SET
        is_deleted = TRUE,
        deleted_at = CURRENT_TIMESTAMP,
        deleted_by = p_deleted_by
    WHERE id = p_order_id AND is_deleted = FALSE;

    -- Invalider les documents liés
    UPDATE documents SET
        is_deleted = TRUE,
        deleted_at = CURRENT_TIMESTAMP,
        deleted_by = p_deleted_by
    WHERE order_id = p_order_id AND is_deleted = FALSE;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- FUNCTION : audit generic trigger
-- Insère automatiquement dans audit.audit_logs sur chaque mutation
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    v_old_data  JSONB;
    v_new_data  JSONB;
    v_changed   TEXT[];
    v_action    TEXT;
    v_entity_id TEXT;
BEGIN
    v_action := TG_OP;

    IF TG_OP = 'INSERT' THEN
        v_new_data  := to_jsonb(NEW);
        v_entity_id := NEW.id::TEXT;
        -- Masquer les champs sensibles
        v_new_data  := v_new_data
                        - 'hashed_password'
                        - 'mfa_secret';
    ELSIF TG_OP = 'UPDATE' THEN
        v_old_data  := to_jsonb(OLD) - 'hashed_password' - 'mfa_secret' - 'updated_at';
        v_new_data  := to_jsonb(NEW) - 'hashed_password' - 'mfa_secret' - 'updated_at';
        v_entity_id := NEW.id::TEXT;
        -- Calculer les champs modifiés
        SELECT ARRAY_AGG(key)
        INTO v_changed
        FROM jsonb_each(v_new_data) AS n(key, val)
        WHERE val IS DISTINCT FROM (v_old_data ->> key)::JSONB;
    ELSIF TG_OP = 'DELETE' THEN
        v_old_data  := to_jsonb(OLD) - 'hashed_password' - 'mfa_secret';
        v_entity_id := OLD.id::TEXT;
    END IF;

    INSERT INTO audit.audit_logs (
        action, entity_type, entity_id,
        old_values, new_values, changed_fields,
        occurred_at
    ) VALUES (
        v_action,
        TG_TABLE_NAME,
        v_entity_id,
        v_old_data,
        v_new_data,
        v_changed,
        CURRENT_TIMESTAMP
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Activer l'audit sur les tables financières critiques
CREATE TRIGGER audit_orders
    AFTER INSERT OR UPDATE OR DELETE ON orders
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_invoices
    AFTER INSERT OR UPDATE OR DELETE ON invoices
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_payment_transactions
    AFTER INSERT OR UPDATE OR DELETE ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_refunds
    AFTER INSERT OR UPDATE OR DELETE ON refunds
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

CREATE TRIGGER audit_users
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();

-- ---------------------------------------------------------------------------
-- FUNCTION : get_client_balance
-- Solde total dû par un client (toutes commandes actives)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_client_balance(p_client_id UUID)
RETURNS TABLE (
    total_orders        INTEGER,
    total_amount_cents  BIGINT,
    total_paid_cents    BIGINT,
    total_balance_cents BIGINT,
    overdue_amount_cents BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER                               AS total_orders,
        COALESCE(SUM(total_cents),     0)::BIGINT       AS total_amount_cents,
        COALESCE(SUM(paid_cents),      0)::BIGINT       AS total_paid_cents,
        COALESCE(SUM(balance_due_cents),0)::BIGINT      AS total_balance_cents,
        COALESCE(SUM(CASE
            WHEN due_date < CURRENT_DATE
            AND payment_status NOT IN ('paid','refunded')
            THEN balance_due_cents ELSE 0 END), 0)::BIGINT AS overdue_amount_cents
    FROM orders
    WHERE client_id  = p_client_id
      AND is_deleted = FALSE
      AND status NOT IN ('cancelled', 'archived');
END;
$$ LANGUAGE plpgsql STABLE;
