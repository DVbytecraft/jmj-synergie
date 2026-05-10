-- =============================================================================
--  JMJ SYNERGIE — Test Data (développement uniquement)
--  NE PAS EXÉCUTER EN PRODUCTION
-- =============================================================================

-- Admin utilisateur (mot de passe : Admin@2026! — bcrypt 12 rounds)
INSERT INTO users (id, email, hashed_password, full_name, role, status, is_email_verified)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin@jmjsynergie.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBIkZGYlhNM5bK',  -- À régénérer
    'Super Administrateur',
    'super_admin',
    'active',
    TRUE
) ON CONFLICT DO NOTHING;

-- Client exemple - Entreprise
INSERT INTO clients (
    id, code, client_type, full_name, company_name, tax_id,
    email, phone, city, country, currency,
    created_by, credit_limit_cents, payment_terms_days
) VALUES (
    '00000000-0000-0000-0000-000000000010',
    'CLT-00001',
    'company',
    'Jean-Marie Mballa',
    'Mballa & Associés SARL',
    'P012345678A',
    'jm.mballa@mballa-sarl.cm',
    '+237 690 000 001',
    'Yaoundé',
    'CM',
    'XAF',
    '00000000-0000-0000-0000-000000000001',
    50000000,  -- 500 000 XAF
    30
) ON CONFLICT DO NOTHING;

-- Client exemple - Particulier
INSERT INTO clients (
    id, code, client_type, full_name,
    email, phone, city, country, currency, created_by
) VALUES (
    '00000000-0000-0000-0000-000000000011',
    'CLT-00002',
    'individual',
    'Marie Fomo Nguetsop',
    'marie.fomo@gmail.com',
    '+237 677 000 002',
    'Douala',
    'CM',
    'XAF',
    '00000000-0000-0000-0000-000000000001'
) ON CONFLICT DO NOTHING;

-- Commande exemple
INSERT INTO orders (
    id, order_number, client_id, status, payment_status,
    currency, subtotal_cents, tax_rate, tax_cents,
    total_cents, created_by
) VALUES (
    '00000000-0000-0000-0000-000000000100',
    'CMD-202604-0001',
    '00000000-0000-0000-0000-000000000010',
    'confirmed',
    'partial',
    'XAF',
    1000000,   -- 10 000 XAF
    19.25,
    192500,    -- TVA 19.25%
    1192500,   -- Total = 11 925 XAF
    '00000000-0000-0000-0000-000000000001'
) ON CONFLICT DO NOTHING;

-- Lignes de commande
INSERT INTO order_items (
    order_id, sort_order, description, unit, quantity,
    unit_price_cents, line_total_cents
) VALUES
    ('00000000-0000-0000-0000-000000000100', 1,
     'Prestation de conseil en stratégie', 'heure', 5.0000, 150000, 750000),
    ('00000000-0000-0000-0000-000000000100', 2,
     'Rapport d''analyse détaillé',         'pièce', 1.0000, 250000, 250000)
ON CONFLICT DO NOTHING;

-- Transaction de paiement partiel
INSERT INTO payment_transactions (
    id, transaction_number, order_id, client_id,
    transaction_type, status, method,
    amount_cents, amount_base_cents, currency,
    recorded_by, transaction_date
) VALUES (
    '00000000-0000-0000-0000-000000000200',
    'TXN-20260411-00000001',
    '00000000-0000-0000-0000-000000000100',
    '00000000-0000-0000-0000-000000000010',
    'payment',
    'completed',
    'mobile_money',
    500000,   -- Paiement partiel : 5 000 XAF
    500000,
    'XAF',
    '00000000-0000-0000-0000-000000000001',
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;
