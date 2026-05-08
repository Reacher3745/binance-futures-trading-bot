"""
Input validation for trading bot order parameters.
All validators raise ValueError with descriptive messages on failure.
"""

from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_SIDES       = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"}
VALID_TIF         = {"GTC", "IOC", "FOK", "GTX"}  # Good-Till-Cancelled / etc.

# Sensible guard-rails (Binance has per-symbol rules; these are sane defaults)
MIN_QUANTITY  = Decimal("0.001")
MAX_QUANTITY  = Decimal("1_000_000")
MIN_PRICE     = Decimal("0.0001")
MAX_PRICE     = Decimal("10_000_000")


# ─────────────────────────────────────────────────────────────────────────────
# Individual field validators
# ─────────────────────────────────────────────────────────────────────────────

def validate_symbol(symbol: str) -> str:
    """Uppercase + basic sanity checks for a trading pair symbol."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValueError(f"Symbol '{symbol}' contains invalid characters (alphanumeric only).")
    if len(symbol) < 4 or len(symbol) > 20:
        raise ValueError(f"Symbol '{symbol}' length ({len(symbol)}) is unusual — expected 4–20 characters.")
    return symbol


def validate_side(side: str) -> str:
    """Validate order side (BUY / SELL)."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}.")
    return side


def validate_order_type(order_type: str) -> str:
    """Validate order type."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: str | float | Decimal) -> Decimal:
    """Parse and validate order quantity."""
    try:
        qty = Decimal(str(quantity)).normalize()
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}' — must be a positive number.")

    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}.")
    if qty < MIN_QUANTITY:
        raise ValueError(f"Quantity {qty} is below minimum allowed ({MIN_QUANTITY}).")
    if qty > MAX_QUANTITY:
        raise ValueError(f"Quantity {qty} exceeds maximum allowed ({MAX_QUANTITY}).")
    return qty


def validate_price(price: str | float | Decimal | None, *, required: bool = False) -> Optional[Decimal]:
    """Parse and validate order price."""
    if price is None or price == "":
        if required:
            raise ValueError("Price is required for this order type but was not provided.")
        return None

    try:
        p = Decimal(str(price)).normalize()
    except InvalidOperation:
        raise ValueError(f"Invalid price '{price}' — must be a positive number.")

    if p <= 0:
        raise ValueError(f"Price must be positive, got {p}.")
    if p < MIN_PRICE:
        raise ValueError(f"Price {p} is below minimum allowed ({MIN_PRICE}).")
    if p > MAX_PRICE:
        raise ValueError(f"Price {p} exceeds maximum allowed ({MAX_PRICE}).")
    return p


def validate_stop_price(stop_price: str | float | Decimal | None, *, required: bool = False) -> Optional[Decimal]:
    """Alias for price validation used specifically for stop prices."""
    try:
        return validate_price(stop_price, required=required)
    except ValueError as exc:
        # Re-raise with 'stop price' terminology
        raise ValueError(str(exc).replace("Price", "Stop price").replace("price", "stop price")) from exc


def validate_time_in_force(tif: str) -> str:
    """Validate time-in-force value."""
    tif = tif.strip().upper()
    if tif not in VALID_TIF:
        raise ValueError(f"Invalid time-in-force '{tif}'. Must be one of: {', '.join(sorted(VALID_TIF))}.")
    return tif


# ─────────────────────────────────────────────────────────────────────────────
# Composite validator — validates all fields together and cross-checks rules
# ─────────────────────────────────────────────────────────────────────────────

def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
    time_in_force: str = "GTC",
) -> dict:
    """
    Run all validators and return a cleaned parameter dict.
    Raises ValueError with a clear message if anything is wrong.
    """
    cleaned: dict = {}

    cleaned["symbol"]         = validate_symbol(symbol)
    cleaned["side"]           = validate_side(side)
    cleaned["type"]           = validate_order_type(order_type)
    cleaned["quantity"]       = validate_quantity(quantity)

    ot = cleaned["type"]

    # Price rules per order type
    price_required   = ot in {"LIMIT", "STOP", "TAKE_PROFIT"}
    stop_required    = ot in {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"}

    cleaned["price"]          = validate_price(price, required=price_required)
    cleaned["stop_price"]     = validate_stop_price(stop_price, required=stop_required)

    # Time-in-force only meaningful for LIMIT orders
    if ot == "LIMIT":
        cleaned["time_in_force"] = validate_time_in_force(time_in_force)

    # Cross-checks
    if ot == "STOP" and cleaned["price"] and cleaned["stop_price"]:
        if cleaned["side"] == "BUY" and cleaned["stop_price"] >= cleaned["price"]:
            raise ValueError(
                "For a BUY STOP order the stop price must be less than the limit price."
            )
        if cleaned["side"] == "SELL" and cleaned["stop_price"] <= cleaned["price"]:
            raise ValueError(
                "For a SELL STOP order the stop price must be greater than the limit price."
            )

    return cleaned
