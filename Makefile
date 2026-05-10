.PHONY: help dev dev-down prod prod-down build logs ps \
        migrate migrate-down db-shell backend-shell frontend-shell \
        certs clean reset

# ─────────────────────────────────────────────────────────────────────────────
#  Biloz — Makefile
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE_PROD = docker compose -f docker-compose.yml
COMPOSE_DEV  = docker compose -f docker-compose.dev.yml

help: ## Afficher cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Développement ───────────────────────────────────────────────────────────

dev: ## Démarrer l'environnement de développement (hot reload)
	@cp -n .env.example .env 2>/dev/null && echo ">> .env créé depuis .env.example" || true
	$(COMPOSE_DEV) up --build

dev-d: ## Démarrer en arrière-plan
	@cp -n .env.example .env 2>/dev/null || true
	$(COMPOSE_DEV) up --build -d

dev-down: ## Arrêter l'environnement de développement
	$(COMPOSE_DEV) down

# ─── Production ──────────────────────────────────────────────────────────────

prod: ## Démarrer en production
	@test -f .env || (echo "ERREUR: fichier .env manquant. Copier .env.example" && exit 1)
	$(COMPOSE_PROD) up --build -d

prod-down: ## Arrêter la production
	$(COMPOSE_PROD) down

build: ## Rebuilder les images sans cache
	$(COMPOSE_PROD) build --no-cache

# ─── Migrations Alembic ───────────────────────────────────────────────────────

migrate: ## Appliquer les migrations (alembic upgrade head)
	$(COMPOSE_DEV) exec backend alembic upgrade head

migrate-create: ## Créer une migration (MSG="description")
	$(COMPOSE_DEV) exec backend alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback d'une migration
	$(COMPOSE_DEV) exec backend alembic downgrade -1

# ─── Shells ──────────────────────────────────────────────────────────────────

db-shell: ## Ouvrir psql dans le conteneur PostgreSQL
	$(COMPOSE_DEV) exec postgres psql -U $${POSTGRES_USER:-biloz_admin} -d $${POSTGRES_DB:-biloz}

backend-shell: ## Ouvrir un shell dans le backend
	$(COMPOSE_DEV) exec backend bash

frontend-shell: ## Ouvrir un shell dans le frontend
	$(COMPOSE_DEV) exec frontend sh

# ─── Logs & status ───────────────────────────────────────────────────────────

logs: ## Suivre les logs (tous les services)
	$(COMPOSE_DEV) logs -f

logs-backend: ## Suivre les logs du backend
	$(COMPOSE_DEV) logs -f backend

logs-frontend: ## Suivre les logs du frontend
	$(COMPOSE_DEV) logs -f frontend

ps: ## État des conteneurs
	$(COMPOSE_DEV) ps

# ─── SSL (production) ────────────────────────────────────────────────────────

certs: ## Générer des certificats auto-signés pour le dev HTTPS
	@bash scripts/gen-certs.sh

# ─── Nettoyage ───────────────────────────────────────────────────────────────

clean: ## Supprimer les conteneurs et images orphelins
	$(COMPOSE_DEV) down --remove-orphans
	docker image prune -f

reset: ## DANGER : supprimer conteneurs + volumes (perte de données !)
	@echo "ATTENTION : Cette commande supprime toutes les données !"
	@read -p "Continuer ? [y/N] " ans && [ "$$ans" = "y" ]
	$(COMPOSE_DEV) down -v --remove-orphans
