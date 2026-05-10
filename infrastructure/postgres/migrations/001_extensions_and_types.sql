-- =============================================================================
--  JMJ SYNERGIE — PostgreSQL Schema
--  Migration 001 : Extensions & Custom Types
--  Author  : Architecture Expert
--  Date    : 2026-04-11
--  Version : 1.0.0
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. EXTENSIONS
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- Trigram search (ILIKE fast)
CREATE EXTENSION IF NOT EXISTS "btree_gist";     -- Exclusion constraints
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_bytes, crypt
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- Accent-insensitive search

-- ---------------------------------------------------------------------------
-- 2. SCHEMA ISOLATION
-- ---------------------------------------------------------------------------
-- Application data (default public)
-- Audit data in its own schema
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS reporting;

-- ---------------------------------------------------------------------------
-- 3. ENUM TYPES
-- ---------------------------------------------------------------------------

-- ── Users ──────────────────────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM (
    'super_admin',   -- Accès total, peut supprimer des données
    'admin',         -- Gestion complète sans suppression physique
    'manager',       -- Création + validation commandes, remboursements
    'operator'       -- Lecture + création commandes seulement
);

CREATE TYPE user_status AS ENUM (
    'active',
    'inactive',
    'suspended',
    'pending_verification'
);

-- ── Clients ────────────────────────────────────────────────────────────────
CREATE TYPE client_type AS ENUM (
    'individual',    -- Particulier
    'company',       -- Entreprise
    'government',    -- Organisme public
    'ngo'            -- ONG / Association
);

CREATE TYPE client_status AS ENUM (
    'active',
    'inactive',
    'blacklisted'
);

-- ── Orders ─────────────────────────────────────────────────────────────────
CREATE TYPE order_status AS ENUM (
    'draft',          -- Brouillon, modifiable
    'confirmed',      -- Validée par un manager
    'in_production',  -- En cours de traitement
    'ready',          -- Prête à livrer
    'delivered',      -- Livrée au client
    'disputed',       -- Litige en cours
    'cancelled',      -- Annulée
    'archived'        -- Archivée (lecture seule)
);

-- ── Documents ──────────────────────────────────────────────────────────────
CREATE TYPE document_type AS ENUM (
    'pro_forma',      -- Facture pro forma (avant commande)
    'invoice',        -- Facture définitive
    'receipt',        -- Reçu de paiement
    'credit_note',    -- Note de crédit (remboursement)
    'delivery_note',  -- Bon de livraison
    'scanned'         -- Document scanné (OCR)
);

CREATE TYPE document_status AS ENUM (
    'draft',
    'issued',         -- Émis
    'sent',           -- Envoyé au client
    'acknowledged',   -- Accusé de réception
    'disputed',
    'cancelled',
    'archived'
);

-- ── Payments ───────────────────────────────────────────────────────────────
CREATE TYPE payment_status AS ENUM (
    'pending',        -- En attente
    'partial',        -- Paiement partiel reçu
    'paid',           -- Intégralement payé
    'overdue',        -- Dépassé l'échéance
    'refunded',       -- Intégralement remboursé
    'partial_refund'  -- Partiellement remboursé
);

CREATE TYPE payment_method AS ENUM (
    'cash',
    'bank_transfer',
    'mobile_money',   -- Orange Money, MTN, etc.
    'check',
    'card',
    'crypto',
    'barter'
);

-- ── Transactions ───────────────────────────────────────────────────────────
CREATE TYPE transaction_type AS ENUM (
    'payment',
    'refund',
    'adjustment',     -- Correction manuelle
    'chargeback'      -- Contestation bancaire
);

CREATE TYPE transaction_status AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed',
    'reversed'
);

-- ── Invoices ───────────────────────────────────────────────────────────────
CREATE TYPE invoice_status AS ENUM (
    'draft',
    'issued',
    'sent',
    'partially_paid',
    'paid',
    'overdue',
    'disputed',
    'cancelled',
    'written_off'     -- Créance irrécouvrable
);

-- ── Refunds ────────────────────────────────────────────────────────────────
CREATE TYPE refund_status AS ENUM (
    'requested',      -- Demande reçue
    'under_review',   -- En cours d'examen
    'approved',       -- Approuvée
    'rejected',       -- Refusée
    'processing',     -- En cours de traitement
    'completed',      -- Remboursement effectué
    'cancelled'
);

CREATE TYPE refund_reason AS ENUM (
    'product_defect',
    'wrong_item',
    'not_delivered',
    'customer_request',
    'duplicate_payment',
    'billing_error',
    'service_failure',
    'other'
);
