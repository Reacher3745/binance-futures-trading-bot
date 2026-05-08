"""
trading_bot.bot — core library package.

Public surface:
  BinanceFuturesClient  - authenticated REST client
  place_order           - order dispatch router
  validate_order_params - composite input validator
  setup_logging         - configures console + file logging
"""

from .client        import BinanceFuturesClient, BinanceClientError, BinanceNetworkError
from .orders        import place_order
from .validators    import validate_order_params
from .logging_config import setup_logging

__all__ = [
    "BinanceFuturesClient",
    "BinanceClientError",
    "BinanceNetworkError",
    "place_order",
    "validate_order_params",
    "setup_logging",
]
