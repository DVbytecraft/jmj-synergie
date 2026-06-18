"""
Money value object.
All amounts stored as integer cents to avoid floating-point errors.
Immutable — any operation returns a new instance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Money:
    """Represents an amount in a specific currency (stored as integer cents)."""
    cents: int
    currency: str = "XAF"

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError(f"Money amount cannot be negative: {self.cents}")
        if len(self.currency) != 3:
            raise ValueError(f"Currency must be ISO 4217 3-letter code: {self.currency}")

    # ── Arithmetic ────────────────────────────────────────────────────────────

    def __add__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        result = self.cents - other.cents
        if result < 0:
            raise ValueError(
                f"Subtraction would produce negative money: {self} - {other}"
            )
        return Money(result, self.currency)

    def __mul__(self, factor: Decimal | int | float) -> Money:
        result = Decimal(str(self.cents)) * Decimal(str(factor))
        return Money(int(result.to_integral_value(ROUND_HALF_UP)), self.currency)

    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.cents < other.cents

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.cents <= other.cents

    def __gt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.cents > other.cents

    def __ge__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.cents >= other.cents

    def is_zero(self) -> bool:
        return self.cents == 0

    def apply_rate(self, rate_percent: Decimal) -> Money:
        """Compute percentage of this amount (e.g. tax, discount)."""
        result = Decimal(str(self.cents)) * rate_percent / Decimal("100")
        return Money(int(result.to_integral_value(ROUND_HALF_UP)), self.currency)

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    # ── Display ───────────────────────────────────────────────────────────────

    @property
    def amount(self) -> Decimal:
        """Human-readable decimal amount."""
        return Decimal(self.cents) / Decimal("100")

    def format(self) -> str:
        """Format for display."""
        if self.currency == "XAF":
            return f"{self.cents // 100:,.0f} XAF"
        return f"{self.amount:.2f} {self.currency}"

    def __repr__(self) -> str:
        return f"Money({self.cents} {self.currency})"

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def zero(cls, currency: str = "XAF") -> Money:
        return cls(0, currency)

    @classmethod
    def from_decimal(cls, amount: Decimal, currency: str = "XAF") -> Money:
        """Convert decimal amount to cents."""
        cents = int((amount * 100).to_integral_value(ROUND_HALF_UP))
        return cls(cents, currency)
