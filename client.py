"""
Binance Futures Testnet REST client.

Handles:
  • HMAC-SHA256 request signing
  • Timestamp synchronisation (server time offset)
  • Retry logic for transient network errors
  • Structured logging of every request/response
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("trading_bot.client")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

TESTNET_BASE_URL  = "https://testnet.binancefuture.com"
RECV_WINDOW       = 5_000          # ms — how long Binance accepts a signed request
DEFAULT_TIMEOUT   = 10             # seconds per HTTP request
MAX_RETRIES       = 3              # total retry attempts for 5xx / connection errors
BACKOFF_FACTOR    = 0.5            # seconds between retries (exponential)

# Binance error codes that are NOT worth retrying
_NO_RETRY_CODES = {
    -1102,  # Mandatory param missing
    -1111,  # Too many decimals
    -2010,  # Insufficient balance
    -2019,  # Margin insufficient
    -1121,  # Invalid symbol
}


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class BinanceClientError(Exception):
    """Raised when the Binance API returns a business-logic error."""
    def __init__(self, code: int, message: str):
        self.code    = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class BinanceNetworkError(Exception):
    """Raised for connection / timeout failures."""


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thin, authenticated wrapper around the Binance USDT-M Futures REST API.

    Usage
    -----
    client = BinanceFuturesClient(api_key="…", api_secret="…")
    resp   = client.new_order(symbol="BTCUSDT", side="BUY", type="MARKET", quantity=0.01)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret are required.")

        self._api_key    = api_key.strip()
        self._api_secret = api_secret.strip().encode()
        self.base_url    = base_url.rstrip("/")
        self._timeout    = timeout
        self._session    = self._build_session()
        self._time_offset: int = 0   # ms — corrected after sync_time()

        logger.debug("BinanceFuturesClient initialised", extra={"base_url": self.base_url})

    # ── Session setup ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://",  adapter)
        return session

    # ── Time synchronisation ──────────────────────────────────────────────────

    def sync_time(self) -> int:
        """
        Fetch Binance server time, compute local→server offset, store it.
        Returns the offset in milliseconds.
        """
        before = int(time.time() * 1000)
        data   = self._request("GET", "/fapi/v1/time", signed=False)
        after  = int(time.time() * 1000)
        server = data["serverTime"]
        # midpoint approximation
        self._time_offset = server - (before + after) // 2
        logger.info(f"Time synced — server offset {self._time_offset:+d} ms")
        return self._time_offset

    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self._time_offset

    # ── Signing ───────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        query   = urllib.parse.urlencode(params)
        digest  = hmac.new(self._api_secret, query.encode(), hashlib.sha256).hexdigest()
        params["signature"] = digest
        return params

    # ── Core HTTP request ─────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        signed: bool = True,
    ) -> Any:
        params = params or {}

        if signed:
            params["timestamp"]  = self._timestamp()
            params["recvWindow"] = RECV_WINDOW
            params = self._sign(params)

        url     = f"{self.base_url}{path}"
        headers = {"X-MBX-APIKEY": self._api_key}

        # ── Log outgoing request ──
        log_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug(
            f"→ {method} {path}",
            extra={"method": method, "path": path, "params": log_params},
        )

        try:
            if method == "GET":
                response = self._session.get(url, params=params, headers=headers, timeout=self._timeout)
            elif method == "POST":
                response = self._session.post(url, params=params, headers=headers, timeout=self._timeout)
            elif method == "DELETE":
                response = self._session.delete(url, params=params, headers=headers, timeout=self._timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except requests.exceptions.Timeout as exc:
            logger.error(f"Request timed out: {method} {path}", extra={"error": str(exc)})
            raise BinanceNetworkError(f"Request to {path} timed out after {self._timeout}s.") from exc

        except requests.exceptions.ConnectionError as exc:
            logger.error(f"Connection error: {method} {path}", extra={"error": str(exc)})
            raise BinanceNetworkError(f"Could not connect to Binance API: {exc}") from exc

        # ── Log response ──
        status = response.status_code
        logger.debug(
            f"← {status} {path}",
            extra={"status_code": status, "response_body": response.text[:2000]},
        )

        # Parse JSON (all Binance responses are JSON)
        try:
            data = response.json()
        except ValueError:
            logger.error("Non-JSON response received", extra={"body": response.text[:500]})
            raise BinanceNetworkError(f"Unexpected non-JSON response (HTTP {status}).")

        # ── Handle API-level errors ──
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            code    = data["code"]
            message = data.get("msg", "Unknown error")
            logger.error(
                f"Binance API error: [{code}] {message}",
                extra={"binance_code": code, "binance_msg": message},
            )
            raise BinanceClientError(code, message)

        if not response.ok:
            raise BinanceNetworkError(f"HTTP {status}: {response.text[:300]}")

        return data

    # ── Public API methods ────────────────────────────────────────────────────

    def get_exchange_info(self) -> dict:
        """Fetch exchange info (symbol rules, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_account(self) -> dict:
        """Fetch account info (balance, positions)."""
        return self._request("GET", "/fapi/v2/account")

    def get_position_risk(self, symbol: Optional[str] = None) -> list:
        """Fetch open position risk data."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v2/positionRisk", params=params)

    def get_order(self, symbol: str, order_id: int) -> dict:
        """Fetch a single order by ID."""
        return self._request("GET", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id})

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order."""
        return self._request("DELETE", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id})

    def new_order(self, **params) -> dict:
        """
        Place a new order.  All parameter keys/values are passed directly to
        the /fapi/v1/order endpoint after serialising Decimal → str.

        Common params
        -------------
        symbol, side, type, quantity, price, stopPrice, timeInForce, reduceOnly
        """
        # Serialise Decimal / numeric types → strings Binance expects
        serialised = {k: str(v) if not isinstance(v, (str, int, bool)) else v
                      for k, v in params.items()
                      if v is not None}

        logger.info(
            "Placing order",
            extra={"order_params": {k: v for k, v in serialised.items()
                                    if k not in {"timestamp", "signature", "recvWindow"}}},
        )
        result = self._request("POST", "/fapi/v1/order", params=serialised)
        logger.info(
            "Order placed successfully",
            extra={
                "order_id":     result.get("orderId"),
                "status":       result.get("status"),
                "executed_qty": result.get("executedQty"),
                "avg_price":    result.get("avgPrice"),
            },
        )
        return result
