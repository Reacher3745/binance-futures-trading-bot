# 🤖 Trading Bot — Binance USDT-M Futures Testnet

A clean, production-quality Python CLI application for placing orders on the
**Binance Futures Testnet** (USDT-M). Supports Market, Limit, and Stop-Limit
orders with full validation, structured JSON logging, and an optional
interactive wizard.

---

## 📁 Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Public package surface
│   ├── client.py            # Authenticated Binance REST client
│   ├── orders.py            # Order placement logic (Market / Limit / Stop)
│   ├── validators.py        # Input validation with descriptive errors
│   └── logging_config.py   # Coloured console + rotating JSON file logging
├── cli.py                   # CLI entry point (argparse)
├── logs/
│   └── trading_bot.log      # Rotating JSON log file (auto-created)
├── README.md
└── requirements.txt
```

---

## ⚙️ Setup

### 1 — Clone / unzip

```bash
git clone https://github.com/your-username/trading-bot.git
cd trading-bot
```

### 2 — Python virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Binance Testnet credentials

1. Visit **https://testnet.binancefuture.com**
2. Log in with a GitHub account.
3. Click **API Key** → generate a new key pair.
4. Export the credentials as environment variables:

```bash
export BINANCE_TESTNET_API_KEY="your_api_key_here"
export BINANCE_TESTNET_API_SECRET="your_api_secret_here"
```

> **Windows (PowerShell)**
> ```powershell
> $env:BINANCE_TESTNET_API_KEY = "your_api_key_here"
> $env:BINANCE_TESTNET_API_SECRET = "your_api_secret_here"
> ```

> **Tip:** Add these lines to your `.bashrc` / `.zshrc` / `.env` file so you
> don't have to export them every session.

---

## 🚀 How to Run

All commands are run from the `trading_bot/` directory via `python cli.py`.

### Global flags

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Enable DEBUG-level console output |

---

### Place a MARKET order

```bash
# BUY 0.01 BTC at market price
python cli.py order \
  --symbol BTCUSDT \
  --side   BUY \
  --type   MARKET \
  --quantity 0.01

# SELL 0.5 ETH at market price (skip confirmation)
python cli.py order \
  --symbol ETHUSDT \
  --side   SELL \
  --type   MARKET \
  --quantity 0.5 \
  --yes
```

**Example output**

```
────────────────────────────────────────────────────────────
  ORDER REQUEST
────────────────────────────────────────────────────────────
  Symbol:               BTCUSDT
  Side:                 BUY
  Type:                 MARKET
  Quantity:             0.01
────────────────────────────────────────────────────────────

  Confirm order? [y/N]: y

  ✓  ORDER PLACED SUCCESSFULLY
────────────────────────────────────────────────────────────
  Order ID:             4661527483
  Symbol:               BTCUSDT
  Side:                 BUY
  Type:                 MARKET
  Status:               FILLED
  Orig Qty:             0.010
  Executed Qty:         0.010
  Avg Price:            96483.40000
────────────────────────────────────────────────────────────
```

---

### Place a LIMIT order

```bash
# SELL 0.05 ETH at $3,250 (Good-Till-Cancelled)
python cli.py order \
  --symbol ETHUSDT \
  --side   SELL \
  --type   LIMIT \
  --quantity 0.05 \
  --price    3250.00 \
  --tif      GTC

# BUY 0.01 BTC at $90,000 (Immediate-Or-Cancel)
python cli.py order \
  --symbol   BTCUSDT \
  --side     BUY \
  --type     LIMIT \
  --quantity 0.01 \
  --price    90000.00 \
  --tif      IOC \
  --yes
```

**Status will be `NEW`** (resting on the order book) or `FILLED` if the price
was already hit.

---

### Place a Stop-Limit order *(bonus)*

```bash
# BUY STOP: trigger at $94,000 → place limit @ $94,100
python cli.py order \
  --symbol     BTCUSDT \
  --side       BUY \
  --type       STOP \
  --quantity   0.01 \
  --stop-price 94000 \
  --price      94100

# SELL STOP: trigger at $92,000 → place limit @ $91,900
python cli.py order \
  --symbol     BTCUSDT \
  --side       SELL \
  --type       STOP \
  --quantity   0.01 \
  --stop-price 92000 \
  --price      91900
```

---

### Place a Stop-Market order *(bonus)*

```bash
# Trigger a market SELL when price drops to $91,500
python cli.py order \
  --symbol     BTCUSDT \
  --side       SELL \
  --type       STOP_MARKET \
  --quantity   0.01 \
  --stop-price 91500
```

---

### Interactive wizard *(bonus)*

Launch a guided prompt-driven session — no flags required:

```bash
python cli.py wizard
```

```
  ╔══════════════════════════════════════╗
  ║     Trading Bot — Order Wizard       ║
  ╚══════════════════════════════════════╝

  Symbol [BTCUSDT]: (e.g. BTCUSDT, ETHUSDT)  BTCUSDT
  Side: BUY / [SELL]  BUY
  Order Type: [MARKET] / LIMIT / STOP / STOP_MARKET  LIMIT
  Quantity: (base asset amount, e.g. 0.01)  0.01
  Limit Price: (USD price)  91000
  Time-in-Force: [GTC] / IOC / FOK / GTX  GTC

  ── ORDER REQUEST ─────────────────────
  Symbol:    BTCUSDT
  Side:      BUY
  Type:      LIMIT
  Quantity:  0.01
  Price:     91000
  TIF:       GTC
  ──────────────────────────────────────

  Confirm and submit? [y/N]: y
```

---

### View account balance

```bash
python cli.py account
```

```
────────────────────────────────────────────────────────────
  ACCOUNT SUMMARY
────────────────────────────────────────────────────────────
  USDT:                 Wallet 10000.0000  Available 9935.1200
  BNB:                  Wallet 1000.0000   Available 1000.0000
────────────────────────────────────────────────────────────
```

---

### Verbose / debug mode

Add `--verbose` before the sub-command to print DEBUG messages to console:

```bash
python cli.py --verbose order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

---

## 📝 Logging

All requests, responses, and errors are logged to **`logs/trading_bot.log`** in
newline-delimited JSON format — ideal for ingestion by log aggregators (Loki,
Datadog, CloudWatch, etc.).

Example log entry:
```json
{
  "timestamp": "2025-05-08T09:14:01.815890+00:00",
  "level": "INFO",
  "logger": "trading_bot.client",
  "message": "Order placed successfully",
  "order_id": 4661527483,
  "status": "FILLED",
  "executed_qty": "0.010",
  "avg_price": "96483.40000"
}
```

The file rotates automatically at **5 MB**, keeping the 3 most recent archives.

---

## 🧩 Architecture

| Layer | File | Responsibility |
|-------|------|----------------|
| **CLI** | `cli.py` | Argument parsing, user prompts, formatted output |
| **Orders** | `bot/orders.py` | Maps validated params → specific Binance order functions |
| **Client** | `bot/client.py` | HMAC signing, HTTP transport, retry logic, error handling |
| **Validators** | `bot/validators.py` | Per-field and cross-field validation with clear error messages |
| **Logging** | `bot/logging_config.py` | Coloured console (INFO+) + rotating JSON file (DEBUG+) |

---

## 🔒 Assumptions & Notes

- **Testnet only.** The base URL is hardcoded to `https://testnet.binancefuture.com`.
  To use mainnet, pass `--base-url https://fapi.binance.com` (extend `cli.py`).
- **USDT-M Futures** (linear contracts). Coin-M (inverse) is not supported.
- **No leverage management.** Set leverage in the testnet web UI or extend
  `client.py` with `POST /fapi/v1/leverage`.
- **Quantity precision** is validated at the bot level (min 0.001). Binance
  imposes per-symbol lot-size rules; if you hit a `-1111` error, reduce
  decimal places.
- **Credentials are never logged.** The `_sign()` method strips the signature
  before logging and the API key appears only in request headers.

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP transport with retry support |
| `urllib3` | Retry strategy (via requests adapter) |

Standard library only — no heavy frameworks.

---

## 🧪 Running Tests (optional)

```bash
pip install pytest
pytest tests/   # if tests/ directory is present
```

---

## 🗺️ Roadmap / Bonus Ideas

- [ ] TWAP execution (slice large orders over time)
- [ ] Grid trading strategy module
- [ ] WebSocket live price feed
- [ ] Rich terminal UI (using `rich` library)
- [ ] Docker support
