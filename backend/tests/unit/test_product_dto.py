from __future__ import annotations

from app.application.dto.product_dto import CreateProductDTO


def test_create_product_dto_uppercases_currency() -> None:
    dto = CreateProductDTO(name="Produit", unit_price_cents=1000, currency="xaf")
    assert dto.currency == "XAF"
