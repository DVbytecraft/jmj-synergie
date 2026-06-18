#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  gen-certs.sh — Génère un certificat SSL auto-signé pour le développement
#  Usage : bash scripts/gen-certs.sh [domaine]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DOMAIN="${1:-localhost}"
SSL_DIR="infrastructure/nginx/ssl"

mkdir -p "$SSL_DIR"

echo ">> Génération du certificat auto-signé pour : $DOMAIN"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$SSL_DIR/privkey.pem" \
  -out    "$SSL_DIR/fullchain.pem" \
  -subj   "/C=FR/ST=IleDeFrance/L=Paris/O=JMJ Synergie/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:www.$DOMAIN,IP:127.0.0.1"

chmod 600 "$SSL_DIR/privkey.pem"
chmod 644 "$SSL_DIR/fullchain.pem"

echo ""
echo "Certificats générés dans $SSL_DIR/"
echo "  - fullchain.pem  (certificat public)"
echo "  - privkey.pem    (clé privée)"
echo ""
echo "ATTENTION : Certificat auto-signé, à utiliser uniquement en développement."
echo "En production, utiliser Let's Encrypt (certbot) ou un certificat signé par une CA."
