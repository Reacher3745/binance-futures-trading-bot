"""
Order placement logic — bridges validated user params → Binance client calls.

Each function:
  1. Accepts clean, validated Python values
  2. Builds the correct Binance parameter dict
  3. Calls the client and returns the full response
  4. Handles order-type-specific formatting
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from .client import BinanceFuturesClient

logger = logging.getLogger("trading_bot.orders")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(value: Optional[Decimal]) -> Optional[str]:
    """Convert Decimal to a plain string without scientific notation."""
    if value is None:
        return None
    return format(value, "f")


# ─────────────────────────────────────────────────────────────────────────────
# Market order
# ─────────────────────────────────────────────────────────────────────────────

def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
) -> dict:
    """
    Place a MARKET order.

    Parameters
    ----------
    client   : authenticated BinanceFuturesClient
    symbol   : e.g. "BTCUSDT"
    side     : "BUY" or "SELL"
    quantity : order quantity (base asset)

    Returns
    -------
    Full Binance order response dict.
    """
    logger.info(f"Market order → {side} {_fmt(quantity)} {symbol}")

    return client.new_order(
        symbol   = symbol,
        side     = side,
        type     = "MARKET",
        quantity = _fmt(quantity),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Limit order
# ─────────────────────────────────────────────────────────────────────────────

def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    time_in_force: str = "GTC",
) -> dict:
    """
    Place a LIMIT order.

    Parameters
    ----------
    client         : authenticated BinanceFuturesClient
    symbol         : e.g. "BTCUSDT"
    side           : "BUY" or "SELL"
    quantity       : order quantity (base asset)
    price          : limit price
    time_in_force  : GTC | IOC | FOK | GTX (default GTC)

    Returns
    -------
    Full Binance order response dict.
    """
    logger.info(
        f"Limit order → {side} {_fmt(quantity)} {symbol} @ {_fmt(price)} ({time_in_force})"
    )

    return client.new_order(
        symbol        = symbol,
        side          = side,
        type          = "LIMIT",
        quantity      = _fmt(quantity),
        price         = _fmt(price),
        timeInForce   = time_in_force,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stop-Limit order  (BONUS)
# ─────────────────────────────────────────────────────────────────────────────

def place_stop_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    stop_price: Decimal,
    time_in_force: str = "GTC",
) -> dict:
    """
    Place a STOP order (stop-limit on Binance Futures).

    The order triggers when the market reaches `stop_price` and then places a
    limit order at `price`.

    Parameters
    ----------
    client         : authenticated BinanceFuturesClient
    symbol         : e.g. "BTCUSDT"
    side           : "BUY" or "SELL"
    quantity       : order quantity (base asset)
    price          : limit price executed after trigger
    stop_price     : trigger price
    time_in_force  : GTC | IOC | FOK (default GTC)

    Returns
    -------
    Full Binance order response dict.
    """
    logger.info(
        f"Stop-Limit order → {side} {_fmt(quantity)} {symbol} "
        f"trigger@{_fmt(stop_price)} limit@{_fmt(price)} ({time_in_force})"
    )

    return client.new_order(
        symbol        = symbol,
        side          = side,
        type          = "STOP",
        quantity      = _fmt(quantity),
        price         = _fmt(price),
        stopPrice     = _fmt(stop_price),
        timeInForce   = time_in_force,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stop-Market order  (BONUS)
# ─────────────────────────────────────────────────────────────────────────────

def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: Decimal,
    stop_price: Decimal,
) -> dict:
    """
    Place a STOP_MARKET order (market order triggered at stop_price).

    Parameters
    ----------
    client     : authenticated BinanceFuturesClient
    symbol     : e.g. "BTCUSDT"
    side       : "BUY" or "SELL"
    quantity   : order quantity (base asset)
    stop_price : trigger price

    Returns
    -------
    Full Binance order response dict.
    """
    logger.info(
        f"Stop-Market order → {side} {_fmt(quantity)} {symbol} trigger@{_fmt(stop_price)}"
    )

    return client.new_order(
        symbol    = symbol,
        side      = side,
        type      = "STOP_MARKET",
        quantity  = _fmt(quantity),
        stopPrice = _fmt(stop_price),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Router — dispatch to the right function based on order type
# ─────────────────────────────────────────────────────────────────────────────

def place_order(client: BinanceFuturesClient, validated_params: dict) -> dict:
    """
    Dispatch to the correct order function based on validated_params["type"].

    Parameters
    ----------
    client           : authenticated BinanceFuturesClient
    validated_params : dict returned by validators.validate_order_params()

    Returns
    -------
    Full Binance order response dict.
    """
    ot  = validated_params["type"]
    sym = validated_params["symbol"]
    sid = validated_params["side"]
    qty = validated_params["quantity"]

    if ot == "MARKET":
        return place_market_order(client, sym, sid, qty)

    elif ot == "LIMIT":
        return place_limit_order(
            client, sym, sid, qty,
            price         = validated_params["price"],
            time_in_force = validated_params.get("time_in_force", "GTC"),
        )

    elif ot == "STOP":
        return place_stop_limit_order(
            client, sym, sid, qty,
            price         = validated_params["price"],
            stop_price    = validated_params["stop_price"],
            time_in_force = validated_params.get("time_in_force", "GTC"),
        )

    elif ot == "STOP_MARKET":
        return place_stop_market_order(
            client, sym, sid, qty,
            stop_price = validated_params["stop_price"],
        )

    else:
        raise NotImplementedError(f"Order type '{ot}' is not yet implemented in place_order().")
