-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 003 : Financial Tables (Invoices, Payments, Refunds)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TABLE : invoices (factures définitives)
-- ---------------------------------------------------------------------------
CREATE TABLE invoices (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_number      VARCHAR(30)     NOT NULL,   -- FACT-202604-0001
    order_id            UUID            REFERENCES orders(id) ON DELETE RESTRICT,
    client_id           UUID            NOT NULL REFERENCES clients(id),

    -- ── Status ────────────────────────────────────────────────────────────
    status              invoice_status  NOT NULL DEFAULT 'draft',

    -- ── Amounts ───────────────────────────────────────────────────────────
    subtotal_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (subtotal_cents >= 0),
    tax_rate            NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (tax_rate BETWEEN 0 AND 100),
    tax_cents           BIGINT          NOT NULL DEFAULT 0
                        CHECK (tax_cents >= 0),
    discount_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (discount_cents >= 0),
    shipping_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (shipping_cents >= 0),
    total_cents         BIGINT          NOT NULL DEFAULT 0
                        CHECK (total_cents >= 0),
    paid_cents          BIGINT          NOT NULL DEFAULT 0
                        CHECK (paid_cents >= 0),
    balance_due_cents   BIGINT          GENERATED ALWAYS AS (total_cents - paid_cents) STORED,

    -- ── Currency ──────────────────────────────────────────────────────────
    currency            VARCHAR(3)      NOT NULL DEFAULT 'XAF'
                        CHECK (currency ~ '^[A-Z]{3}$'),

    -- ── Dates ─────────────────────────────────────────────────────────────
    issue_date          DATE            NOT NULL DEFAULT CURRENT_DATE,
    due_date            DATE            NOT NULL,
    sent_at             TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,    -- Date du dernier paiement complétant la facture

    -- ── Legal Info (snapshot at time of invoicing) ────────────────────────
    -- Stocker un snapshot garantit l'intégrité légale même si le client change
    client_snapshot     JSONB           NOT NULL DEFAULT '{}'::JSONB,
    company_snapshot    JSONB           NOT NULL DEFAULT '{}'::JSONB,

    -- ── References ────────────────────────────────────────────────────────
    purchase_order_ref  VARCHAR(100),
    notes               TEXT,
    terms_and_conditions TEXT,
    payment_instructions TEXT,

    -- ── File ──────────────────────────────────────────────────────────────
    file_path           VARCHAR(500),
    is_signed           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_stamped          BOOLEAN         NOT NULL DEFAULT FALSE,
    signed_at           TIMESTAMPTZ,
    signed_by           UUID            REFERENCES users(id),

    -- ── Staff ─────────────────────────────────────────────────────────────
    created_by          UUID            NOT NULL REFERENCES users(id),
    issued_by           UUID            REFERENCES users(id),

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ── Constraints ───────────────────────────────────────────────────────
    CONSTRAINT invoices_number_unique       UNIQUE (invoice_number),
    CONSTRAINT invoices_due_after_issue     CHECK (due_date >= issue_date),
    CONSTRAINT invoices_paid_not_exceed     CHECK (paid_cents <= total_cents),
    CONSTRAINT invoices_paid_has_date       CHECK (
        (status = 'paid' AND paid_at IS NOT NULL) OR status != 'paid'
    )
);

CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : invoice_items (lignes de la facture — snapshot de order_items)
-- ---------------------------------------------------------------------------
CREATE TABLE invoice_items (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id          UUID            NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    order_item_id       UUID            REFERENCES order_items(id) ON DELETE SET NULL,
    sort_order          SMALLINT        NOT NULL DEFAULT 0,

    item_code           VARCHAR(50),
    description         VARCHAR(1000)   NOT NULL,
    unit                VARCHAR(20),
    quantity            NUMERIC(14,4)   NOT NULL CHECK (quantity > 0),
    unit_price_cents    BIGINT          NOT NULL CHECK (unit_price_cents >= 0),
    item_discount_cents BIGINT          NOT NULL DEFAULT 0 CHECK (item_discount_cents >= 0),
    item_tax_rate       NUMERIC(5,2)    NOT NULL DEFAULT 0.00,
    item_tax_cents      BIGINT          NOT NULL DEFAULT 0,
    line_total_cents    BIGINT          NOT NULL CHECK (line_total_cents >= 0),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- TABLE : pro_formas (devis / factures pro forma)
-- ---------------------------------------------------------------------------
CREATE TABLE pro_formas (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    pro_forma_number    VARCHAR(30)     NOT NULL,   -- PF-202604-0001
    client_id           UUID            NOT NULL REFERENCES clients(id),
    order_id            UUID            REFERENCES orders(id) ON DELETE SET NULL,

    -- ── Status ────────────────────────────────────────────────────────────
    status              document_status NOT NULL DEFAULT 'draft',

    -- ── Amounts ───────────────────────────────────────────────────────────
    subtotal_cents      BIGINT          NOT NULL DEFAULT 0 CHECK (subtotal_cents >= 0),
    tax_rate            NUMERIC(5,2)    NOT NULL DEFAULT 0.00,
    tax_cents           BIGINT          NOT NULL DEFAULT 0 CHECK (tax_cents >= 0),
    discount_cents      BIGINT          NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
    shipping_cents      BIGINT          NOT NULL DEFAULT 0 CHECK (shipping_cents >= 0),
    total_cents         BIGINT          NOT NULL DEFAULT 0 CHECK (total_cents >= 0),
    currency            VARCHAR(3)      NOT NULL DEFAULT 'XAF',

    -- ── Dates ─────────────────────────────────────────────────────────────
    issue_date          DATE            NOT NULL DEFAULT CURRENT_DATE,
    validity_date       DATE            NOT NULL,   -- Date d'expiration du devis
    converted_at        TIMESTAMPTZ,               -- Date de conversion en commande

    -- ── Snapshots ─────────────────────────────────────────────────────────
    client_snapshot     JSONB           NOT NULL DEFAULT '{}'::JSONB,
    company_snapshot    JSONB           NOT NULL DEFAULT '{}'::JSONB,

    -- ── File ──────────────────────────────────────────────────────────────
    file_path           VARCHAR(500),
    is_signed           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_stamped          BOOLEAN         NOT NULL DEFAULT FALSE,
    signed_at           TIMESTAMPTZ,
    signed_by           UUID            REFERENCES users(id),

    -- ── Notes ─────────────────────────────────────────────────────────────
    notes               TEXT,
    terms_and_conditions TEXT,

    -- ── Staff ─────────────────────────────────────────────────────────────
    created_by          UUID            NOT NULL REFERENCES users(id),

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pro_formas_number_unique         UNIQUE (pro_forma_number),
    CONSTRAINT pro_formas_validity_after_issue  CHECK (validity_date >= issue_date)
);

CREATE TRIGGER trg_pro_formas_updated_at
    BEFORE UPDATE ON pro_formas
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : pro_forma_items
-- ---------------------------------------------------------------------------
CREATE TABLE pro_forma_items (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    pro_forma_id        UUID            NOT NULL REFERENCES pro_formas(id) ON DELETE CASCADE,
    sort_order          SMALLINT        NOT NULL DEFAULT 0,

    item_code           VARCHAR(50),
    description         VARCHAR(1000)   NOT NULL,
    unit                VARCHAR(20),
    quantity            NUMERIC(14,4)   NOT NULL CHECK (quantity > 0),
    unit_price_cents    BIGINT          NOT NULL CHECK (unit_price_cents >= 0),
    item_discount_cents BIGINT          NOT NULL DEFAULT 0,
    item_tax_rate       NUMERIC(5,2)    NOT NULL DEFAULT 0.00,
    item_tax_cents      BIGINT          NOT NULL DEFAULT 0,
    line_total_cents    BIGINT          NOT NULL CHECK (line_total_cents >= 0),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- TABLE : payment_transactions
-- ---------------------------------------------------------------------------
CREATE TABLE payment_transactions (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_number  VARCHAR(40)         NOT NULL,   -- TXN-20260411-ABCD1234
    order_id            UUID                REFERENCES orders(id) ON DELETE RESTRICT,
    invoice_id          UUID                REFERENCES invoices(id) ON DELETE RESTRICT,
    client_id           UUID                NOT NULL REFERENCES clients(id),

    -- ── Au moins un lien requis : order ou invoice ─────────────────────────
    CONSTRAINT txn_has_reference CHECK (
        order_id IS NOT NULL OR invoice_id IS NOT NULL
    ),

    -- ── Type & Status ─────────────────────────────────────────────────────
    transaction_type    transaction_type    NOT NULL DEFAULT 'payment',
    status              transaction_status  NOT NULL DEFAULT 'pending',
    method              payment_method      NOT NULL,

    -- ── Amounts ───────────────────────────────────────────────────────────
    amount_cents        BIGINT              NOT NULL
                        CHECK (amount_cents > 0),
    currency            VARCHAR(3)          NOT NULL DEFAULT 'XAF',
    -- Montant converti en devise de base (XAF) pour reporting unifié
    amount_base_cents   BIGINT              NOT NULL
                        CHECK (amount_base_cents > 0),
    exchange_rate       NUMERIC(18,8)       NOT NULL DEFAULT 1.00000000,
    fees_cents          BIGINT              NOT NULL DEFAULT 0
                        CHECK (fees_cents >= 0),

    -- ── References ────────────────────────────────────────────────────────
    external_reference  VARCHAR(100),       -- Référence banque / mobile money
    receipt_number      VARCHAR(50),
    bank_name           VARCHAR(100),
    account_last4       VARCHAR(4),         -- 4 derniers chiffres (sécurité)
    check_number        VARCHAR(50),

    -- ── Dates ─────────────────────────────────────────────────────────────
    transaction_date    TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    value_date          DATE,               -- Date de valeur bancaire
    completed_at        TIMESTAMPTZ,
    failed_at           TIMESTAMPTZ,

    -- ── Failure ───────────────────────────────────────────────────────────
    failure_reason      TEXT,
    failure_code        VARCHAR(50),

    -- ── Notes ─────────────────────────────────────────────────────────────
    notes               TEXT,
    metadata            JSONB               DEFAULT '{}'::JSONB,

    -- ── Staff ─────────────────────────────────────────────────────────────
    recorded_by         UUID                NOT NULL REFERENCES users(id),
    verified_by         UUID                REFERENCES users(id),

    -- ── Immutabilité : les transactions complétées ne peuvent être modifiées
    -- (enforced via trigger ci-dessous)

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT txn_number_unique            UNIQUE (transaction_number),
    CONSTRAINT txn_completed_has_date       CHECK (
        (status = 'completed' AND completed_at IS NOT NULL) OR status != 'completed'
    ),
    CONSTRAINT txn_failed_has_date          CHECK (
        (status = 'failed' AND failed_at IS NOT NULL) OR status != 'failed'
    )
);

CREATE TRIGGER trg_transactions_updated_at
    BEFORE UPDATE ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Immutabilité des transactions complétées (protection anti-fraude)
CREATE OR REPLACE FUNCTION prevent_completed_txn_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('completed', 'reversed') THEN
        RAISE EXCEPTION
            'Transaction % est % et ne peut plus être modifiée. Créez une transaction corrective.',
            OLD.transaction_number, OLD.status
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_transactions_immutable
    BEFORE UPDATE ON payment_transactions
    FOR EACH ROW EXECUTE FUNCTION prevent_completed_txn_modification();

-- ---------------------------------------------------------------------------
-- TABLE : refunds
-- ---------------------------------------------------------------------------
CREATE TABLE refunds (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                      UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    refund_number           VARCHAR(30)     NOT NULL,   -- RMB-202604-0001
    order_id                UUID            REFERENCES orders(id) ON DELETE RESTRICT,
    invoice_id              UUID            REFERENCES invoices(id) ON DELETE RESTRICT,
    client_id               UUID            NOT NULL REFERENCES clients(id),
    original_transaction_id UUID            REFERENCES payment_transactions(id) ON DELETE RESTRICT,

    -- ── Status & Reason ───────────────────────────────────────────────────
    status                  refund_status   NOT NULL DEFAULT 'requested',
    reason                  refund_reason   NOT NULL,
    reason_detail           TEXT,

    -- ── Amounts ───────────────────────────────────────────────────────────
    requested_amount_cents  BIGINT          NOT NULL
                            CHECK (requested_amount_cents > 0),
    approved_amount_cents   BIGINT
                            CHECK (approved_amount_cents IS NULL OR approved_amount_cents > 0),
    refunded_amount_cents   BIGINT          NOT NULL DEFAULT 0
                            CHECK (refunded_amount_cents >= 0),
    currency                VARCHAR(3)      NOT NULL DEFAULT 'XAF',
    method                  payment_method, -- Méthode de remboursement

    -- ── Approval Workflow ─────────────────────────────────────────────────
    requested_by            UUID            NOT NULL REFERENCES users(id),
    reviewed_by             UUID            REFERENCES users(id),
    approved_by             UUID            REFERENCES users(id),

    -- ── Dates ─────────────────────────────────────────────────────────────
    requested_at            TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at             TIMESTAMPTZ,
    approved_at             TIMESTAMPTZ,
    rejected_at             TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,

    -- ── Rejection ─────────────────────────────────────────────────────────
    rejection_reason        TEXT,

    -- ── References ────────────────────────────────────────────────────────
    refund_transaction_id   UUID            REFERENCES payment_transactions(id),
    notes                   TEXT,
    metadata                JSONB           DEFAULT '{}'::JSONB,

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ── Constraints ───────────────────────────────────────────────────────
    CONSTRAINT refunds_number_unique        UNIQUE (refund_number),
    CONSTRAINT refunds_has_reference        CHECK (
        order_id IS NOT NULL OR invoice_id IS NOT NULL
    ),
    CONSTRAINT refunds_approved_not_exceed  CHECK (
        approved_amount_cents IS NULL OR
        approved_amount_cents <= requested_amount_cents
    ),
    CONSTRAINT refunds_workflow_dates       CHECK (
        (status = 'approved'   AND approved_at  IS NOT NULL) OR status != 'approved'
    ),
    CONSTRAINT refunds_rejected_has_reason  CHECK (
        (status = 'rejected'   AND rejection_reason IS NOT NULL) OR status != 'rejected'
    ),
    CONSTRAINT refunds_completed_has_txn    CHECK (
        (status = 'completed'  AND refund_transaction_id IS NOT NULL) OR status != 'completed'
    )
);

CREATE TRIGGER trg_refunds_updated_at
    BEFORE UPDATE ON refunds
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
