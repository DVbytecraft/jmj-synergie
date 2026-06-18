"""
Domain exceptions hierarchy.
Each exception maps to a specific HTTP status in the API layer —
never leak infrastructure errors to clients.
"""
from __future__ import annotations
from typing import Any


class AppException(Exception):
    """Root application exception."""
    default_message: str = "Une erreur inattendue s'est produite"
    default_code: str = "APP_ERROR"

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.context = context or {}
        super().__init__(self.message)


# ── 404 Not Found ─────────────────────────────────────────────────────────────

class EntityNotFoundError(AppException):
    """Requested entity does not exist (or is soft-deleted)."""
    default_code = "NOT_FOUND"

    def __init__(self, entity: str, identifier: Any) -> None:
        super().__init__(
            message=f"{entity} introuvable : {identifier}",
            context={"entity": entity, "id": str(identifier)},
        )
        self.entity = entity
        self.identifier = identifier


# ── 409 Conflict ─────────────────────────────────────────────────────────────

class DuplicateEntityError(AppException):
    default_code = "DUPLICATE"

    def __init__(self, entity: str, field: str, value: Any) -> None:
        super().__init__(
            message=f"{entity} avec {field}='{value}' existe déjà",
            context={"entity": entity, "field": field, "value": str(value)},
        )


# ── 422 Business Rule Violations ──────────────────────────────────────────────

class BusinessRuleError(AppException):
    """Violated a domain invariant."""
    default_code = "BUSINESS_RULE"


class InvalidOrderStateError(BusinessRuleError):
    default_code = "INVALID_ORDER_STATE"

    def __init__(self, current: str, required: str | list[str]) -> None:
        allowed = required if isinstance(required, list) else [required]
        super().__init__(
            message=f"Commande en état '{current}', état requis : {allowed}",
            context={"current": current, "required": allowed},
        )


class InvalidRefundError(BusinessRuleError):
    default_code = "INVALID_REFUND"


class InsufficientPaymentError(BusinessRuleError):
    default_code = "INSUFFICIENT_PAYMENT"

    def __init__(self, paid: int, required: int) -> None:
        super().__init__(
            message=f"Montant insuffisant : payé={paid}, requis={required}",
            context={"paid_cents": paid, "required_cents": required},
        )


class OrderAlreadyPaidError(BusinessRuleError):
    default_code = "ALREADY_PAID"


class RefundExceedsPaidError(BusinessRuleError):
    default_code = "REFUND_EXCEEDS_PAID"

    def __init__(self, refund: int, paid: int) -> None:
        super().__init__(
            message=f"Remboursement ({refund}) dépasse le montant payé ({paid})",
            context={"refund_cents": refund, "paid_cents": paid},
        )


# ── 403 Permission ────────────────────────────────────────────────────────────

class PermissionDeniedError(AppException):
    default_code = "PERMISSION_DENIED"
    default_message = "Action non autorisée pour ce rôle"


class AuthenticationError(AppException):
    default_code = "AUTH_FAILED"
    default_message = "Authentification échouée"


class AccountLockedError(AuthenticationError):
    default_code = "ACCOUNT_LOCKED"

    def __init__(self, locked_until: str) -> None:
        super().__init__(
            message=f"Compte verrouillé jusqu'à {locked_until}",
            context={"locked_until": locked_until},
        )


# ── 400 Validation ────────────────────────────────────────────────────────────

class ValidationError(AppException):
    default_code = "VALIDATION_ERROR"


# ── 413 File ─────────────────────────────────────────────────────────────────

class FileTooLargeError(AppException):
    default_code = "FILE_TOO_LARGE"


class InvalidFileTypeError(AppException):
    default_code = "INVALID_FILE_TYPE"


# ── 500 Infrastructure ────────────────────────────────────────────────────────

class InfrastructureError(AppException):
    """DB, PDF, email failures — never expose internals."""
    default_code = "INFRASTRUCTURE_ERROR"
    default_message = "Erreur interne du serveur"


class PDFGenerationError(InfrastructureError):
    default_code = "PDF_ERROR"
    default_message = "Erreur lors de la génération du PDF"
