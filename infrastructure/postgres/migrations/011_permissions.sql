-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 011 : RBAC Granulaire (Permissions dynamiques)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TABLE : permissions (catalogue de toutes les permissions)
-- ---------------------------------------------------------------------------
CREATE TABLE permissions (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        VARCHAR(100) NOT NULL,   -- 'orders:create', 'refunds:approve'
    description TEXT,
    category    VARCHAR(50) NOT NULL DEFAULT 'general',
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT permissions_code_unique UNIQUE (code),
    CONSTRAINT permissions_code_format CHECK (code ~ '^[a-z_]+:[a-z_]+$')
);

-- ---------------------------------------------------------------------------
-- TABLE : role_permissions (mapping rôle → permissions)
-- ---------------------------------------------------------------------------
CREATE TABLE role_permissions (
    role             user_role   NOT NULL,
    permission_code  VARCHAR(100) NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
    granted_by       UUID        REFERENCES users(id) ON DELETE SET NULL,
    granted_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (role, permission_code)
);

-- ---------------------------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------------------------
CREATE INDEX idx_role_permissions_role
    ON role_permissions (role);

CREATE INDEX idx_permissions_category
    ON permissions (category)
    WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- SEED : Permissions catalogue
-- ---------------------------------------------------------------------------
INSERT INTO permissions (code, description, category) VALUES
    -- Clients
    ('clients:read',         'Consulter les clients',               'clients'),
    ('clients:create',       'Créer des clients',                   'clients'),
    ('clients:update',       'Modifier les clients',                'clients'),
    ('clients:delete',       'Supprimer des clients',               'clients'),

    -- Commandes
    ('orders:read',          'Consulter les commandes',             'orders'),
    ('orders:create',        'Créer des commandes',                 'orders'),
    ('orders:update',        'Modifier des commandes (draft)',      'orders'),
    ('orders:confirm',       'Confirmer des commandes',             'orders'),
    ('orders:cancel',        'Annuler des commandes',               'orders'),
    ('orders:delete',        'Supprimer des commandes',             'orders'),

    -- Produits
    ('products:read',        'Consulter le catalogue produits',     'products'),
    ('products:create',      'Créer des produits',                  'products'),
    ('products:update',      'Modifier des produits',               'products'),
    ('products:delete',      'Supprimer des produits',              'products'),

    -- Paiements
    ('payments:read',        'Consulter les paiements',             'payments'),
    ('payments:record',      'Enregistrer un paiement',             'payments'),

    -- Remboursements
    ('refunds:read',         'Consulter les remboursements',        'refunds'),
    ('refunds:request',      'Demander un remboursement',           'refunds'),
    ('refunds:approve',      'Approuver un remboursement',          'refunds'),
    ('refunds:reject',       'Rejeter un remboursement',            'refunds'),

    -- Documents / PDF
    ('documents:read',       'Consulter les documents',             'documents'),
    ('documents:generate',   'Générer des PDF',                     'documents'),
    ('documents:upload',     'Uploader des fichiers',               'documents'),
    ('documents:delete',     'Supprimer des documents',             'documents'),

    -- Utilisateurs
    ('users:read',           'Consulter les utilisateurs',          'users'),
    ('users:create',         'Créer des utilisateurs',              'users'),
    ('users:update',         'Modifier les utilisateurs',           'users'),
    ('users:delete',         'Désactiver des utilisateurs',         'users'),

    -- Permissions (admin système)
    ('permissions:read',     'Consulter les permissions',           'permissions'),
    ('permissions:manage',   'Gérer les permissions par rôle',      'permissions');

-- ---------------------------------------------------------------------------
-- SEED : Permissions par rôle (héritage cumulatif)
-- ---------------------------------------------------------------------------

-- super_admin : accès total
INSERT INTO role_permissions (role, permission_code)
SELECT 'super_admin', code FROM permissions;

-- admin : tout sauf permissions:manage
INSERT INTO role_permissions (role, permission_code)
SELECT 'admin', code FROM permissions
WHERE code != 'permissions:manage';

-- manager : opérations métier sans suppression ni gestion utilisateurs
INSERT INTO role_permissions (role, permission_code) VALUES
    ('manager', 'clients:read'),    ('manager', 'clients:create'),
    ('manager', 'clients:update'),

    ('manager', 'orders:read'),     ('manager', 'orders:create'),
    ('manager', 'orders:update'),   ('manager', 'orders:confirm'),
    ('manager', 'orders:cancel'),

    ('manager', 'products:read'),   ('manager', 'products:create'),
    ('manager', 'products:update'),

    ('manager', 'payments:read'),   ('manager', 'payments:record'),

    ('manager', 'refunds:read'),    ('manager', 'refunds:request'),
    ('manager', 'refunds:approve'), ('manager', 'refunds:reject'),

    ('manager', 'documents:read'),  ('manager', 'documents:generate'),
    ('manager', 'documents:upload'),

    ('manager', 'users:read');

-- operator : lecture + création de base
INSERT INTO role_permissions (role, permission_code) VALUES
    ('operator', 'clients:read'),

    ('operator', 'orders:read'),    ('operator', 'orders:create'),
    ('operator', 'orders:update'),

    ('operator', 'products:read'),

    ('operator', 'payments:read'),

    ('operator', 'refunds:read'),   ('operator', 'refunds:request'),

    ('operator', 'documents:read'), ('operator', 'documents:upload');
