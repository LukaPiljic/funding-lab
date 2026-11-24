"""Day 1: a perpetual futures position (PnL, margin, liquidation price)."""
from decimal import Decimal
from enum import Enum


class Side(Enum):
    LONG = "long"
    SHORT = "short"


class Position:
    def __init__(self, side: Side, size: Decimal, entry_price: Decimal, leverage: Decimal):
        # Decimal, not float: floats are binary and can't store values like 0.1 exactly (0.1 + 0.2 != 0.3), so money math drifts.
        if not isinstance(side, Side):
            raise TypeError("side must be Side.LONG or Side.SHORT")
        for name, value in (("size", size), ("entry_price", entry_price), ("leverage", leverage)):
            if not isinstance(value, Decimal):
                raise TypeError(f"{name} must be a Decimal, e.g. Decimal('0.1'), not {type(value).__name__}")
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")

        self.side = side
        self.size = size
        self.entry_price = entry_price
        self.leverage = leverage

    def notional(self) -> Decimal:
        """Position value at entry: size * entry price."""
        return self.size * self.entry_price

    def profit_and_loss(self, exit_price: Decimal) -> Decimal:
        """PnL if closed at exit_price: long gains when price rises, short when it falls."""
        if self.side is Side.LONG:
            return self.size * (exit_price - self.entry_price)
        return self.size * (self.entry_price - exit_price)

    def margin(self) -> Decimal:
        """Initial margin: notional / leverage."""
        return self.notional() / self.leverage

    def liquidation_price(self, maintenance: Decimal) -> Decimal:
        """Price at which loss = margin - maintenance amount (fees ignored).

        maintenance is a fraction, e.g. Decimal("0.005") for 0.5%.
        """
        if self.side is Side.LONG:
            return self.entry_price * (1 - 1 / self.leverage + maintenance)
        return self.entry_price * (1 + 1 / self.leverage - maintenance)
