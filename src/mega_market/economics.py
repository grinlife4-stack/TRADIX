"""Deterministic unit-economics calculations using Decimal only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class Money:
    """A currency amount. Negative values are allowed for calculated profit/loss."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Money.amount must be Decimal; floats are not accepted")
        if not self.amount.is_finite():
            raise ValueError("Money.amount must be finite")
        if not _CURRENCY_PATTERN.fullmatch(self.currency):
            raise ValueError("currency must be a three-letter uppercase code")


@dataclass(frozen=True, slots=True)
class UnitEconomicsInput:
    """Per-unit sale price and all known variable costs in one currency."""

    selling_price: Money
    supplier_cost: Money
    shipping_cost: Money
    marketplace_fee: Money
    payment_fee: Money
    advertising_cost: Money
    tax_cost: Money
    returns_reserve: Money

    def __post_init__(self) -> None:
        values = (
            self.selling_price,
            self.supplier_cost,
            self.shipping_cost,
            self.marketplace_fee,
            self.payment_fee,
            self.advertising_cost,
            self.tax_cost,
            self.returns_reserve,
        )
        if any(not isinstance(value, Money) for value in values):
            raise TypeError("all unit-economics fields must be Money")
        currencies = {value.currency for value in values}
        if len(currencies) != 1:
            raise ValueError("all amounts must use the same currency; convert explicitly upstream")
        if self.selling_price.amount <= 0:
            raise ValueError("selling_price must be greater than zero")
        if any(value.amount < 0 for value in values[1:]):
            raise ValueError("cost inputs cannot be negative")


@dataclass(frozen=True, slots=True)
class UnitEconomicsResult:
    total_cost: Money
    net_profit: Money
    net_margin: Decimal


def calculate_unit_economics(data: UnitEconomicsInput) -> UnitEconomicsResult:
    """Calculate per-unit net profit and margin without implicit FX or rounding."""

    costs = (
        data.supplier_cost,
        data.shipping_cost,
        data.marketplace_fee,
        data.payment_fee,
        data.advertising_cost,
        data.tax_cost,
        data.returns_reserve,
    )
    total_cost_amount = sum((item.amount for item in costs), start=Decimal("0"))
    profit_amount = data.selling_price.amount - total_cost_amount
    currency = data.selling_price.currency

    return UnitEconomicsResult(
        total_cost=Money(total_cost_amount, currency),
        net_profit=Money(profit_amount, currency),
        net_margin=profit_amount / data.selling_price.amount,
    )
