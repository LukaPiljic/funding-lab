"""Day 1 (optional hour): a perp position.

TODO
- Position class: side (long/short), size, entry price, leverage
- pnl(price)
- margin()
- liquidation_price(maintenance)
- Use Decimal, not float, for prices (add a one-line comment saying why)
"""
from decimal import Decimal
from enum import Enum


class Side(Enum):
    LONG = "long"
    SHORT = "short"


class Position:
    def __init__(self, side: Side, size: Decimal, entry_price: Decimal, leverage: Decimal):


        self.side = side
        self.size = size
        self.entry_price = entry_price
        self.leverage = leverage

    def profit_and_loss(self, price: Decimal) -> Decimal:
        # TODO
        raise NotImplementedError

    def margin(self) -> Decimal:
        # TODO
        raise NotImplementedError

    def liquidation_price(self, maintenance: Decimal) -> Decimal:
        # TODO
        raise NotImplementedError
