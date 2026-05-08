#!/usr/bin/env python3
"""
Trading Bot CLI — Binance USDT-M Futures Testnet

Usage examples
--------------
# Market BUY
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

# Limit SELL
python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.1 --price 3200.00

# Stop-Limit BUY
python cli.py order --symbol BTCUSDT --side BUY --type STOP \\
    --quantity 0.01 --price 95000 --stop-price 94000

# Interactive wizard
python cli.py wizard

# Account balance
python cli.py account

# Verbose (DEBUG) logging
python cli.py --verbose order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
"""

from __future__ import annotations

import os
import sys
import logging
import argparse
import textwrap
from decimal import Decimal
from typing import Optional

# ─── Make sure the project root is on sys.path ────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from bot import (
    BinanceFuturesClient,
    BinanceClientError,
    BinanceNetworkError,
    place_order,
    validate_order_params,
    setup_logging,
)

# ─── ANSI helpers ────────────────────────────────────────────────────────────

BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[32m"
RED     = "\033[31m"
YELLOW  = "\033[33m"
CYAN    = "\033[36m"
BLUE    = "\033[34m"
RESET   = "\033[0m"

def _c(text: str, *codes: str) -> str:
    """Wrap text with ANSI codes (no-op if stdout is not a tty)."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + str(text) + RESET


# ─── Credentials ─────────────────────────────────────────────────────────────

def _load_credentials() -> tuple[str, str]:
    """
    Load API credentials from environment variables.
    Exits with a helpful message if they are missing.
    """
    api_key    = os.environ.get("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(_c("\n  ✗  Missing API credentials.\n", RED, BOLD))
        print(
            "  Set the following environment variables before running:\n\n"
            "    export BINANCE_TESTNET_API_KEY='your_key_here'\n"
            "    export BINANCE_TESTNET_API_SECRET='your_secret_here'\n\n"
            "  Generate keys at: https://testnet.binancefuture.com\n"
        )
        sys.exit(1)

    return api_key, api_secret


# ─── Display helpers ──────────────────────────────────────────────────────────

def _divider(char: str = "─", width: int = 60) -> str:
    return _c(char * width, DIM)


def _print_order_request(params: dict) -> None:
    """Pretty-print the order parameters about to be submitted."""
    print()
    print(_divider())
    print(_c("  ORDER REQUEST", BOLD, BLUE))
    print(_divider())
    rows = [
        ("Symbol",         params["symbol"]),
        ("Side",           params["side"]),
        ("Type",           params["type"]),
        ("Quantity",       params["quantity"]),
    ]
    if params.get("price"):
        rows.append(("Price",      params["price"]))
    if params.get("stop_price"):
        rows.append(("Stop Price", params["stop_price"]))
    if params.get("time_in_force"):
        rows.append(("TIF",        params["time_in_force"]))

    for label, value in rows:
        print(f"  {_c(label + ':', DIM):<22} {_c(value, BOLD)}")
    print(_divider())
    print()


def _print_order_response(response: dict) -> None:
    """Pretty-print a successful order response."""
    print(_c("  ✓  ORDER PLACED SUCCESSFULLY", GREEN, BOLD))
    print(_divider())

    fields = [
        ("Order ID",      response.get("orderId")),
        ("Symbol",        response.get("symbol")),
        ("Side",          response.get("side")),
        ("Type",          response.get("type")),
        ("Status",        response.get("status")),
        ("Orig Qty",      response.get("origQty")),
        ("Executed Qty",  response.get("executedQty")),
        ("Avg Price",     response.get("avgPrice")),
        ("Price",         response.get("price")),
        ("Stop Price",    response.get("stopPrice")),
        ("Time in Force", response.get("timeInForce")),
        ("Update Time",   response.get("updateTime")),
    ]
    for label, value in fields:
        if value not in (None, "", "0", "0.00000000"):
            print(f"  {_c(label + ':', DIM):<22} {value}")

    print(_divider())
    print()


def _print_account(account: dict) -> None:
    """Print a concise account summary."""
    print()
    print(_divider())
    print(_c("  ACCOUNT SUMMARY", BOLD, BLUE))
    print(_divider())
    assets = account.get("assets", [])
    for asset in assets:
        wb = float(asset.get("walletBalance", 0))
        if wb > 0:
            print(
                f"  {_c(asset['asset']+ ':', DIM):<22} "
                f"Wallet {_c(f'{wb:.4f}', BOLD)}  "
                f"Available {asset.get('availableBalance', '—')}"
            )
    print(_divider())
    print()


# ─── Command: order ───────────────────────────────────────────────────────────

def cmd_order(args: argparse.Namespace, client: BinanceFuturesClient, logger: logging.Logger) -> None:
    """Handle the 'order' sub-command."""
    try:
        validated = validate_order_params(
            symbol         = args.symbol,
            side           = args.side,
            order_type     = args.type,
            quantity       = args.quantity,
            price          = getattr(args, "price", None),
            stop_price     = getattr(args, "stop_price", None),
            time_in_force  = getattr(args, "tif", "GTC") or "GTC",
        )
    except ValueError as exc:
        logger.error(f"Validation failed: {exc}")
        print(_c(f"\n  ✗  Validation error: {exc}\n", RED, BOLD))
        sys.exit(2)

    _print_order_request(validated)

    # Confirmation prompt (skipped if --yes flag given)
    if not args.yes:
        try:
            confirm = input(_c("  Confirm order? [y/N]: ", YELLOW)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(0)
        if confirm not in {"y", "yes"}:
            print("  Cancelled.")
            sys.exit(0)
        print()

    try:
        response = place_order(client, validated)
        _print_order_response(response)
    except BinanceClientError as exc:
        logger.error(f"Binance API error: {exc}")
        print(_c(f"\n  ✗  Binance error [{exc.code}]: {exc.message}\n", RED, BOLD))
        sys.exit(1)
    except BinanceNetworkError as exc:
        logger.error(f"Network error: {exc}")
        print(_c(f"\n  ✗  Network error: {exc}\n", RED, BOLD))
        sys.exit(1)


# ─── Command: wizard ─────────────────────────────────────────────────────────

def cmd_wizard(client: BinanceFuturesClient, logger: logging.Logger) -> None:
    """Interactive order wizard — guided prompts with inline validation."""

    def prompt(label: str, default: Optional[str] = None, hint: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        extra  = f"  {_c('(' + hint + ')', DIM)}" if hint else ""
        while True:
            try:
                raw = input(f"  {_c(label + suffix + ':', CYAN)} {extra} ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.")
                sys.exit(0)
            if not raw and default:
                return default
            if raw:
                return raw
            print(_c("    Value cannot be empty.", RED))

    def prompt_choice(label: str, choices: list[str], default: Optional[str] = None) -> str:
        options = " / ".join(
            _c(f"[{c}]", BOLD) if c == default else c for c in choices
        )
        while True:
            raw = prompt(label, hint=options).upper()
            if raw in choices:
                return raw
            print(_c(f"    Choose one of: {', '.join(choices)}", RED))

    print()
    print(_c("  ╔══════════════════════════════════════╗", CYAN))
    print(_c("  ║     Trading Bot — Order Wizard       ║", CYAN, BOLD))
    print(_c("  ╚══════════════════════════════════════╝", CYAN))
    print()

    symbol     = prompt("Symbol", default="BTCUSDT", hint="e.g. BTCUSDT, ETHUSDT").upper()
    side       = prompt_choice("Side", ["BUY", "SELL"])
    order_type = prompt_choice("Order Type", ["MARKET", "LIMIT", "STOP", "STOP_MARKET"], default="MARKET")
    quantity   = prompt("Quantity", hint="base asset amount, e.g. 0.01")

    price      = None
    stop_price = None
    tif        = "GTC"

    if order_type in {"LIMIT", "STOP"}:
        price = prompt("Limit Price", hint="USD price")
        if order_type == "LIMIT":
            tif = prompt_choice("Time-in-Force", ["GTC", "IOC", "FOK", "GTX"], default="GTC")

    if order_type in {"STOP", "STOP_MARKET"}:
        stop_price = prompt("Stop (Trigger) Price", hint="trigger USD price")

    # Validate
    try:
        validated = validate_order_params(
            symbol        = symbol,
            side          = side,
            order_type    = order_type,
            quantity      = quantity,
            price         = price,
            stop_price    = stop_price,
            time_in_force = tif,
        )
    except ValueError as exc:
        logger.error(f"Validation failed: {exc}")
        print(_c(f"\n  ✗  {exc}\n", RED, BOLD))
        sys.exit(2)

    print()
    _print_order_request(validated)

    try:
        confirm = input(_c("  Confirm and submit? [y/N]: ", YELLOW)).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.")
        sys.exit(0)

    if confirm not in {"y", "yes"}:
        print("  Cancelled.")
        sys.exit(0)

    print()
    try:
        response = place_order(client, validated)
        _print_order_response(response)
    except BinanceClientError as exc:
        logger.error(f"Binance API error: {exc}")
        print(_c(f"\n  ✗  Binance error [{exc.code}]: {exc.message}\n", RED, BOLD))
        sys.exit(1)
    except BinanceNetworkError as exc:
        logger.error(f"Network error: {exc}")
        print(_c(f"\n  ✗  Network error: {exc}\n", RED, BOLD))
        sys.exit(1)


# ─── Command: account ────────────────────────────────────────────────────────

def cmd_account(client: BinanceFuturesClient, logger: logging.Logger) -> None:
    """Print a concise account / balance summary."""
    try:
        account = client.get_account()
        _print_account(account)
    except (BinanceClientError, BinanceNetworkError) as exc:
        logger.error(f"Failed to fetch account: {exc}")
        print(_c(f"\n  ✗  {exc}\n", RED, BOLD))
        sys.exit(1)


# ─── Argument parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description=textwrap.dedent("""\
            Binance Futures Testnet — Trading Bot CLI
            ─────────────────────────────────────────
            Credentials via environment variables:
              BINANCE_TESTNET_API_KEY
              BINANCE_TESTNET_API_SECRET
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level console logging.",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── order ──
    order_p = sub.add_parser(
        "order",
        help="Place a single order non-interactively.",
        description="Place a MARKET, LIMIT, STOP, or STOP_MARKET order.",
    )
    order_p.add_argument("--symbol",    required=True,  help="Trading pair, e.g. BTCUSDT")
    order_p.add_argument("--side",      required=True,  choices=["BUY", "SELL"])
    order_p.add_argument("--type",      required=True,  dest="type",
                         choices=["MARKET", "LIMIT", "STOP", "STOP_MARKET"],
                         help="Order type")
    order_p.add_argument("--quantity",  required=True,  help="Base asset quantity, e.g. 0.01")
    order_p.add_argument("--price",     default=None,   help="Limit price (required for LIMIT/STOP)")
    order_p.add_argument("--stop-price",dest="stop_price", default=None,
                         help="Trigger price (required for STOP / STOP_MARKET)")
    order_p.add_argument("--tif",       default="GTC",
                         choices=["GTC", "IOC", "FOK", "GTX"],
                         help="Time-in-force for LIMIT orders (default: GTC)")
    order_p.add_argument("--yes", "-y", action="store_true",
                         help="Skip confirmation prompt.")

    # ── wizard ──
    sub.add_parser(
        "wizard",
        help="Interactive order wizard with guided prompts.",
    )

    # ── account ──
    sub.add_parser(
        "account",
        help="Display account balance and available margin.",
    )

    return parser


# ─── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    logger = setup_logging(verbose=args.verbose)
    logger.debug("CLI started", extra={"command": args.command})

    api_key, api_secret = _load_credentials()

    try:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
        client.sync_time()
    except BinanceNetworkError as exc:
        logger.critical(f"Could not connect to Binance: {exc}")
        print(_c(f"\n  ✗  Connection failed: {exc}\n", RED, BOLD))
        sys.exit(1)

    if args.command == "order":
        cmd_order(args, client, logger)
    elif args.command == "wizard":
        cmd_wizard(client, logger)
    elif args.command == "account":
        cmd_account(client, logger)


if __name__ == "__main__":
    main()
