"""Address value object — immutable, validates ISO country code."""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Address:
    line1: str
    city: str
    country: str          # ISO 3166-1 alpha-2
    line2: str = ""
    state: str = ""
    postal_code: str = ""

    def __post_init__(self) -> None:
        if not re.match(r"^[A-Z]{2}$", self.country):
            raise ValueError(f"Country must be ISO 3166-1 alpha-2: '{self.country}'")
        if not self.line1.strip():
            raise ValueError("Address line1 cannot be empty")
        if not self.city.strip():
            raise ValueError("City cannot be empty")

    def one_line(self) -> str:
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        parts.append(self.city)
        if self.postal_code:
            parts.append(self.postal_code)
        parts.append(self.country)
        return ", ".join(parts)
