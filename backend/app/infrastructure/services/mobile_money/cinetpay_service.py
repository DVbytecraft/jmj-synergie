"""
Service CinetPay — initiation paiement mobile money, vérification statut, webhook.
En mode dev (ENVIRONMENT != "production"), les appels API sont simulés.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CinetPayService:
    BASE_URL = "https://api-checkout.cinetpay.com/v2"

    def __init__(self) -> None:
        self._api_key = settings.CINETPAY_API_KEY
        self._site_id = settings.CINETPAY_SITE_ID

    # ── Paiement ──────────────────────────────────────────────────────────────

    async def initiate_payment(
        self,
        *,
        amount: int,
        phone: str,
        transaction_id: str,
        currency: str = "XAF",
        description: str = "Paiement JMJ Synergie",
        customer_name: str = "Client",
        notify_url: str = "",
        return_url: str = "",
    ) -> dict[str, Any]:
        """Initier un paiement mobile money via CinetPay."""
        if settings.ENVIRONMENT != "production":
            return self._simulate_initiate(transaction_id, amount, phone)

        payload = {
            "apikey": self._api_key,
            "site_id": self._site_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "alternative_currency": "",
            "description": description,
            "customer_id": phone,
            "customer_name": customer_name,
            "customer_phone_number": phone,
            "notify_url": notify_url,
            "return_url": return_url,
            "channels": "MOBILE_MONEY",
            "lang": "fr",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.BASE_URL}/payment", json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") not in ("201", 201):
            raise ValueError(f"CinetPay error: {data.get('message', 'Unknown error')}")

        return {
            "transaction_id": transaction_id,
            "payment_url": data.get("data", {}).get("payment_url", ""),
            "status": "pending",
        }

    async def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """Vérifier le statut d'un paiement via CinetPay."""
        if settings.ENVIRONMENT != "production":
            return self._simulate_verify(transaction_id)

        payload = {
            "apikey": self._api_key,
            "site_id": self._site_id,
            "transaction_id": transaction_id,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.BASE_URL}/payment/check", json=payload)
            resp.raise_for_status()
            data = resp.json()

        cinetpay_status = data.get("data", {}).get("status", "")
        if cinetpay_status == "ACCEPTED":
            status = "completed"
        elif cinetpay_status in ("REFUSED", "CANCELLED", "FAILED"):
            status = "failed"
        else:
            status = "pending"

        return {
            "transaction_id": transaction_id,
            "status": status,
            "cinetpay_status": cinetpay_status,
            "raw": data,
        }

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Valider la signature HMAC du webhook CinetPay."""
        if not self._api_key:
            return False
        expected = hmac.new(  # noqa: S324
            self._api_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── Simulation dev ────────────────────────────────────────────────────────

    def _simulate_initiate(self, transaction_id: str, amount: int, phone: str) -> dict[str, Any]:
        logger.info("[DEV] Simulated CinetPay initiation: txn=%s amount=%d phone=%s", transaction_id, amount, phone)
        return {
            "transaction_id": transaction_id,
            "payment_url": f"{settings.FRONTEND_URL}/dev-mock-payment/{transaction_id}",
            "status": "pending",
        }

    def _simulate_verify(self, transaction_id: str) -> dict[str, Any]:
        logger.info("[DEV] Simulated CinetPay verify: txn=%s -> completed", transaction_id)
        return {
            "transaction_id": transaction_id,
            "status": "completed",
            "cinetpay_status": "ACCEPTED",
            "raw": {},
        }


cinetpay_service = CinetPayService()
