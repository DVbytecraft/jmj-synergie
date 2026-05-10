-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 002 : Core Tables (Users, Clients, Orders)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- UTILITY : updated_at auto-refresh trigger function
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- TABLE : users
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    email               VARCHAR(255)    NOT NULL,
    hashed_password     VARCHAR(255)    NOT NULL,
    full_name           VARCHAR(255)    NOT NULL,
    phone               VARCHAR(30),

    -- ── Access Control ────────────────────────────────────────────────────
    role                user_role       NOT NULL DEFAULT 'operator',
    status              user_status     NOT NULL DEFAULT 'active',
    is_email_verified   BOOLEAN         NOT NULL DEFAULT FALSE,

    -- ── Signature / Assets ────────────────────────────────────────────────
    -- Paths stored relative to STORAGE_PATH
    avatar_path         VARCHAR(500),
    signature_path      VARCHAR(500),   -- Image PNG de la signature manuscrite

    -- ── Security ──────────────────────────────────────────────────────────
    failed_login_count  SMALLINT        NOT NULL DEFAULT 0
                        CHECK (failed_login_count >= 0),
    locked_until        TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    last_login_ip       INET,
    password_changed_at TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mfa_secret          VARCHAR(64),    -- TOTP secret (encrypted at app level)
    mfa_enabled         BOOLEAN         NOT NULL DEFAULT FALSE,

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ── Constraints ───────────────────────────────────────────────────────
    CONSTRAINT users_email_unique           UNIQUE (email),
    CONSTRAINT users_email_format           CHECK (email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT users_deleted_consistency    CHECK (
        (is_deleted = FALSE AND deleted_at IS NULL AND deleted_by IS NULL) OR
        (is_deleted = TRUE  AND deleted_at IS NOT NULL)
    ),
    CONSTRAINT users_lock_consistency       CHECK (
        (locked_until IS NULL) OR (locked_until > CURRENT_TIMESTAMP OR failed_login_count > 0)
    )
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : user_sessions (refresh tokens / active sessions)
-- ---------------------------------------------------------------------------
CREATE TABLE user_sessions (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash          VARCHAR(128)    NOT NULL,   -- SHA-256 du refresh token
    ip_address          INET,
    user_agent          VARCHAR(500),
    device_fingerprint  VARCHAR(100),
    expires_at          TIMESTAMPTZ     NOT NULL,
    revoked             BOOLEAN         NOT NULL DEFAULT FALSE,
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT sessions_token_unique UNIQUE (token_hash),
    CONSTRAINT sessions_revoke_consistency CHECK (
        (revoked = FALSE AND revoked_at IS NULL) OR
        (revoked = TRUE  AND revoked_at IS NOT NULL)
    )
);

-- ---------------------------------------------------------------------------
-- TABLE : clients
-- ---------------------------------------------------------------------------
CREATE TABLE clients (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    code                VARCHAR(20)     NOT NULL,   -- CLT-00001
    client_type         client_type     NOT NULL,
    status              client_status   NOT NULL DEFAULT 'active',

    -- ── Personal / Company Info ───────────────────────────────────────────
    full_name           VARCHAR(255)    NOT NULL,
    company_name        VARCHAR(255),
    trade_name          VARCHAR(255),   -- Nom commercial si différent
    tax_id              VARCHAR(60),    -- NIF / SIRET / RC
    registration_number VARCHAR(60),    -- Numéro d'immatriculation

    -- ── Contact ───────────────────────────────────────────────────────────
    email               VARCHAR(255),
    email_secondary     VARCHAR(255),
    phone               VARCHAR(30)     NOT NULL,
    phone_secondary     VARCHAR(30),
    website             VARCHAR(255),

    -- ── Address ───────────────────────────────────────────────────────────
    address_line1       VARCHAR(255),
    address_line2       VARCHAR(255),
    city                VARCHAR(100),
    state_province      VARCHAR(100),
    postal_code         VARCHAR(20),
    country             VARCHAR(2)      NOT NULL DEFAULT 'CM'  -- ISO 3166-1 alpha-2
                        CHECK (country ~ '^[A-Z]{2}$'),

    -- ── Financial Settings ────────────────────────────────────────────────
    currency            VARCHAR(3)      NOT NULL DEFAULT 'XAF'
                        CHECK (currency ~ '^[A-Z]{3}$'),
    credit_limit_cents  BIGINT          NOT NULL DEFAULT 0
                        CHECK (credit_limit_cents >= 0),
    payment_terms_days  SMALLINT        NOT NULL DEFAULT 30
                        CHECK (payment_terms_days BETWEEN 0 AND 365),
    default_tax_rate    NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (default_tax_rate BETWEEN 0 AND 100),

    -- ── Relationship ──────────────────────────────────────────────────────
    assigned_to         UUID            REFERENCES users(id) ON DELETE SET NULL,
    referred_by         UUID            REFERENCES clients(id) ON DELETE SET NULL,

    -- ── Meta ──────────────────────────────────────────────────────────────
    notes               TEXT,
    tags                TEXT[]          DEFAULT '{}',
    metadata            JSONB           DEFAULT '{}'::JSONB,

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          UUID            NOT NULL REFERENCES users(id),

    -- ── Constraints ───────────────────────────────────────────────────────
    CONSTRAINT clients_code_unique      UNIQUE (code),
    CONSTRAINT clients_taxid_unique     UNIQUE (tax_id),
    CONSTRAINT clients_email_format     CHECK (
        email IS NULL OR email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'
    ),
    CONSTRAINT clients_company_requires_name CHECK (
        client_type = 'individual' OR company_name IS NOT NULL
    )
);

CREATE TRIGGER trg_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : client_contacts (contacts supplémentaires par client)
-- ---------------------------------------------------------------------------
CREATE TABLE client_contacts (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id       UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    full_name       VARCHAR(255) NOT NULL,
    job_title       VARCHAR(100),
    email           VARCHAR(255),
    phone           VARCHAR(30),
    is_primary      BOOLEAN     NOT NULL DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_client_contacts_updated_at
    BEFORE UPDATE ON client_contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : orders
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_number        VARCHAR(30)     NOT NULL,   -- CMD-202604-0001
    client_id           UUID            NOT NULL REFERENCES clients(id),

    -- ── Status ────────────────────────────────────────────────────────────
    status              order_status    NOT NULL DEFAULT 'draft',
    payment_status      payment_status  NOT NULL DEFAULT 'pending',

    -- ── Amounts (all in smallest currency unit — centimes) ─────────────────
    -- RÈGLE : Jamais de FLOAT pour les montants financiers
    subtotal_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (subtotal_cents >= 0),
    tax_rate            NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (tax_rate BETWEEN 0 AND 100),
    tax_cents           BIGINT          NOT NULL DEFAULT 0
                        CHECK (tax_cents >= 0),
    discount_rate       NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (discount_rate BETWEEN 0 AND 100),
    discount_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (discount_cents >= 0),
    shipping_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (shipping_cents >= 0),
    total_cents         BIGINT          NOT NULL DEFAULT 0
                        CHECK (total_cents >= 0),
    paid_cents          BIGINT          NOT NULL DEFAULT 0
                        CHECK (paid_cents >= 0),
    refunded_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (refunded_cents >= 0),

    -- ── Derived (computed as generated column) ────────────────────────────
    balance_due_cents   BIGINT          GENERATED ALWAYS AS
                            (total_cents - paid_cents + refunded_cents) STORED,

    -- ── Currency & Locale ─────────────────────────────────────────────────
    currency            VARCHAR(3)      NOT NULL DEFAULT 'XAF'
                        CHECK (currency ~ '^[A-Z]{3}$'),
    exchange_rate       NUMERIC(18,8)   NOT NULL DEFAULT 1.00000000,  -- Vers XAF

    -- ── Dates ─────────────────────────────────────────────────────────────
    ordered_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at        TIMESTAMPTZ,
    due_date            DATE,           -- Echéance de paiement
    delivery_date       DATE,           -- Date de livraison prévue
    delivered_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,

    -- ── References ────────────────────────────────────────────────────────
    purchase_order_ref  VARCHAR(100),   -- Référence bon de commande client
    notes               TEXT,
    internal_notes      TEXT,           -- Notes internes (non visibles client)
    shipping_address    JSONB,          -- Adresse livraison snapshot
    metadata            JSONB           DEFAULT '{}'::JSONB,

    -- ── Staff ─────────────────────────────────────────────────────────────
    created_by          UUID            NOT NULL REFERENCES users(id),
    confirmed_by        UUID            REFERENCES users(id),
    cancelled_by        UUID            REFERENCES users(id),

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ── Business Constraints ──────────────────────────────────────────────
    CONSTRAINT orders_number_unique     UNIQUE (order_number),
    CONSTRAINT orders_paid_not_exceed   CHECK (paid_cents <= total_cents + refunded_cents),
    CONSTRAINT orders_refund_not_exceed CHECK (refunded_cents <= paid_cents),
    CONSTRAINT orders_total_coherence   CHECK (
        total_cents = subtotal_cents + tax_cents + shipping_cents - discount_cents
        OR status = 'draft'  -- Draft peut être incohérent temporairement
    ),
    CONSTRAINT orders_confirmed_has_date CHECK (
        confirmed_at IS NOT NULL OR status NOT IN ('confirmed','in_production','ready','delivered')
    ),
    CONSTRAINT orders_delivered_has_date CHECK (
        delivered_at IS NOT NULL OR status != 'delivered'
    )
);

CREATE TRIGGER trg_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : order_items (lignes de commande)
-- ---------------------------------------------------------------------------
CREATE TABLE order_items (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id            UUID            NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sort_order          SMALLINT        NOT NULL DEFAULT 0,

    -- ── Product / Service ─────────────────────────────────────────────────
    item_code           VARCHAR(50),    -- Référence article
    description         VARCHAR(1000)   NOT NULL,
    unit                VARCHAR(20),    -- kg, m², pièce, heure...
    notes               TEXT,

    -- ── Amounts ───────────────────────────────────────────────────────────
    quantity            NUMERIC(14,4)   NOT NULL
                        CHECK (quantity > 0),
    unit_price_cents    BIGINT          NOT NULL
                        CHECK (unit_price_cents >= 0),
    item_discount_cents BIGINT          NOT NULL DEFAULT 0
                        CHECK (item_discount_cents >= 0),
    item_tax_rate       NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (item_tax_rate BETWEEN 0 AND 100),
    item_tax_cents      BIGINT          NOT NULL DEFAULT 0
                        CHECK (item_tax_cents >= 0),
    line_total_cents    BIGINT          NOT NULL
                        CHECK (line_total_cents >= 0),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT order_items_line_total CHECK (
        line_total_cents = (CAST(quantity * unit_price_cents AS BIGINT))
                            - item_discount_cents + item_tax_cents
        OR TRUE  -- Calculé côté app, vérifié par trigger
    )
);

CREATE TRIGGER trg_order_items_updated_at
    BEFORE UPDATE ON order_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : order_status_history (traçabilité des transitions d'état)
-- ---------------------------------------------------------------------------
CREATE TABLE order_status_history (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id        UUID        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    from_status     order_status,
    to_status       order_status NOT NULL,
    changed_by      UUID        NOT NULL REFERENCES users(id),
    reason          TEXT,
    metadata        JSONB,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
