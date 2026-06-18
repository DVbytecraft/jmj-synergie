-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 004 : Documents & Audit Trail
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TABLE : documents (fichiers générés ou scannés)
-- ---------------------------------------------------------------------------
CREATE TABLE documents (
    -- ── Identity ──────────────────────────────────────────────────────────
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_number     VARCHAR(40)     NOT NULL,   -- DOC-20260411-XXXX
    document_type       document_type   NOT NULL,
    status              document_status NOT NULL DEFAULT 'draft',

    -- ── Relations polymorphes ─────────────────────────────────────────────
    order_id            UUID            REFERENCES orders(id)      ON DELETE SET NULL,
    invoice_id          UUID            REFERENCES invoices(id)    ON DELETE SET NULL,
    pro_forma_id        UUID            REFERENCES pro_formas(id)  ON DELETE SET NULL,
    client_id           UUID            REFERENCES clients(id)     ON DELETE SET NULL,

    -- ── File Info ─────────────────────────────────────────────────────────
    file_name           VARCHAR(255)    NOT NULL,
    file_path           VARCHAR(500)    NOT NULL,
    file_size_bytes     BIGINT          NOT NULL CHECK (file_size_bytes > 0),
    mime_type           VARCHAR(100)    NOT NULL,
    checksum_sha256     CHAR(64),       -- Intégrité du fichier

    -- ── Signature ─────────────────────────────────────────────────────────
    is_signed           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_stamped          BOOLEAN         NOT NULL DEFAULT FALSE,
    signed_at           TIMESTAMPTZ,
    stamped_at          TIMESTAMPTZ,
    signed_by           UUID            REFERENCES users(id),

    -- ── Version (pour les documents modifiés) ─────────────────────────────
    version             SMALLINT        NOT NULL DEFAULT 1
                        CHECK (version >= 1),
    parent_document_id  UUID            REFERENCES documents(id),  -- Version précédente
    is_latest           BOOLEAN         NOT NULL DEFAULT TRUE,

    -- ── OCR (pour les scans) ──────────────────────────────────────────────
    ocr_data            JSONB,          -- Données extraites
    ocr_confidence      NUMERIC(4,2)    CHECK (ocr_confidence BETWEEN 0 AND 1),
    ocr_processed_at    TIMESTAMPTZ,

    -- ── Expiration (pro forma) ────────────────────────────────────────────
    expires_at          DATE,

    -- ── Metadata ──────────────────────────────────────────────────────────
    notes               TEXT,
    metadata            JSONB           DEFAULT '{}'::JSONB,
    tags                TEXT[]          DEFAULT '{}',

    -- ── Staff ─────────────────────────────────────────────────────────────
    created_by          UUID            NOT NULL REFERENCES users(id),

    -- ── Soft Delete ───────────────────────────────────────────────────────
    is_deleted          BOOLEAN         NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID            REFERENCES users(id),

    -- ── Timestamps ────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT documents_number_unique      UNIQUE (document_number),
    CONSTRAINT documents_sign_consistency   CHECK (
        (is_signed = TRUE  AND signed_at IS NOT NULL AND signed_by IS NOT NULL) OR
        (is_signed = FALSE AND signed_at IS NULL)
    ),
    CONSTRAINT documents_stamp_consistency  CHECK (
        (is_stamped = TRUE  AND stamped_at IS NOT NULL) OR
        (is_stamped = FALSE AND stamped_at IS NULL)
    )
);

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TABLE : document_access_log (qui a consulté/téléchargé un document)
-- ---------------------------------------------------------------------------
CREATE TABLE document_access_log (
    id              BIGSERIAL   PRIMARY KEY,
    document_id     UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    accessed_by     UUID        REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(20) NOT NULL CHECK (action IN ('view','download','email')),
    ip_address      INET,
    user_agent      VARCHAR(300),
    accessed_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (accessed_at);

-- Partitions par trimestre (gérer la croissance du log)
CREATE TABLE document_access_log_2026_q1
    PARTITION OF document_access_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE document_access_log_2026_q2
    PARTITION OF document_access_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE TABLE document_access_log_2026_q3
    PARTITION OF document_access_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

CREATE TABLE document_access_log_2026_q4
    PARTITION OF document_access_log
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

CREATE TABLE document_access_log_default
    PARTITION OF document_access_log DEFAULT;

-- ---------------------------------------------------------------------------
-- SCHEMA audit : Journal d'audit complet de toutes les mutations
-- ---------------------------------------------------------------------------
CREATE TABLE audit.audit_logs (
    id              BIGSERIAL       PRIMARY KEY,
    -- Qui
    user_id         UUID,
    user_email      VARCHAR(255),
    user_role       VARCHAR(30),
    session_id      UUID,
    -- Depuis où
    ip_address      INET,
    user_agent      TEXT,
    request_id      UUID,
    -- Quoi
    action          VARCHAR(50)     NOT NULL,   -- INSERT, UPDATE, DELETE, LOGIN...
    entity_type     VARCHAR(100)    NOT NULL,   -- 'order', 'payment', etc.
    entity_id       TEXT,
    -- Changements
    old_values      JSONB,          -- Valeurs avant modification
    new_values      JSONB,          -- Valeurs après modification
    changed_fields  TEXT[],        -- Liste des champs modifiés
    -- Contexte
    description     TEXT,
    metadata        JSONB,
    severity        VARCHAR(10)     NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('debug','info','warning','error','critical')),
    -- Quand
    occurred_at     TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (occurred_at);

-- Partitions mensuelles pour l'audit (volume élevé)
CREATE TABLE audit.audit_logs_2026_04
    PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE audit.audit_logs_2026_05
    PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE audit.audit_logs_2026_06
    PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE audit.audit_logs_default
    PARTITION OF audit.audit_logs DEFAULT;

-- ---------------------------------------------------------------------------
-- TABLE : notifications
-- ---------------------------------------------------------------------------
CREATE TABLE notifications (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    client_id       UUID        REFERENCES clients(id) ON DELETE CASCADE,

    -- Au moins une cible
    CONSTRAINT notif_has_target CHECK (
        user_id IS NOT NULL OR client_id IS NOT NULL
    ),

    channel         VARCHAR(20) NOT NULL DEFAULT 'in_app'
                    CHECK (channel IN ('in_app','email','sms','push')),
    type            VARCHAR(50) NOT NULL,
    subject         VARCHAR(255),
    body            TEXT        NOT NULL,
    data            JSONB       DEFAULT '{}'::JSONB,

    is_read         BOOLEAN     NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    failure_reason  TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- TABLE : settings (configuration applicative persistée)
-- ---------------------------------------------------------------------------
CREATE TABLE app_settings (
    key             VARCHAR(100)    PRIMARY KEY,
    value           JSONB           NOT NULL,
    description     TEXT,
    is_encrypted    BOOLEAN         NOT NULL DEFAULT FALSE,
    category        VARCHAR(50)     NOT NULL DEFAULT 'general',
    updated_by      UUID            REFERENCES users(id),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_settings_updated_at
    BEFORE UPDATE ON app_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Valeurs par défaut
INSERT INTO app_settings (key, value, description, category) VALUES
    ('company.name',          '"JMJ Synergie"',  'Raison sociale',          'company'),
    ('company.address',       '""',              'Adresse principale',       'company'),
    ('company.phone',         '""',              'Téléphone',               'company'),
    ('company.email',         '""',              'Email de contact',        'company'),
    ('company.tax_id',        '""',              'NIF / numéro fiscal',     'company'),
    ('invoice.prefix',        '"FACT"',          'Préfixe numérotation',    'invoice'),
    ('invoice.next_number',   '1',               'Prochain numéro',         'invoice'),
    ('order.prefix',          '"CMD"',           'Préfixe commande',        'order'),
    ('order.next_number',     '1',               'Prochain numéro',         'order'),
    ('payment.currency',      '"XAF"',           'Devise par défaut',       'payment'),
    ('payment.tax_rate',      '19.25',           'TVA par défaut (%)',      'payment'),
    ('payment.terms_days',    '30',              'Délai paiement (jours)',  'payment')
ON CONFLICT (key) DO NOTHING;
