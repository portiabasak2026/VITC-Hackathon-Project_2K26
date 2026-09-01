# Ledger — Multi-Agent Financial Intelligence

> A Streamlit-based financial intelligence dashboard that combines live market data, technical indicators, quantitative fundamentals, TF-IDF regulatory-document retrieval, concurrent agent execution, portfolio tracking, and persistent analysis history.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Not%20Specified-lightgrey.svg)](#license)

## Overview

Ledger is a local-first financial analysis application built around a small **multi-agent orchestration layer**.

For a selected ticker, Ledger concurrently runs three specialist components:

1. **Market Dynamics Agent** — interprets technical telemetry derived from Yahoo Finance price/volume history.
2. **Fundamental Analysis Agent** — screens quantitative company fundamentals such as P/E, market capitalization, sector, and profit margin.
3. **Regulatory RAG Agent** — retrieves relevant documents from a local disclosure corpus using TF-IDF vectors and cosine similarity.

A deterministic **synthesis layer** then combines those signals with the user's selected risk profile and produces one of:

- `ACCUMULATE`
- `HOLD`
- `REDUCE`

The application also persists user accounts, watchlists, holdings, and analysis history in SQLite.

> **Important:** Ledger is an educational/demo application. Its recommendations are rule-based signals, not investment advice. Market data may be delayed or incomplete, and the current RAG corpus is small and partially static. Do not use the application as the sole basis for financial decisions.

---

## Key Features

### 📈 Market intelligence

- Fetches approximately six months of daily historical market data through `yfinance`.
- Calculates:
  - RSI(14)
  - MACD(12, 26, 9)
  - 20-day volume ratio
  - 20-day annualized realized volatility
- Classifies:
  - Momentum: `Bullish`, `Bearish`, or `Neutral`
  - Volume: `Standard` or `Anomaly`
  - Volatility: `High` or `Low`
- Caches market data for five minutes.
- Provides an explicit degraded/offline simulation mode.

### 🤖 Concurrent multi-agent analysis

The analysis pipeline uses `ThreadPoolExecutor(max_workers=3)` to execute the three specialist agents concurrently.

```text
                         ┌─────────────────────┐
                         │   Selected Ticker   │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
          ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐
          │ Market Agent │  │ Fundamental  │  │ Regulatory RAG  │
          │              │  │ Agent        │  │ Agent           │
          └──────┬───────┘  └──────┬───────┘  └────────┬────────┘
                 │                 │                   │
                 └─────────────────┼───────────────────┘
                                   ▼
                       ┌────────────────────────┐
                       │ Deterministic Synthesis │
                       │ + Risk Profile          │
                       └────────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ ACCUMULATE / HOLD / │
                         │ REDUCE + Confidence  │
                         └──────────────────────┘
```

The concurrency is genuine: the three tasks are submitted to a thread pool before their results are collected.

### 🧠 Retrieval-augmented analysis

The RAG component currently uses:

- `TfidfVectorizer`
- cosine similarity
- a small in-code disclosure corpus
- ticker-aware filtering
- a configurable `top_k` result count

The current corpus contains examples for `AAPL`, `TSLA`, `NVDA`, plus a `GLOBAL` regulatory/prudential document.

Retrieved documents are surfaced as source attributions in the UI and persisted with analysis history.

### 💼 Portfolio tracking

Users can:

- Add holdings by ticker.
- Record number of shares.
- Optionally record cost basis per share.
- View current position value.
- View total portfolio valuation.
- View total cost basis.
- View unrealized P/L.
- Delete positions.

Portfolio valuation uses the same cached market-price pipeline used by the dashboard.

### ⭐ Persistent watchlists

Each user gets a persistent watchlist stored in SQLite.

The default watchlist is:

```text
AAPL, TSLA, NVDA
```

Users can edit and save their active watchlist from the sidebar.

Ticker input is validated against:

```text
^[A-Z]{1,5}(\.[A-Z])?$
```

### 🕘 Analysis history

Every completed multi-agent analysis is persisted with:

- username
- ticker
- risk profile
- action
- recommendation kind
- confidence
- rationale
- source attributions
- degraded-input state
- execution latency
- timestamp

The History tab displays previous agent invocations for the signed-in user.

### 🔐 Authentication

Accounts are stored in SQLite and passwords are hashed using `bcrypt`.

The authentication layer supports:

- account creation
- password hashing
- username uniqueness
- password verification
- Streamlit session-based login state

### 🎨 Financial-terminal-style UI

The application uses a custom dark visual system with:

- IBM Plex Sans
- IBM Plex Mono
- compact market tape
- signal badges
- Plotly charts
- technical gauges
- agent trace cards
- recommendation cards

The Streamlit theme is configured through `config.toml`.

---

## Architecture

Ledger is intentionally split into a small number of focused modules.

```text
.
├── app.py
├── auth.py
├── db.py
├── rag.py
├── config.toml
├── requirements.txt
├── README.md
└── users.db
```

### `app.py`

The main Streamlit application.

Responsibilities include:

- page configuration
- login/signup UI
- session state
- ticker validation
- market-data ingestion
- technical indicator calculations
- fundamentals retrieval
- agent orchestration
- synthesis logic
- dashboard rendering
- portfolio rendering
- history rendering
- architecture view
- custom CSS

### `auth.py`

A lightweight authentication layer backed by SQLite.

It creates and accesses the `users` table and uses `bcrypt` for password hashing and verification.

### `db.py`

The persistence layer.

It manages:

```text
watchlist_items
holdings
analysis_history
```

It also contains a migration path for older `analysis_history` schemas, including adding the `latency` column when necessary.

### `rag.py`

The retrieval engine.

It creates a TF-IDF representation of the disclosure corpus and uses cosine similarity to rank documents for a query.

### `config.toml`

Streamlit theme/server configuration.

The current theme is based around a dark brown/black surface, amber primary color, and light text.

---

## Data Flow

### 1. Authentication

```text
User
 │
 ├── Create account ──► bcrypt hash ──► SQLite
 │
 └── Login ───────────► bcrypt verify ─► Streamlit session
```

### 2. Market analysis

```text
Ticker
  │
  ▼
yfinance
  │
  ▼
6 months daily OHLCV
  │
  ├──► RSI(14)
  ├──► MACD(12,26,9)
  ├──► Volume / 20-day average
  └──► 20-day annualized volatility
```

### 3. Agent execution

```text
Market data ───────────► Market Agent
Fundamentals ──────────► Fundamental Agent
Ticker + query ────────► Regulatory RAG Agent
                              │
                              ▼
                       Retrieved documents
```

All three specialist tasks are executed concurrently.

### 4. Synthesis

The synthesis layer considers:

- momentum
- volatility
- valuation elevation
- user risk profile
- whether inputs are degraded

It then produces an action, confidence score, rationale, and attribution list.

### 5. Persistence

```text
Analysis result
      │
      ▼
analysis_history
      │
      ▼
History tab
```

---

## Recommendation Logic

The current synthesis engine is intentionally deterministic.

### Action selection

The effective decision order is:

| Condition | Action |
|---|---|
| Momentum is `Bearish` | `REDUCE` |
| Low risk + high volatility or elevated P/E | `HOLD` |
| High risk + bullish momentum | `ACCUMULATE` |
| Otherwise | `HOLD` |

An elevated trailing P/E is currently defined as:

```text
Trailing P/E > 45
```

### Confidence

The current confidence calculation is bounded between `0.40` and `0.95`.

It is primarily influenced by:

- distance of RSI from the neutral level of 50
- whether the data is degraded

This means the displayed confidence should be interpreted as a **signal-strength heuristic**, not a statistically calibrated probability of return.

---

## Technical Indicators

### RSI

Ledger computes RSI using exponentially weighted average gains and losses with a 14-period window.

Conceptually:

```text
RS = Average Gain / Average Loss

RSI = 100 - (100 / (1 + RS))
```

Missing/undefined values are normalized to `50`.

### MACD

The application calculates:

```text
Fast EMA  = 12 periods
Slow EMA  = 26 periods
Signal    = 9 periods
```

The MACD spread is:

```text
MACD line - Signal line
```

Momentum classification uses a price-scaled threshold:

```text
abs(MACD spread) < 0.0005 × price
```

→ `Neutral`

Positive spread → `Bullish`

Negative spread → `Bearish`

### Volume

The latest trading volume is compared with the mean of the preceding 20 trading sessions.

```text
Volume ratio = Today's volume / Previous 20-day average
```

A ratio of:

- `>= 1.5` → `Anomaly`
- `<= 0.5` → `Anomaly`
- otherwise → `Standard`

### Volatility

Realized volatility is calculated from the most recent 20 daily percentage returns and annualized using:

```text
daily return standard deviation × √252 × 100
```

Current classification:

- `>= 40%` → `High`
- `< 40%` → `Low`

---

## RAG Design

The current RAG implementation is intentionally lightweight.

### Corpus

The disclosure corpus is defined directly in `rag.py`.

It currently includes:

- Apple (`AAPL`)
- Tesla (`TSLA`)
- NVIDIA (`NVDA`)
- a global SEBI/RBI-oriented volatility document

### Retrieval

Documents are transformed into TF-IDF vectors:

```python
TfidfVectorizer(stop_words="english")
```

A query is transformed using the same vectorizer and ranked using cosine similarity.

Ticker filtering allows a requested ticker plus the `GLOBAL` document.

### Important limitation

Despite the project's RAG architecture, the current implementation is **not a live SEC/EDGAR document ingestion pipeline**.

The disclosure text is currently embedded in the application source code. Therefore, retrieved passages should be understood as the application's configured corpus, not proof that Ledger fetched the latest filing at analysis time.

---

## Persistence Model

SQLite is used for local persistence.

### Users

```text
users
├── username PRIMARY KEY
└── password
```

Passwords are stored as bcrypt hashes rather than plaintext.

### Watchlist

```text
watchlist_items
├── id
├── username
├── ticker
├── position
└── added_at
```

`(username, ticker)` is unique.

### Holdings

```text
holdings
├── id
├── username
├── ticker
├── shares
├── cost_basis
└── added_at
```

### Analysis history

```text
analysis_history
├── id
├── username
├── ticker
├── risk_tolerance
├── action
├── kind
├── confidence
├── rationale
├── attributions
├── degraded
├── latency
└── run_at
```

Attributions are serialized as JSON when stored.

---

## Installation

### Prerequisites

Recommended:

- Python 3.10+
- pip
- network access for Yahoo Finance data

### 1. Clone the project

```bash
git clone <your-repository-url>
cd <your-repository-directory>
```

### 2. Create a virtual environment

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The current dependency set includes:

- Streamlit
- Plotly
- yfinance
- pandas
- NumPy
- requests
- bcrypt
- scikit-learn

### 4. Configure Streamlit

If you want Streamlit to automatically load the supplied theme configuration, place the configuration at:

```text
.streamlit/config.toml
```

The supplied `config.toml` contains the theme and headless-server settings.

### 5. Start Ledger

```bash
streamlit run app.py
```

Streamlit will display the local application URL in the terminal.

---

## First Run

1. Open Ledger in your browser.
2. Select **Create Account**.
3. Create a username and password.
4. Log in.
5. Review the default watchlist.
6. Select a risk profile.
7. Select an asset.
8. Review the technical telemetry.
9. Click **Execute Multi-Agent Reasoning Swarm**.
10. Review each agent's output and the final synthesis.
11. Optionally add portfolio positions.
12. Review previous analyses in **History**.

---

## Configuration

### Risk profile

The sidebar supports:

```text
Low
Medium
High
```

The risk profile influences the deterministic synthesis rules.

### Watchlist

Enter comma-separated tickers:

```text
AAPL, TSLA, NVDA, MSFT
```

Invalid entries are reported before saving.

### Degraded feed simulation

**Simulate Data Feed Outage** intentionally disables live market/fundamental/RAG inputs.

This is useful for testing failure handling and degraded analysis paths without intentionally breaking the application.

### Refresh

**Refresh Live Telemetry**:

- increments the refresh epoch
- clears cached market data
- clears cached fundamentals
- clears the current in-memory agent results

---

## Caching

Market data is cached for approximately five minutes.

Fundamental data is cached for approximately one hour.

The application also exposes a manual refresh action that clears these caches.

Caching reduces repeated external requests and makes normal Streamlit reruns less expensive.

---

## Error and Degraded-Mode Behavior

Ledger is designed to avoid inventing unavailable market data.

Examples:

- no/insufficient price history → market feed marked unavailable
- simulated outage → agents return `Degraded`
- missing fundamentals → fundamental feed becomes unavailable
- no relevant RAG result → retrieval returns an explicit empty result
- missing portfolio price → the position is displayed with a zero current price in the current implementation

The last behavior is worth noting for production use: a missing quote should ideally be represented as **unknown**, rather than mathematically equivalent to a real price of `$0.00`.

---

## Security Notes

The current project is suitable for a local/demo environment, but it is **not production-hardened authentication infrastructure**.

Current protections:

- passwords are bcrypt-hashed
- SQL queries use parameterized values
- user-scoped queries include the authenticated username

Before deploying publicly, consider:

- secure session/authentication architecture
- CSRF protection
- rate limiting
- password reset/recovery
- account lockout or abuse controls
- secret management
- HTTPS
- stronger input validation
- database backups
- audit logging
- authorization testing
- production-grade database deployment
- protection of the SQLite database file

### Database file

`users.db` contains application state and credentials. Do not commit a populated production database to a public repository.

Add it to `.gitignore` for normal development:

```gitignore
users.db
.venv/
__pycache__/
.streamlit/secrets.toml
```

---

## Production Readiness

Ledger has a strong demo architecture, but several components should evolve before production deployment.

### Current strengths

- clear separation between UI, authentication, persistence, and retrieval
- real market-data ingestion
- deterministic technical calculations
- concurrent specialist execution
- persistent user state
- graceful degraded-mode simulation
- source attribution
- explicit recommendation rules
- compact Streamlit UI

### Current limitations

#### 1. The "agents" are deterministic functions

There is currently no LLM or autonomous reasoning model.

Agent traces are generated from templates and computed values.

The synthesis layer is a fixed rule engine.

#### 2. RAG is not live document retrieval

The disclosure corpus is embedded in `rag.py`.

A production version should ingest and refresh real filings/documents.

#### 3. Fundamental analysis is quantitative

The fundamental agent currently surfaces numeric fields such as P/E, market cap, sector, and profit margin.

It does not perform qualitative reading of:

- MD&A
- risk factors
- earnings-call transcripts
- balance-sheet narratives
- management commentary

#### 4. Yahoo Finance is an external dependency

Availability and field completeness can vary by ticker.

The application should treat external data as fallible.

#### 5. SQLite is appropriate for local use

For multi-user production deployment, consider PostgreSQL or another managed database.

#### 6. Confidence is not calibrated

The confidence score is a heuristic signal-strength value. It is not a backtested probability or expected-return estimate.

---

## Recommended Next Evolution

A production-oriented roadmap could look like this:

### Phase 1 — Reliability

- Add automated unit tests to the repository.
- Add integration tests for each agent.
- Add explicit missing-price handling in portfolio calculations.
- Add structured logging.
- Add stronger input validation.
- Add a proper `.streamlit/config.toml` project structure.
- Add CI for linting, type checking, and tests.

### Phase 2 — Real RAG

Replace the small in-code corpus with a document pipeline:

```text
SEC / regulatory source
        │
        ▼
Document ingestion
        │
        ▼
Cleaning + chunking
        │
        ▼
Embeddings / vector index
        │
        ▼
Ticker/date/source filters
        │
        ▼
Retrieved evidence
```

### Phase 3 — Actual agent reasoning

Introduce an LLM synthesis layer that receives:

- technical signals
- fundamentals
- retrieved evidence
- risk profile
- portfolio context

The model should be required to cite the evidence it actually used.

### Phase 4 — Evaluation

Build a reproducible evaluation suite measuring:

- retrieval precision
- recommendation consistency
- citation correctness
- degraded-mode behavior
- latency
- signal calibration
- backtest performance

### Phase 5 — Production infrastructure

Consider:

- PostgreSQL
- proper authentication provider
- secrets management
- background jobs
- scheduled data ingestion
- observability
- deployment automation
- role-based access control
- audit trails

---

## Testing

The project should be tested at three levels.

### Unit tests

Recommended targets:

```text
parse_watchlist()
compute_rsi()
compute_macd()
market classification rules
synthesis decision rules
RAG retrieval
database CRUD
```

### Integration tests

Test:

```text
login → dashboard
watchlist → market data
market data → agents
agents → synthesis
synthesis → database
database → history
holdings → portfolio valuation
```

External services should be mocked in deterministic test runs.

### Manual smoke test

Run:

```bash
streamlit run app.py
```

Then verify:

- account creation
- login
- invalid credentials
- watchlist editing
- market refresh
- degraded-mode toggle
- multi-agent execution
- portfolio add/delete
- history persistence
- logout

---

## Performance Notes

The three specialist agent tasks are dispatched concurrently:

```python
with ThreadPoolExecutor(max_workers=3) as executor:
    ...
```

This is useful because the agents are primarily I/O/independent-computation oriented and do not depend on one another before synthesis.

The application also caches expensive external-data retrieval:

```text
Market data       → 5 minutes
Fundamentals      → 1 hour
```

The analysis history records total execution latency, making it possible to monitor the application's runtime behavior over time.

---

## Dependency Summary

| Package | Purpose |
|---|---|
| `streamlit` | Web application UI and session state |
| `plotly` | Charts and technical gauges |
| `yfinance` | Market data and quantitative company information |
| `pandas` | Time-series/data manipulation |
| `numpy` | Numerical calculations |
| `requests` | HTTP dependency available for future/auxiliary integrations |
| `bcrypt` | Password hashing and verification |
| `scikit-learn` | TF-IDF and cosine-similarity retrieval |

---

## Project Philosophy

Ledger follows a few useful design principles:

### Evidence over invented data

If an external feed is unavailable, the application should show that the feed is unavailable rather than fabricate a number.

### Deterministic before sophisticated

The current recommendation engine favors simple, inspectable rules over opaque behavior.

### Parallel specialists, centralized synthesis

Independent signals are generated separately, then combined in one synthesis layer.

### Persistent state

Watchlists, holdings, and analysis history survive Streamlit reruns and subsequent sessions.

### Attribution matters

Analysis output carries source attributions so users can distinguish computed market signals from retrieved disclosure evidence.

---

## Disclaimer

Ledger is an educational software project for financial-data exploration and multi-agent application design.

It does **not** provide personalized investment advice, guarantees, predictions, or recommendations suitable for real-money trading.

Market data can be delayed, incomplete, incorrect, or temporarily unavailable. Technical indicators are historical calculations and do not guarantee future performance. The current recommendation engine is a deterministic heuristic and has not been presented here as a validated trading strategy.

Always independently verify financial information and consult a qualified financial professional where appropriate.

---

## License

No license is currently specified in the project files.

If this repository is intended for public distribution, add an explicit license file such as `LICENSE` and update this section accordingly.

---

## Acknowledgements

Ledger is built with:

- Streamlit
- Plotly
- yfinance
- pandas
- NumPy
- scikit-learn
- bcrypt

