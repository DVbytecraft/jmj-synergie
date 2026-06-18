-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 010 : Catalogue produits / services
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TYPE : product_status
-- ---------------------------------------------------------------------------
CREATE TYPE product_status AS ENUM (
    'active',       -- En vente
    'inactive',     -- Temporairement indisponible
    'discontinued', -- Arrêté définitivement
    'draft'         -- Brouillon non publié
);

-- ---------------------------------------------------------------------------
-- TABLE : products (catalogue centralisé)
-- ---------------------------------------------------------------------------
CREATE TABLE products (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    code                VARCHAR(50)     NOT NULL,       -- REF-00001
    name                VARCHAR(255)    NOT NULL,
    description         TEXT,
    short_description   VARCHAR(500),

    -- ── Classification ────────────────────────────────────────────────────
    category            VARCHAR(100),
    sub_category        VARCHAR(100),
    tags                TEXT[]          DEFAULT '{}',

    -- ── Mesure ────────────────────────────────────────────────────────────
    unit                VARCHAR(20),    -- kg, m², pièce, heure, litre...
    weight_grams        INTEGER         CHECK (weight_grams IS NULL OR weight_grams >= 0),
    dimensions_cm       JSONB,          -- {"l": 10, "w": 5, "h": 3}

    -- ── Tarification ─────────────────────────────────────────────────────
    unit_price_cents    BIGINT          NOT NULL DEFAULT 0
                        CHECK (unit_price_cents >= 0),
    currency            VARCHAR(3)      NOT NULL DEFAULT 'XAF'
                        CHECK (currency ~ '^[A-Z]{3}$'),
    tax_rate            NUMERIC(5,2)    NOT NULL DEFAULT 0.00
                        CHECK (tax_rate BETWEEN 0 AND 100),
    min_order_quantity  NUMERIC(14,4)   NOT NULL DEFAULT 1
                        CHECK (min_order_quantity > 0),

    -- ── Stock (optionnel si suivi d'inventaire) ───────────────────────────
    track_stock         BOOLEAN         NOT NULL DEFAULT FALSE,
    stock_quantity      NUMERIC(14,4)   DEFAULT 0
                        CHECK (stock_quantity IS NULL OR stock_quantity >= 0),
    low_stock_threshold NUMERIC(14,4),

    -- ── Images ────────────────────────────────────────────────────────────
    image_path          VARCHAR(500),

    -- ── Status ────────────────────────────────────────────────────────────
    status              product_status  NOT NULL DEFAULT 'active',

    -- ── Meta ──────────────────────────────────────────────────────────────
    notes               TEXT,
    metadata            JSONB           DEFAULT '{}'::JSONB,
    supplier_ref        VARCHAR(100),   -- Référence fournisseur
    barcode             VARCHAR(60),

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Audit ─────────────────────────────────────────────────────────────
    created_by          UUID            NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- ── Constraints ───────────────────────────────────────────────────────
    CONSTRAINT products_code_unique     UNIQUE (code),
    CONSTRAINT products_barcode_unique  UNIQUE (barcode)
);

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : product_price_tiers (tarifs dégressifs par quantité)
-- ---------------------------------------------------------------------------
CREATE TABLE product_price_tiers (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id      UUID        NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    min_quantity    NUMERIC(14,4) NOT NULL CHECK (min_quantity > 0),
    max_quantity    NUMERIC(14,4),          -- NULL = illimité
    unit_price_cents BIGINT     NOT NULL CHECK (unit_price_cents >= 0),
    currency        VARCHAR(3)  NOT NULL DEFAULT 'XAF',
    label           VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT price_tiers_range_valid CHECK (
        max_quantity IS NULL OR max_quantity > min_quantity
    )
);

-- ---------------------------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX idx_products_code_active
    ON products (code)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_products_name_trgm
    ON products USING GIN (name gin_trgm_ops)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_products_category
    ON products (category, status)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_products_status
    ON products (status)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_products_tags
    ON products USING GIN (tags)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_price_tiers_product
    ON product_price_tiers (product_id, min_quantity);

-- ---------------------------------------------------------------------------
-- AUDIT trigger
-- ---------------------------------------------------------------------------
CREATE TRIGGER audit_products
    AFTER INSERT OR UPDATE OR DELETE ON products
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
