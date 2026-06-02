# Stock Buy/Sell Signal Generator

A multi-agent AI system that generates stock buy/sell/hold signals using various data sources and analysis techniques.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration — application.yml](#configuration--applicationyml)
5. [Docker Compose](#docker-compose)
6. [Initialisation Scripts](#initialisation-scripts)
7. [Feature Flags](#feature-flags)
8. [Running the Application](#running-the-application)
9. [All CLI Options](#all-cli-options)
10. [Utility Scripts](#utility-scripts)
11. [Architecture Diagram](#architecture-diagram)
12. [AWS Deployment Architecture](#aws-deployment-architecture)

---

## Quick Start

Minimum steps to run a single-agent analysis with no infrastructure:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your LLM API key
export OPENAI_API_KEY=sk-...

# 3. Run — Streamlit dashboard opens in browser
python main.py

# Or run headless
python main.py --ticker AAPL --nogui
```

---

## System Requirements

| Dependency | Version | Required | Notes |
|---|---|---|---|
| Python | 3.11+ | Yes | |
| Docker Desktop | 4.x+ | For infrastructure | Kafka, Qdrant, PostgreSQL, Neo4j, Unleash |
| ffmpeg | Any | For `EarningsCallAgent` | `brew install ffmpeg` |
| Node.js | 18+ | For React dashboard only | `python main.py --react` |

---

## Installation

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/<your-org>/StockAIAssistant.git
cd StockAIAssistant
pip install -r requirements.txt
```

### 2. Install optional audio transcription backend (pick one)

```bash
# Recommended — fastest local transcription (GPU/CPU)
pip install faster-whisper

# Alternative — local CPU-only fallback
pip install openai-whisper

# Or set OPENAI_API_KEY and use the cloud Whisper API (no extra install)
```

### 3. Install ffmpeg (required for EarningsCallAgent)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

### 4. Install React frontend (optional)

```bash
cd frontend
npm install
cd ..
```

---

## Configuration — application.yml

Copy and edit the template. This file is gitignored — never commit it.

```bash
cp application.yml.example application.yml   # if example exists, else create manually
```

Minimal `application.yml` for full local stack:

```yaml
debug: false

llm:
  model: gpt-4o-mini        # or ollama/llama3.1, claude-sonnet-4-6, etc.
  api_base: null             # set to http://localhost:11434 for Ollama

postgres:
  enabled: true
  host: localhost
  port: 5433                 # Docker postgres on 5433 (local postgres stays on 5432)
  database: stock_signal
  user: postgres
  password: postgres
  backfill_years: 5

kafka:
  enabled: true
  bootstrap_servers: localhost:9092
  topics:
    prices: stock-prices
    news: stock-news
    filings: sec-filings
    earnings_call: earnings-call-live

qdrant:
  enabled: true
  host: localhost
  port: 6333

neo4j:
  enabled: true
  uri: bolt://localhost:7687
  user: neo4j
  password: neo4j_password

whisper:
  model_size: base            # tiny / base / small / medium / large
  chunk_seconds: 30

feature_flags:
  unleash:
    url: http://localhost:4242/api
    app_name: stock-signal-api
    refresh_interval_seconds: 15
  defaults:
    single_stock_analysis: true
    watchlist_analysis: false
    premarket_analysis: false
    aftermarket_analysis: false
    knowledge_graph: false    # set true after Neo4j is running
```

---

## Docker Compose

### Services overview

| Service | Port | Profile | Purpose |
|---|---|---|---|
| Zookeeper | 2181 | default | Kafka dependency |
| Kafka | 9092 | default | Event streaming |
| Qdrant | 6333, 6334 | default | Vector database |
| PostgreSQL | 5433 | default | OHLCV price cache |
| Adminer | 8080 | default | PostgreSQL UI |
| Neo4j | 7474, 7687 | default | Knowledge graph |
| Unleash | 4242 | `feature-flags` | Feature flag server |
| Unleash DB | — | `feature-flags` | Unleash's PostgreSQL |

### Step 1 — Start core infrastructure

```bash
docker compose up -d
```

Starts Kafka, Qdrant, PostgreSQL, Adminer, and Neo4j.

### Step 2 — Start feature flags (optional but recommended)

```bash
docker compose --profile feature-flags up -d
```

Adds the Unleash feature flag server on `http://localhost:4242`.

### Step 3 — Verify all services are healthy

```bash
docker compose ps
```

Expected: all containers in `running` or `healthy` state.

```bash
# Verify individual services
curl http://localhost:6333/healthz          # Qdrant
curl http://localhost:9092                  # Kafka (connection refused = healthy)
curl http://localhost:4242/health           # Unleash
open http://localhost:7474                  # Neo4j Browser
open http://localhost:8080                  # Adminer (PostgreSQL UI)
```

### Adminer login (PostgreSQL)

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `postgres` |
| Username | `postgres` |
| Password | `postgres` |
| Database | `stock_signal` |

### Stop all services

```bash
docker compose --profile feature-flags down
```

---

## Initialisation Scripts

Run these once after Docker services are healthy, in this order:

### Script 1 — init_infrastructure.py

Creates all Qdrant collections, Kafka topics, and Unleash feature flags automatically.

```bash
python scripts/init_infrastructure.py
```

What it does:
- Creates Qdrant collections: `stock_news`, `sec_filings`, `stock_prices`, `investor_presentations`, `earnings_call_transcripts`
- Creates Kafka topics: `stock-prices`, `stock-news`, `sec-filings`, `earnings-call-live`
- Registers all feature flags in Unleash with their default values

### Script 2 — seed_knowledge_graph.py

Seeds the Neo4j + NetworkX knowledge graph with all 11 GICS sectors, macro factor relationships, and ~80 major tickers. Safe to re-run (idempotent).

```bash
python scripts/seed_knowledge_graph.py
```

Expected output:
```
Seeding knowledge graph...
  Neo4j enabled : True
  Neo4j URI     : bolt://localhost:7687
  In-memory graph: 184 nodes, 301 edges
  Syncing to Neo4j...
  Neo4j sync complete.

Spot-check:
  AAPL     sector=Information Technology          rate_sensitive=False  cyclical=False
  JPM      sector=Financials                      rate_sensitive=False  cyclical=False
  NEE      sector=Utilities                       rate_sensitive=True   cyclical=False
  XOM      sector=Energy                          rate_sensitive=False  cyclical=False
  TSLA     sector=Consumer Discretionary          rate_sensitive=False  cyclical=True
  UNKNOWN  sector=N/A                             rate_sensitive=False  cyclical=False
```

> Only needed when `KNOWLEDGE_GRAPH` feature flag is enabled and Neo4j is running.

---

## Feature Flags

All flags have safe defaults. Enable them progressively as you bring up more infrastructure.

### Flag reference

| Flag | Default | Requires | Description |
|---|---|---|---|
| `single_stock_analysis` | `true` | Nothing | Core single stock analysis |
| `watchlist_analysis` | `false` | Nothing | Batch watchlist analysis |
| `premarket_analysis` | `false` | Nothing | Pre-market hours (4:00–9:30 AM ET) |
| `aftermarket_analysis` | `false` | Nothing | After-hours (4:00–8:00 PM ET) |
| `ml_analysis` | `true` | scikit-learn, xgboost | LSTM + XGBoost + EnsembleScorer |
| `knowledge_graph` | `false` | Neo4j running | Neo4j + NetworkX sector/macro rules |
| `agent_technical` | `true` | yfinance | TechnicalAnalysisAgent |
| `agent_news` | `true` | yfinance | NewsAgent |
| `agent_sec` | `true` | SEC EDGAR (free) | SECFilingAgent |
| `agent_sentiment` | `true` | LLM | SentimentAgent |
| `agent_zacks` | `true` | Web scraping | ZacksAnalysisAgent |
| `agent_tipranks` | `true` | yfinance | TipRanksAgent |
| `agent_seekingalpha` | `true` | yfinance | SeekingAlphaAgent |
| `agent_insider` | `true` | yfinance | InsiderInstitutionalAgent |
| `agent_motleyfool` | `true` | yfinance | MotleyFoolAgent |
| `agent_stockstory` | `true` | yfinance | StockStoryAgent |
| `agent_yahoofinance` | `true` | yfinance | YahooFinanceAgent |
| `agent_morningstar` | `true` | yfinance | MorningstarAgent |
| `agent_gurufocus` | `true` | yfinance | GuruFocusAgent |
| `agent_tradingview` | `true` | yfinance | TradingViewAgent |
| `agent_stockrover` | `true` | yfinance | StockRoverAgent |
| `agent_simplywallst` | `true` | yfinance | SimplyWallStAgent |
| `agent_alphaspread` | `true` | yfinance | AlphaSpreadAgent |
| `agent_factset` | `true` | yfinance | FactSetAgent |
| `agent_capitaliq` | `true` | yfinance | CapitalIQAgent |
| `agent_marketbeat` | `true` | yfinance | MarketBeatAgent |
| `agent_refinitiv` | `true` | yfinance | RefinitivAgent |
| `agent_macrotrends` | `true` | yfinance | MacrotrendsAgent |
| `agent_ycharts` | `true` | yfinance | YChartsAgent |
| `agent_koyfin` | `true` | yfinance | KoyfinAgent |
| `agent_valueline` | `true` | yfinance | ValueLineAgent |
| `agent_xtwitter` | `true` | yfinance | XTwitterAgent |
| `agent_facebook` | `true` | yfinance | FacebookAgent |
| `agent_instagram` | `true` | yfinance | InstagramAgent |
| `agent_cnbc` | `true` | yfinance | CNBCAgent |
| `agent_bloomberg` | `true` | yfinance | BloombergAgent |
| `agent_wsj` | `true` | yfinance | WSJAgent |
| `agent_marketwatch` | `true` | yfinance | MarketWatchAgent |
| `agent_foxbusiness` | `true` | yfinance | FoxBusinessAgent |
| `agent_barrons` | `true` | yfinance | BarronsAgent |
| `agent_insidermonkey` | `true` | yfinance | InsiderMonkeyAgent |
| `agent_quiverquant` | `true` | yfinance | QuiverQuantAgent |
| `agent_dataroma` | `true` | yfinance | DataromaAgent |
| `agent_openinsider` | `true` | yfinance | OpenInsiderAgent |
| `agent_whalewisdom` | `true` | yfinance | WhaleWisdomAgent |
| `agent_etfcom` | `true` | yfinance | ETFComAgent |
| `agent_etfdb` | `true` | yfinance | ETFDBAgent |
| `agent_globalxetf` | `true` | yfinance | GlobalXETFAgent |
| `agent_arkinvest` | `true` | yfinance | ARKInvestAgent |
| `agent_morningstaretf` | `true` | yfinance | MorningstarETFAgent |
| `agent_reddit` | `true` | yfinance | RedditAgent |
| `agent_stocktwits` | `true` | yfinance | StockTwitsAgent |
| `agent_options_flow` | `true` | yfinance | OptionsFlowAgent |
| `agent_investor_presentation` | `true` | pypdf, ffmpeg | InvestorPresentationAgent |
| `agent_earnings_call` | `true` | ffmpeg, Whisper | EarningsCallAgent |

### Enabling flags — Local (Unleash)

After `docker compose --profile feature-flags up -d` and running `init_infrastructure.py`:

1. Open `http://localhost:4242` in your browser
2. Login: **admin / unleash4all**
3. Go to **Feature Toggles** → find the flag → click to enable
4. No restart needed — flags refresh every 15 seconds

To enable the knowledge graph:
1. Enable `knowledge_graph` in Unleash UI
2. Set `neo4j.enabled: true` in `application.yml`
3. Run `python scripts/seed_knowledge_graph.py`

### Enabling flags — via environment variables (override)

Any flag can be overridden with an env var regardless of Unleash:

```bash
export KNOWLEDGE_GRAPH=true
export NEO4J_ENABLED=true
```

### Verify all flags

```bash
python -c "from infrastructure.feature_flags import get_all_flags; import json; print(json.dumps(get_all_flags(), indent=2))"
```

---

## Running the Application

### Recommended startup order

```bash
# 1. Start Docker services
docker compose --profile feature-flags up -d

# 2. Wait for services to be healthy (~30s)
docker compose ps

# 3. Initialise infrastructure (first time only)
python scripts/init_infrastructure.py

# 4. Seed knowledge graph (first time, or when Neo4j flag is enabled)
python scripts/seed_knowledge_graph.py

# 5. Run the application
python main.py
```

### Option A — Streamlit Dashboard (default)

```bash
python main.py
# Opens http://localhost:8501 automatically
```

### Option B — React Dashboard

```bash
cd frontend && npm install && cd ..
python main.py --react
# Starts FastAPI on :8000 + React dev server on :5173
```

### Option C — Headless CLI (single agent)

```bash
python main.py --ticker AAPL --nogui
python main.py --ticker AAPL --nogui --days 60
python main.py --ticker AAPL --nogui --model gpt-4o
```

### Option D — Multi-agent mode (no infrastructure)

```bash
python main.py --ticker AAPL --nogui --multi-agent
python main.py --ticker AAPL --nogui --multi-agent --verbose
```

### Option E — Multi-agent with full infrastructure

```bash
python main.py --ticker AAPL --nogui --multi-agent --kafka --qdrant
```

### Option F — Local LLM (Ollama)

```bash
# Start Ollama first
ollama pull llama3.1

python main.py --ticker AAPL --nogui --multi-agent \
  --model ollama/llama3.1 \
  --base-url http://localhost:11434
```

### Option G — Earnings call audio analysis

```bash
# From uploaded file
export EARNINGS_AUDIO_FILE_AAPL=/path/to/aapl-q1-2026.mp3
python main.py --ticker AAPL --nogui --multi-agent --kafka --qdrant

# From live webcast URL
export EARNINGS_WEBCAST_URL_AAPL=https://investor.apple.com/webcast-url
python main.py --ticker AAPL --nogui --multi-agent --kafka --qdrant
```

### Option H — Investor presentation PDFs

```bash
# Place PDFs in the ticker's folder
mkdir -p pdfs/AAPL
cp ~/Downloads/aapl-investor-day-2025.pdf pdfs/AAPL/

python main.py --ticker AAPL --nogui --multi-agent

# Or point to a custom directory
export PDF_DIR=/path/to/pdfs
python main.py --ticker AAPL --nogui --multi-agent
```

---

## All CLI Options

```
python main.py [OPTIONS]

Options:
  --ticker TICKER         Stock ticker symbol (e.g. AAPL, MSFT)
  --nogui                 Run headless, print JSON to stdout
  --days N                Historical data window in days (default: 365)
  --model MODEL           LLM model (default: gpt-4o-mini)
                          Examples: gpt-4o, ollama/llama3.1,
                                    claude-sonnet-4-6, bedrock/anthropic.claude-3-sonnet
  --base-url URL          API base URL for local LLMs (e.g. http://localhost:11434)
  --multi-agent           Use 49-agent orchestrator instead of single agent
  --verbose               Include per-agent details in output (multi-agent only)
  --kafka                 Enable Kafka event streaming
  --qdrant                Enable Qdrant vector storage
  --react                 Launch React dashboard instead of Streamlit
```

---

## Utility Scripts

### scripts/init_infrastructure.py

Initialises Qdrant collections, Kafka topics, and Unleash feature flags.
Run once after `docker compose up`.

```bash
python scripts/init_infrastructure.py
```

Optional env var overrides:
```bash
QDRANT_HOST=localhost QDRANT_PORT=6333 \
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
UNLEASH_URL=http://localhost:4242 \
python scripts/init_infrastructure.py
```

### scripts/seed_knowledge_graph.py

Seeds Neo4j + NetworkX with GICS sectors, macro factors, and ~80 tickers.
Safe to re-run (all writes use MERGE — no duplicates).

```bash
python scripts/seed_knowledge_graph.py
```

Requires: Neo4j running (`docker compose up -d`) and `neo4j.enabled: true` in `application.yml`.

#### Verifying data in Neo4j

Open Neo4j Browser at `http://localhost:7474` (credentials: `neo4j / neo4j_password`) and run:

```cypher
-- Count all nodes
MATCH (n) RETURN count(n)

-- Check a specific ticker
MATCH (s:Stock {ticker: 'AAPL'})-[r]->(n) RETURN type(r), n.name

-- All stocks in a sector
MATCH (s:Stock)-[:BELONGS_TO_SECTOR]->(sec:Sector {name: 'Information Technology'})
RETURN s.ticker
```

Or via Python:
```bash
python -c "
from infrastructure.knowledge_graph import StockKnowledgeGraph
import json
kg = StockKnowledgeGraph()
print(json.dumps(kg.get_context('AAPL'), indent=2))
"
```

#### Knowledge Graph Explorer (Streamlit Dashboard)

When the `knowledge_graph` feature flag is enabled, a **🧠 Knowledge Graph Explorer** section
appears in the dashboard. Type a natural language question and get an AI-generated answer backed
by a Cypher query against Neo4j.

**50 example questions you can ask:**

Sector queries:
1. Which stocks belong to the Energy sector?
2. How many stocks are in each sector?
3. Which sector has the most stocks?
4. Show me all sectors in the knowledge graph
5. Which stocks are in the Information Technology sector?
6. Which stocks are in the Financials sector?
7. Which stocks are in the Health Care sector?
8. Which stocks are in Consumer Discretionary?
9. Which stocks are in Consumer Staples?
10. Which stocks are in the Utilities sector?

Industry queries:
11. Which stocks are in the Semiconductors industry?
12. Which stocks are in the Pharmaceuticals industry?
13. Which stocks are in the Banks industry?
14. Which stocks are in the Software industry?
15. Which stocks are in the Biotechnology industry?
16. Which industry has the most stocks?
17. Show all industries in the Information Technology sector
18. Show all industries in the Health Care sector
19. Which industry does TSLA belong to?
20. Which industry does JPM belong to?

Macro sensitivity queries:
21. Which sectors are sensitive to interest rates?
22. Which sectors benefit from rising oil prices?
23. Which sectors are hurt by inflation?
24. Which sectors benefit from GDP growth?
25. Which sectors are sensitive to consumer confidence?
26. Which sectors are hurt by rising unemployment?
27. Which sectors benefit from rising commodity prices?
28. Which sectors are sensitive to China's economic growth?
29. Which sectors are negatively affected by trade policy?
30. Which sectors benefit from an aging population?

Stock-specific queries:
31. What sector and industry does AAPL belong to?
32. What macro factors affect NVDA?
33. What macro factors affect NEE?
34. What macro factors affect XOM?
35. What macro factors affect JPM?
36. Is TSLA sensitive to interest rates?
37. Is AMZN a cyclical stock?
38. What are the peers of MSFT in the same industry?
39. What are the peers of AAPL in the same industry?
40. What are the peers of JNJ in the same sector?

Risk / signal queries:
41. Which stocks are rate sensitive?
42. Which stocks are cyclical?
43. Which sectors have the strongest sensitivity to interest rates?
44. Which macro factor has the most sector dependencies?
45. Which sectors have positive sensitivity to GDP growth?
46. Which sectors have negative sensitivity to inflation?
47. Which sectors are most sensitive to oil prices?
48. Show macro factors with strength greater than 0.8 for any sector
49. Which sectors have mixed sensitivity to inflation?
50. Which sectors are defensively positioned against economic downturns?

Additional sector and industry queries:
51. Which stocks are in the Real Estate sector?
52. How many industries exist in the Health Care sector?
53. Which sector has the fewest stocks?
54. Show all stocks in the Materials sector
55. Which stocks are in the Industrials sector?
56. Show me all stocks grouped by sector
57. Which sector contains the most industries?
58. How many stocks are in the Communication Services sector?
59. Show me all stocks in the Energy sector
60. Which stocks are in the Utilities sector and have more than one macro sensitivity?

Additional industry queries:
61. Which stocks are in the Insurance industry?
62. Which stocks are in the Electric Vehicles industry?
63. Which stocks are in the Payment Processing industry?
64. Which stocks are in the Asset Management industry?
65. Show me all industries that belong to the Financials sector
66. Which industry has the most stocks in the Health Care sector?
67. Which stocks are in the Aerospace and Defense industry?
68. Show me all stocks in the Internet Retail industry?
69. Which stocks are in the Gold Mining industry?
70. Show me industries in the Consumer Staples sector

Additional macro sensitivity queries:
71. Which sectors are most sensitive to advertising spend?
72. Which sectors benefit from innovation cycles?
73. Which sectors are hurt by rising credit spreads?
74. Which sectors have the most macro factor sensitivities?
75. Which macro factor affects the most sectors?
76. Which sectors have both positive and negative macro sensitivities?
77. What is the average macro sensitivity strength across all sectors?
78. Which sectors are sensitive to manufacturing PMI?
79. Which sectors have a sensitivity strength above 0.9?
80. Which sectors are affected by regulatory risk?

Additional stock-specific queries:
81. What macro factors affect META?
82. What macro factors affect UNH?
83. What macro factors affect LIN?
84. What sector does COST belong to?
85. What industry does NEM belong to?
86. Is NEE a cyclical stock?
87. Is DOW sensitive to commodity prices?
88. What are the peers of JPM in the same industry?
89. What are the peers of LLY in the same sector?
90. What macro factors are most relevant for XOM?

Additional risk and signal queries:
91. Which stocks are both rate sensitive and have high macro sensitivity strength?
92. Which sectors would benefit most from a GDP recovery?
93. Which sectors are most exposed to inflation risk?
94. Which sectors would be hurt most by a China slowdown?
95. Which stocks belong to defensive sectors?
96. Which sectors have the weakest sensitivity to interest rates?
97. Show all macro factors and how many sectors are sensitive to each
98. Which sectors have positive sensitivity to oil prices?
99. Which stocks are in sectors sensitive to consumer confidence?
100. What is the full macro sensitivity profile for the Financials sector?

### scripts/scheduled_buy_now_report.py

Runs a buy-now analysis for a ticker and sends a PDF report by email.
Designed to be called by an n8n cron job or any scheduler.

```bash
python scripts/scheduled_buy_now_report.py \
  --ticker AAPL \
  --email recipient@example.com \
  --days 30
```

Required env vars:
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
OPENAI_API_KEY=sk-...
```

### scripts/launch_n8n_workflow.py

Triggers or manages n8n workflows via the n8n REST API.

```bash
python scripts/launch_n8n_workflow.py \
  --url http://localhost:5678 \
  --api-key your-n8n-api-key \
  --workflow-id <workflow-id>
```

Required env vars:
```bash
N8N_URL=http://localhost:5678
N8N_API_KEY=your-n8n-api-key
```

---

## PostgreSQL Explorer (Natural Language Queries)

When PostgreSQL is enabled (`postgres.enabled: true` in `application.yml`), a **🗄️ PostgreSQL Explorer**
section appears in the Streamlit dashboard. Type a natural language question and get an AI-generated
answer backed by a SQL query against the database.

Three tables are available:
- `stock_prices_daily` — daily OHLCV price history per ticker
- `stock_watchlist` — tickers saved to the watchlist
- `stock_schedule_configs` — scheduled analysis job configurations

**Example questions you can ask:**

Stock price queries:
1. Which ticker has the most price history?
2. What is the latest closing price for AAPL?
3. Show me TSLA prices from the last 30 days
4. Which ticker has the highest average closing price?
5. Which ticker has the lowest average closing price?
6. What is the highest price NVDA has ever reached?
7. What is the lowest price AAPL has ever reached?
8. Show me the top 10 tickers by average volume
9. Which tickers have data for more than 365 days?
10. What is the average daily volume for MSFT?
11. Show me AAPL open and close prices for the last 7 days
12. Which day had the highest volume for TSLA?
13. Show me the most recent price record for each ticker
14. What is the price range (high minus low) for NVDA this month?
15. Which ticker had the biggest single-day price gain?
16. Which ticker had the biggest single-day price drop?
17. Show me all tickers that have data from before 2023
18. How many total price records are in the database?
19. What is the average closing price of AAPL over the last 90 days?
20. Show me the 5 most recently updated tickers

Price comparison queries:
21. Which ticker has a higher average close — AAPL or MSFT?
22. Compare the average volume of AAPL and TSLA
23. Which tickers have closing prices above $500?
24. Which tickers have closing prices below $50?
25. Show me tickers where the latest close is higher than the open
26. Which ticker has the most volatile price history (highest standard deviation of close)?
27. Show me the top 5 tickers by total trading volume
28. Which ticker has the highest price-to-open ratio on average?
29. Show me tickers where close is consistently higher than open
30. What percentage of days did AAPL close higher than it opened?

Watchlist queries:
31. Which tickers are in my watchlist?
32. How many tickers are in the watchlist?
33. Which watchlist tickers are currently enabled?
34. Which watchlist tickers are disabled?
35. When was each ticker added to the watchlist?
36. Which ticker was most recently added to the watchlist?
37. Which ticker was added to the watchlist first?
38. How many tickers were added to the watchlist from the dashboard?
39. Show me all watchlist tickers sorted by creation date
40. Are there any watchlist tickers with no price data?

Schedule queries:
41. What schedules are currently enabled?
42. Which schedules are disabled?
43. When is the next scheduled analysis run?
44. Which schedule last ran successfully?
45. Which schedules have errors in the last run?
46. Show me all schedules sorted by next run time
47. How many schedules are configured for pre-market?
48. Which schedule runs most frequently?
49. Show me the last error message for any failed schedule
50. Which schedules are configured to run on weekdays only?

Cross-table queries:
51. Which watchlist tickers also have price history in the database?
52. Which watchlist tickers have no price data at all?
53. Show me the latest price for each ticker in the watchlist
54. How many days of price history exist for each watchlist ticker?
55. Which watchlist ticker has the highest latest closing price?
56. Which watchlist ticker has the lowest latest closing price?
57. Show me the average closing price for each enabled watchlist ticker
58. Which enabled watchlist tickers have price data from today?
59. How many price records exist per watchlist ticker?
60. Show me watchlist tickers sorted by average daily volume

Additional price analysis queries:
61. What is the 52-week high for AAPL?
62. What is the 52-week low for TSLA?
63. Which ticker has gained the most in the last 30 days?
64. Which ticker has lost the most in the last 30 days?
65. Show me the daily closing prices for NVDA this year
66. What is the average spread between high and low for MSFT?
67. Which tickers have had a volume spike in the last 7 days?
68. Show me all tickers with more than 1 million average daily volume
69. Which ticker had the highest close yesterday?
70. What is the month-over-month price change for AMZN?
71. Show me tickers where close price dropped more than 5% in a single day
72. Which tickers have been consistently above their 50-day average close?
73. Show me the top 5 tickers by highest single-day volume ever
74. What is the all-time average closing price for JPM?
75. Show me price records added in the last 24 hours
76. Which tickers have the fewest price records?
77. What is the total number of trading days tracked per ticker?
78. Show me AAPL prices where volume exceeded 100 million
79. Which ticker had the most stable price over the last 90 days?
80. Show me all price records where close is lower than open by more than 3%

Additional watchlist and schedule queries:
81. How many tickers were added to the watchlist this month?
82. Show me all disabled watchlist tickers
83. Which schedule has the earliest run time?
84. Which schedule has run the most recently?
85. Show me all schedules configured to email reports
86. Which schedules use gpt-4o as the model?
87. How many schedules run pre-market vs intraday?
88. Show me schedules that have never run successfully
89. What is the most common timezone configured in schedules?
90. Which schedule has the largest top_n value configured?
91. Show me all watchlist tickers added before this year
92. Which schedules have a last_error recorded?
93. How many unique email addresses are configured across all schedules?
94. Show me all schedules with weekdays_only set to false
95. Which watchlist tickers have been enabled the longest?
96. Show me the average days parameter across all schedule configs
97. Which schedule was most recently updated?
98. How many schedules are configured per session type?
99. Show me all tickers in the watchlist that have price data from the last 7 days
100. What is the total volume traded across all tickers in the last 30 days?

---

## Qdrant Semantic Search (Natural Language Queries)

When Qdrant is enabled (`qdrant.enabled: true` in `application.yml`), a **🔍 Qdrant Semantic Search**
section appears in the Streamlit dashboard. Unlike SQL or Cypher, Qdrant uses **semantic similarity** —
your question is converted to a vector embedding and matched against the most relevant stored documents.

Available collections searched automatically based on your question:
- `stock_news` — recent news articles
- `sec_filings` — 10-K, 10-Q, 8-K filings
- `earnings_transcripts` — earnings call transcripts
- `investor_presentations` — investor presentation PDFs
- `zacks_data`, `tipranks_data`, `morningstar_data` — analyst research
- `seekingalpha_data`, `gurufocus_data` — independent analysis
- `reddit_data`, `stocktwits_data` — social sentiment
- `insider_institutional_data` — insider and hedge fund activity
- `options_flow_data` — options flow and unusual activity
- `cnbc_data`, `bloomberg_data`, `wsj_data`, `barrons_data` — financial media

**100 example questions you can ask:**

News queries:
1. What is the latest news about AAPL?
2. What negative news has been published about TSLA recently?
3. Are there any merger or acquisition rumors for MSFT?
4. What news is driving NVDA stock movement?
5. Has there been any regulatory news affecting Meta?
6. What supply chain news is affecting semiconductor stocks?
7. Are there any CEO changes reported in the news?
8. What news is affecting bank stocks this week?
9. Has there been any FDA approval news for pharma stocks?
10. What geopolitical news is affecting energy stocks?
11. What news is there about AI investments in tech stocks?
12. Has any major stock announced a stock buyback recently?
13. What news is driving volatility in the market today?
14. Are there any dividend cut announcements in the news?
15. What news is there about tariffs affecting consumer stocks?
16. What infrastructure spending news affects industrial stocks?
17. Has there been any data breach news affecting tech companies?
18. What news is there about electric vehicle demand?
19. Are there any layoff announcements affecting tech stocks?
20. What news is there about interest rate decisions affecting financials?

SEC filings queries:
21. What risks did AAPL mention in their latest 10-K?
22. What did TSLA say about competition in their annual filing?
23. What revenue guidance did MSFT provide in their 10-Q?
24. What litigation risks did JPM disclose in their filings?
25. What did NVDA say about supply constraints in their SEC filing?
26. What did management say about debt levels in recent filings?
27. What acquisitions did GOOGL disclose in their 8-K?
28. What did Amazon say about their cloud business in their 10-K?
29. What cybersecurity risks were disclosed in recent filings?
30. What did META say about regulatory pressure in their annual report?
31. What did XOM disclose about environmental liabilities?
32. What executive compensation details were disclosed in proxy filings?
33. What did UNH say about medical cost trends in their 10-Q?
34. What share repurchase programs were announced in 8-K filings?
35. What did AMZN say about capital expenditure plans in their 10-K?

Earnings call transcript queries:
36. What did AAPL management say about iPhone demand on the earnings call?
37. What guidance did TSLA provide on the last earnings call?
38. What did NVDA say about AI chip demand on their earnings call?
39. What did JPM management say about interest rate outlook?
40. What questions did analysts ask on the MSFT earnings call?
41. What did management say about margins on the last earnings call?
42. What cost-cutting measures did META discuss on their earnings call?
43. What did AMZN say about AWS growth on the earnings call?
44. What risks did management highlight on the GOOGL earnings call?
45. What did the CFO say about capital allocation on the earnings call?
46. What did TSLA say about Cybertruck production on the earnings call?
47. What international expansion plans did SBUX discuss on their call?
48. What did AAPL say about services revenue growth on the earnings call?
49. What did management say about hiring plans on the last earnings call?
50. What did NVDA say about data center demand outlook?

Analyst and research queries:
51. What is the analyst consensus on AAPL?
52. What price target did analysts set for NVDA?
53. What did Morningstar say about TSLA valuation?
54. What is the Zacks rating for JPM?
55. What did Seeking Alpha analysts say about MSFT growth?
56. Which stocks have the most analyst upgrades recently?
57. What did TipRanks analysts say about META earnings?
58. What is the bull case for AMZN according to analysts?
59. What valuation concerns did analysts raise about NVDA?
60. What did GuruFocus say about AAPL intrinsic value?
61. What is the bear case for TSLA from Barron's?
62. What did Bloomberg analysts say about Fed rate expectations?
63. What did WSJ report about GOOGL antitrust concerns?
64. What is the CNBC analyst view on energy sector stocks?
65. What did MarketWatch say about consumer spending trends?

Social sentiment queries:
66. What is the Reddit sentiment on GME?
67. Are retail investors bullish or bearish on TSLA on StockTwits?
68. What stocks are trending on WallStreetBets right now?
69. What are retail traders saying about NVDA options?
70. Is there short squeeze chatter about any stocks on Reddit?
71. What is the social media sentiment on AAPL after earnings?
72. What meme stocks are being discussed on Reddit this week?
73. Are there any unusual retail interest spikes on StockTwits?
74. What are traders saying about the Fed rate decision on Reddit?
75. What is the overall market sentiment on social media today?
76. What stocks do Reddit users consider undervalued?
77. Is there bearish sentiment building on any large-cap stocks?
78. What options plays are being discussed on WallStreetBets?
79. Are there any stocks with unusual bullish StockTwits activity?
80. What sectors are retail investors rotating into according to Reddit?

Insider and institutional queries:
81. Which insiders have been buying their own company stock recently?
82. Which insiders have been selling large amounts of stock?
83. What hedge funds have recently increased their AAPL position?
84. Which institutional investors are exiting TSLA?
85. What stocks are Cathie Wood and ARK Invest buying?
86. Which stocks have had the most insider buying this quarter?
87. What did Warren Buffett recently buy or sell?
88. Which small-cap stocks are seeing new institutional interest?
89. Are any insiders buying ahead of earnings announcements?
90. Which stocks have both insider buying and analyst upgrades?

Options flow queries:
91. What unusual options activity is there on AAPL?
92. Which stocks have the highest put/call ratio today?
93. Are there any large call sweeps on NVDA?
94. Which stocks are showing bullish options flow?
95. Which stocks are showing bearish options flow?
96. What is the implied volatility trend for TSLA options?
97. Are there any large block options trades on SPY?
98. Which stocks have the most out-of-the-money call buying?
99. What dark pool activity has been detected for MSFT?
100. Which stocks have unusual options volume compared to open interest?

---

## Kafka Stream Explorer (Natural Language Queries)

When Kafka is enabled (`kafka.enabled: true` in `application.yml`), a **📨 Kafka Stream Explorer**
section appears in the Streamlit dashboard. Unlike SQL or Cypher, Kafka is a message stream —
queries inspect topic metadata (partitions, offsets, message counts) or sample recent messages.

The LLM automatically picks one of three actions based on your question:
- `list_topics` — show all topics and their descriptions
- `topic_stats` — partition count, begin/end offsets, total message count for a topic
- `sample_messages` — read the latest N messages from a topic

Available topics:
- `stock-prices` — real-time OHLCV price updates
- `stock-news` — news articles from NewsAgent
- `sec-filings` — SEC EDGAR filing summaries
- `earnings-call-live` — live earnings call transcript chunks
- `zacks-data`, `tipranks-data`, `morningstar-data` — analyst data
- `reddit-data`, `stocktwits-data` — social sentiment
- `insider-institutional-data` — insider and hedge fund activity
- `options-flow-data` — options flow and unusual activity
- `cnbc-data`, `bloomberg-data`, `wsj-data`, `barrons-data` — financial media

**100 example questions you can ask:**

Topic discovery and metadata queries:
1. List all available Kafka topics
2. How many Kafka topics exist in total?
3. Which topics are currently active?
4. What is the purpose of each Kafka topic?
5. Which topics have the most messages?
6. Which topics have the fewest messages?
7. Which topics have zero messages?
8. How many partitions does the stock-news topic have?
9. What is the current offset for the stock-prices topic?
10. Show me the beginning and end offsets for all topics

Stock price stream queries (stock-prices):
11. How many price messages are in the stock-prices topic?
12. Show me the latest price messages from the stream
13. What is the most recently streamed stock price?
14. How many price updates have been published today?
15. Show me recent price messages for any ticker
16. What tickers have had price updates streamed recently?
17. What is the latest streamed closing price for AAPL?
18. How many price records exist per partition in stock-prices?
19. Are there any price messages in the stream right now?
20. Show me the last 10 price stream messages

News stream queries (stock-news):
21. How many news messages are in the stock-news topic?
22. Show me the latest news articles from the stream
23. What is the most recent news item published to Kafka?
24. How many news articles have been streamed?
25. Are there any news messages about TSLA in the stream?
26. Show me the latest 5 news stream messages
27. What news topics are being streamed right now?
28. How many news messages are waiting to be consumed?
29. What is the offset lag in the stock-news topic?
30. Show me recent news stream messages for tech stocks

SEC filings stream queries (sec-filings):
31. How many SEC filing messages are in the stream?
32. Show me the latest SEC filing messages
33. What filings have been streamed recently?
34. How many 8-K filings have been published to Kafka?
35. Are there any 10-K filings in the sec-filings stream?
36. What is the current offset in the sec-filings topic?
37. Show me the most recent SEC filing message payload
38. How many SEC filing messages exist per partition?
39. Are there any new filings waiting to be consumed?
40. Show me the last 5 messages from the sec-filings topic

Earnings call stream queries (earnings-call-live):
41. Are there any live earnings call chunks in the stream?
42. Show me the latest earnings call transcript chunks
43. How many earnings call messages have been streamed?
44. What is the current offset in the earnings-call-live topic?
45. Are there any earnings call messages from today?
46. Show me the most recent earnings call transcript chunk
47. How many partitions does the earnings-call-live topic have?
48. What is the beginning offset for the earnings-call-live topic?
49. Are there any unprocessed earnings call chunks waiting?
50. Show me all earnings call messages in the stream

Analyst data stream queries (zacks, tipranks, morningstar):
51. How many messages are in the zacks-data topic?
52. Show me the latest TipRanks analyst messages
53. How many Morningstar data messages have been streamed?
54. Are there any analyst rating updates in the stream?
55. What is the offset in the tipranks-data topic?
56. Show me recent Seeking Alpha messages from the stream
57. How many GuruFocus messages are in the stream?
58. Are there any analyst upgrade messages waiting to be consumed?
59. What is the latest analyst data message payload?
60. How many analyst data topics have messages?

Social sentiment stream queries (reddit, stocktwits):
61. How many Reddit sentiment messages are in the stream?
62. Show me the latest StockTwits messages
63. Are there any WallStreetBets messages in the stream?
64. How many social sentiment messages have been published?
65. What is the current offset in the reddit-data topic?
66. Show me recent social sentiment stream messages
67. Are there any unusual sentiment spikes in the stream?
68. How many StockTwits messages exist per partition?
69. What is the latest Reddit message payload in the stream?
70. Are there any social media messages from the last hour?

Financial media stream queries (cnbc, bloomberg, wsj):
71. How many CNBC news messages are in the stream?
72. Show me the latest Bloomberg data messages
73. How many WSJ articles have been streamed?
74. Are there any Barron's messages in the stream?
75. What is the current offset in the bloomberg-data topic?
76. Show me the most recent MarketWatch stream messages
77. How many financial media topics have messages?
78. What is the latest CNBC message payload?
79. Are there any Fox Business messages waiting to be consumed?
80. Show me recent messages from all financial media topics

Options flow stream queries (options-flow-data):
81. How many options flow messages are in the stream?
82. Show me the latest options flow messages
83. Are there any unusual options activity messages in the stream?
84. What is the current offset in the options-flow-data topic?
85. How many partitions does the options-flow-data topic have?
86. Show me the most recent options flow message payload
87. Are there any put/call ratio messages in the stream?
88. How many options flow messages have been published today?
89. What is the beginning offset for the options-flow-data topic?
90. Are there any large block options messages in the stream?

Insider and institutional stream queries:
91. How many insider trading messages are in the stream?
92. Show me the latest insider-institutional-data messages
93. Are there any hedge fund activity messages in the stream?
94. What is the current offset in the insider-institutional-data topic?
95. How many insider trading messages have been streamed?
96. Show me the most recent insider trading message payload
97. Are there any institutional buying messages waiting to be consumed?
98. How many messages exist across all insider and institutional topics?
99. What is the total message count across all Kafka topics?
100. Which Kafka topic has had the most activity overall?

---

## Unusual Options Screener

The **🎯 Unusual Options Screener** section in the Streamlit dashboard lets you filter options contracts by price and unusual activity across a single ticker or your entire watchlist.

**Controls:**
- **Max option price** — only show contracts at or below this premium (e.g. $0.25)
- **Option type** — calls only, puts only, or both
- **Min volume** — minimum contracts traded today
- **Min vol/OI ratio** — volume ÷ open interest; values above 1.0 mean more volume than all existing open interest (extremely unusual)
- **Expirations to scan** — how many nearest expiry dates to include
- **Scan entire watchlist** — run across all watchlist tickers at once

**Color coding in results:**
- 🟠 Orange = vol/OI ≥ 2x (extremely unusual — likely institutional sweep)
- 🟡 Yellow = vol/OI ≥ 1x (unusual activity)

**100 example questions / filter combinations:**

Cheap options by price:
1. Show me all options below $0.25
2. Find options priced under $0.10
3. What options are available for under $0.50?
4. Show me the cheapest calls available right now
5. Find puts priced below $0.15
6. What options cost less than $1?
7. Show me options under $0.05 with any volume
8. Find calls below $0.20 on AAPL
9. Show me puts under $0.30 on TSLA
10. What are the cheapest options on NVDA?

Unusual activity — high vol/OI ratio:
11. Show options where volume exceeds open interest
12. Find options with vol/OI ratio above 2x
13. What options have more volume than open interest today?
14. Show me the most unusually active cheap options
15. Find calls with vol/OI above 3x priced under $0.25
16. What puts have extremely unusual volume today?
17. Show options where vol/OI is above 5x
18. Find options with vol/OI above 1x under $0.50
19. What options show institutional sweep activity today?
20. Show me options where volume is 10x the open interest

High volume options:
21. Find options with volume above 10,000 contracts
22. Show me the highest volume cheap options today
23. What calls have more than 5,000 contracts traded?
24. Find puts with volume above 50,000
25. Show options with at least 1,000 contracts traded under $0.25
26. What are the most actively traded cheap options?
27. Find options with volume above 100,000 today
28. Show me calls with more than 20,000 contracts traded under $0.50
29. What options have unusually high volume on low open interest?
30. Find options where volume spiked above normal levels

By ticker — single stock:
31. Show me unusual cheap options for AAPL
32. Find calls under $0.25 on TSLA
33. What puts are available under $0.50 on NVDA?
34. Show me unusual options activity on META
35. Find cheap calls on MSFT expiring this week
36. What options under $0.10 exist for AMZN?
37. Show me unusual put activity on JPM under $0.25
38. Find calls under $0.20 on AMD
39. What cheap options are available on GOOGL?
40. Show me unusual options on SPY under $0.25

By expiration:
41. Find cheap options expiring this week
42. Show me unusual options expiring within 7 days
43. What cheap calls expire in the next 30 days?
44. Find puts under $0.25 expiring next month
45. Show me options in the nearest 2 expirations only
46. What options under $0.50 have the soonest expiry?
47. Find unusual cheap options expiring in 3 expirations
48. Show me calls expiring this Friday under $0.25
49. What cheap puts expire within the next 2 weeks?
50. Find options with the highest vol/OI in the nearest expiration

By option type:
51. Show me only unusual cheap calls
52. Find puts under $0.25 with unusual activity
53. What calls show unusual volume under $0.50?
54. Show me all unusual puts across my watchlist
55. Find calls under $0.10 with vol/OI above 1x
56. What puts have vol/OI above 2x under $0.25?
57. Show me calls with high volume and low price
58. Find puts under $0.15 with more volume than open interest
59. What calls are priced between $0.10 and $0.25 with unusual activity?
60. Show me only out-of-the-money puts under $0.25

Watchlist scanning:
61. Scan my entire watchlist for options under $0.25
62. Find unusual cheap options across all my watchlist tickers
63. What options under $0.50 show unusual activity in my watchlist?
64. Scan watchlist for calls under $0.25 with vol/OI above 1x
65. Find the most unusually active cheap puts across my watchlist
66. Show me all cheap options with high volume across my watchlist
67. What watchlist stocks have unusual call activity under $0.25?
68. Scan watchlist for puts under $0.10 with any unusual activity
69. Find the top 10 most unusual cheap options across all my tickers
70. Show me calls under $0.25 for every ticker in my watchlist

Implied volatility:
71. Show me cheap options with high implied volatility
72. Find options under $0.25 with IV above 100%
73. What cheap calls have the highest implied volatility?
74. Show me puts under $0.25 with IV above 80%
75. Find unusual options with IV spike above 150%
76. What cheap options have IV above 200%?
77. Show me calls with unusually high IV under $0.50
78. Find puts where IV is elevated and price is under $0.25
79. What options combine low price with high IV and unusual volume?
80. Show me cheap options where IV suggests a big move expected

In-the-money vs out-of-the-money:
81. Show me in-the-money calls under $0.25
82. Find out-of-the-money puts under $0.10 with unusual volume
83. What in-the-money options are under $0.50 with high activity?
84. Show me deep out-of-the-money calls under $0.05
85. Find ITM puts under $0.25 with vol/OI above 1x
86. What OTM calls under $0.25 have the highest volume?
87. Show me near-the-money options under $0.25 with unusual activity
88. Find OTM puts with unusual volume under $0.10
89. What ITM calls are available under $0.50 with high vol/OI?
90. Show me options close to the current stock price under $0.25

Combined filters — advanced screening:
91. Find calls under $0.25 with volume above 10,000 and vol/OI above 2x
92. Show puts under $0.10 with IV above 100% and volume above 5,000
93. Find unusual cheap options across my watchlist in the nearest expiration only
94. Show calls under $0.50 with vol/OI above 3x and volume above 50,000
95. Find puts under $0.25 expiring this week with unusual activity
96. Show me calls under $0.10 with the highest vol/OI ratio today
97. Find options under $0.25 where volume is 5x the open interest
98. Show unusual puts across my watchlist under $0.15 with volume above 1,000
99. Find the single most unusual cheap option available right now
100. Show me everything — all options under $0.25 with any unusual activity across my entire watchlist

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Entry Points                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐         │
│   │ CLI (main.py) │  │ REST API      │  │ Streamlit     │  │ React         │         │
│   │ --ticker AAPL │  │ (api.py)      │  │ Dashboard     │  │ Dashboard     │         │
│   │ --multi-agent │  │ FastAPI       │  │ (default)     │  │ (--react)     │         │
│   └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘         │
│           │                  │                  │                  │                  │
│           └──────────────────┴──────────────────┴──────────────────┘                  │
│                                      ▼                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        ┌───────────────────┐                 ┌───────────────────────┐
        │  Single-Agent     │                 │  Multi-Agent Mode     │
        │  StockSignalAgent │                 │  OrchestratorAgent    │
        └───────────────────┘                 └───────────┬───────────┘
                                                          │
┌─────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────┐
│                                                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              47 Specialized Data Source Agents                                                │ │
│  ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                                                               │ │
│  │   Core Analysis          Analyst Ratings        Financial Data       News & Media        Social & Alt Data   │ │
│  │   ─────────────          ──────────────         ──────────────       ────────────        ─────────────────   │ │
│  │   • TechnicalAgent       • ZacksAgent           • MorningstarAgent   • CNBCAgent         • RedditAgent       │ │
│  │   • NewsAgent            • TipRanksAgent        • GuruFocusAgent     • BloombergAgent    • StockTwitsAgent   │ │
│  │   • SECFilingAgent       • SeekingAlphaAgent    • FactSetAgent       • WSJAgent          • XTwitterAgent     │ │
│  │   • SentimentAgent       • MotleyFoolAgent      • YahooFinanceAgent  • MarketWatchAgent  • OptionsFlowAgent  │ │
│  │                          • MarketBeatAgent      • YChartsAgent       • BarronsAgent      • FacebookAgent     │ │
│  │   Insider Data           • StockStoryAgent      • KoyfinAgent        • FoxBusinessAgent  • InstagramAgent    │ │
│  │   ───────────                                   • ValueLineAgent                                              │ │
│  │   • InsiderMonkeyAgent   Technical Charts       • MacrotrendsAgent   ETF Research                            │ │
│  │   • QuiverQuantAgent     ───────────────        • CapitalIQAgent     ────────────                            │ │
│  │   • DataromaAgent        • TradingViewAgent     • RefinitivAgent     • ETFComAgent                           │ │
│  │   • OpenInsiderAgent     • StockRoverAgent                           • ETFDBAgent                            │ │
│  │   • WhaleWisdomAgent     • SimplyWallStAgent                         • GlobalXETFAgent                       │ │
│  │   • InsiderInstAgent     • AlphaSpreadAgent                          • ARKInvestAgent                        │ │
│  │                                                                      • MorningstarETF                        │ │
│  │                                                                                                               │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                          │                                                        │
│                                                          ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    Machine Learning Module                                                    │ │
│  ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                                                               │ │
│  │   ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐                      │ │
│  │   │   LSTM Price Predictor  │  │  XGBoost Signal         │  │  Ensemble Scorer        │                      │ │
│  │   │   (ml/price_predictor)  │  │  Classifier             │  │  (ml/ensemble_scorer)   │                      │ │
│  │   ├─────────────────────────┤  │  (ml/signal_classifier) │  ├─────────────────────────┤                      │ │
│  │   │ • 5-day price forecast  │  ├─────────────────────────┤  │ • Weighted agent voting │                      │ │
│  │   │ • Trend detection       │  │ • BUY/SELL/HOLD signal  │  │ • Confidence scoring    │                      │ │
│  │   │ • TensorFlow/Keras      │  │ • 14 technical features │  │ • Signal aggregation    │                      │ │
│  │   │ • Momentum fallback     │  │ • RandomForest fallback │  │ • Historical calibration│                      │ │
│  │   └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘                      │ │
│  │                                                                                                               │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                          │                                                        │
│                                                          ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                    Infrastructure Layer                                                       │ │
│  ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                                                               │ │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │ │
│  │   │    Kafka     │  │   Qdrant     │  │  Embeddings  │  │   Langfuse   │  │ LLM Provider │                   │ │
│  │   │  (Streaming) │  │ (Vector DB)  │  │  (384-dim)   │  │ (Observ.)    │  │ (LiteLLM)    │                   │ │
│  │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘                   │ │
│  │                                                                                                               │ │
│  │   ┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐   │ │
│  │   │                                    Feature Flags                                                      │   │ │
│  │   ├──────────────────────────────────────────────────────────────────────────────────────────────────────┤   │ │
│  │   │   Local (APP_ENV=local)              │    AWS (APP_ENV=qa/stg/prod)                                  │   │ │
│  │   │   ┌────────────────────────┐         │    ┌────────────────────────┐                                 │   │ │
│  │   │   │  Unleash Server        │         │    │  AWS AppConfig         │                                 │   │ │
│  │   │   │  (Docker, port 4242)   │         │    │  (Terraform managed)   │                                 │   │ │
│  │   │   └────────────────────────┘         │    └────────────────────────┘                                 │   │ │
│  │   └──────────────────────────────────────────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                                                               │ │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              External Data Sources                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ • yfinance (OHLCV, News, Fundamentals)    • SEC EDGAR API (10-K, 10-Q, 8-K filings)    │
│ • Reddit/StockTwits APIs (Social)          • Options Flow Data (Unusual Activity)       │
│ • LLM APIs (OpenAI, Claude, Ollama)        • Kafka/MSK (Event Streaming)                │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Agentic Lifecycle Pattern                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐                   │
│    │   PLAN   │ ───▶ │ PERCEIVE │ ───▶ │  REASON  │ ───▶ │   ACT    │                   │
│    │          │      │          │      │          │      │          │                   │
│    │ Define   │      │ Fetch    │      │ Compute  │      │ Generate │                   │
│    │ steps    │      │ data     │      │ signal   │      │ output   │                   │
│    └──────────┘      └──────────┘      └──────────┘      └──────────┘                   │
│                                                                                          │
│    All agents extend AgenticAIBase and follow this lifecycle                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              LLM Provider Options                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                     │
│   │  Cloud LLMs     │    │  Self-Hosted    │    │  Enterprise     │                     │
│   ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                     │
│   │ • OpenAI GPT-4o │    │ • Ollama        │    │ • Azure OpenAI  │                     │
│   │ • Claude 4.6    │    │ • Llama 3.1     │    │ • AWS Bedrock   │                     │
│   │ • Gemini 2.0    │    │ • Mistral       │    │ • GCP Vertex AI │                     │
│   │ • Groq          │    │ • CodeLlama     │    │                 │                     │
│   └─────────────────┘    └─────────────────┘    └─────────────────┘                     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Data Source Agents (47 Total)                               │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  Analyst Ratings          Financial Data         Social/News        Insider Data        │
│  ─────────────────        ──────────────         ───────────        ────────────        │
│  • ZacksAgent             • MorningstarAgent     • CNBCAgent        • InsiderMonkey     │
│  • TipRanksAgent          • GuruFocusAgent       • BloombergAgent   • QuiverQuant       │
│  • SeekingAlphaAgent      • FactSetAgent         • WSJAgent         • DataromaAgent     │
│  • MotleyFoolAgent        • CapitalIQAgent       • MarketWatch      • OpenInsider       │
│  • MarketBeatAgent        • RefinitivAgent       • FoxBusiness      • WhaleWisdom       │
│  • StockStoryAgent        • MacrotrendsAgent     • BarronsAgent     • InsiderInst.      │
│                           • YChartsAgent         • XTwitterAgent                        │
│  Technical/Charts         • KoyfinAgent          • FacebookAgent    ETF Research        │
│  ───────────────          • ValueLineAgent       • InstagramAgent   ────────────        │
│  • TradingViewAgent       • YahooFinanceAgent                       • ETFComAgent       │
│  • StockRoverAgent                               Social & Alt Data  • ETFDBAgent        │
│  • SimplyWallStAgent                             ────────────────   • GlobalXETF        │
│  • AlphaSpreadAgent                              • RedditAgent      • ARKInvest         │
│                                                  • StockTwitsAgent  • MorningstarETF    │
│  ML Components                                   • OptionsFlowAgent                     │
│  ─────────────                                                                          │
│  • PricePredictor (LSTM)                                                                │
│  • SignalClassifier (XGBoost)                                                           │
│  • EnsembleScorer                                                                       │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                Signal Flow                                               │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   Each Agent Output:              ML Analysis:               Final Synthesis:            │
│   ┌────────────────────┐         ┌────────────────────┐     ┌────────────────────┐      │
│   │ signal: BULLISH/   │         │ LSTM Price Predict │     │ Weighted aggregate │      │
│   │         BEARISH/   │  ──────▶│ XGBoost Classifier │────▶│ of all agent       │      │
│   │         NEUTRAL    │         │ Ensemble Scorer    │     │ signals via LLM    │      │
│   │ confidence: 0.0-1.0│         │                    │     │                    │      │
│   │ data: {...}        │         │ 5-day forecast     │     │ Final: BUY/SELL/   │      │
│   └────────────────────┘         │ confidence score   │     │        HOLD        │      │
│                                  └────────────────────┘     └────────────────────┘      │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           Dashboard Options (Streamlit / React)                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   Streamlit (default: python main.py)        React (python main.py --react)             │
│   ─────────────────────────────────          ─────────────────────────────              │
│   • Server-rendered Python UI                • Client-side SPA (TypeScript)             │
│   • Built-in state management                • Vite + Tailwind CSS                      │
│   • Direct Python integration                • Connects to FastAPI backend              │
│   • Best for: rapid prototyping              • Best for: production deployment          │
│                                                                                          │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│   │  Stock Info     │  │ Technical Chart │  │  Agent Signals  │  │  ML Analysis    │   │
│   │  • Price, Vol   │  │ • Price + SMA   │  │ • 47 agent view │  │ • LSTM forecast │   │
│   │  • PE, PEG, EPS │  │ • RSI, MACD     │  │ • Confidence    │  │ • XGBoost signal│   │
│   │  • 52-week H/L  │  │ • Bollinger     │  │ • Reasoning     │  │ • Ensemble score│   │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│   │                           Report Actions                                         │   │
│   ├─────────────────────────────────────────────────────────────────────────────────┤   │
│   │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │   │
│   │  │  Download PDF   │  │   Send Text     │  │   Send Email    │                  │   │
│   │  │  (reportlab)    │  │   (Twilio SMS)  │  │   (SMTP)        │                  │   │
│   │  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │   │
│   │  Buttons enabled after analysis completes                                        │   │
│   └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│   Features: Watchlist (20 max), Auto-refresh, Quick Picks, Analysis Period 3mo-10yr      │
│                                                                                          │
│   AWS Deployment: React frontend → S3 + CloudFront (static hosting)                     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## AWS Deployment Architecture

This section covers multiple AWS deployment options, from enterprise-grade to simple serverless approaches.

### Deployment Options Overview

| Option | Complexity | Monthly Cost | Best For |
|--------|------------|--------------|----------|
| **EKS Fargate + Bedrock** | High | $$$-$$$$ | Enterprise, HA, compliance |
| **App Runner** | Low | $$ | Startups, MVPs, quick deploys |
| **Lambda + API Gateway** | Low | $ | Low traffic, batch processing |

---

### Option 1: Enterprise (EKS Fargate + Amazon Bedrock)

Full-featured deployment with serverless containers, native AWS LLM, and complete observability.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    AWS Cloud (Primary Region: us-east-1)                     │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                                   Edge Layer                                        │    │
│   ├────────────────────────────────────────────────────────────────────────────────────┤    │
│   │                                                                                     │    │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │    │
│   │  │   Route 53   │───▶│  CloudFront  │───▶│ API Gateway  │───▶│   WAF        │     │    │
│   │  │   (DNS)      │    │  (CDN/Edge)  │    │  (REST API)  │    │  (Security)  │     │    │
│   │  │              │    │              │    │              │    │              │     │    │
│   │  │ • Health     │    │ • Edge cache │    │ • Rate limit │    │ • DDoS prot. │     │    │
│   │  │   checks     │    │ • DDoS prot. │    │ • API keys   │    │ • IP filter  │     │    │
│   │  │ • Failover   │    │ • SSL term.  │    │ • Throttling │    │ • Geo block  │     │    │
│   │  │ • Latency    │    │ • Compress   │    │ • Caching    │    │ • Rate limit │     │    │
│   │  └──────────────┘    └──────────────┘    └──────┬───────┘    └──────────────┘     │    │
│   │                                                 │                                  │    │
│   └─────────────────────────────────────────────────┼──────────────────────────────────┘    │
│                                                     │                                       │
│   ┌─────────────────────────────────────────────────┼──────────────────────────────────┐    │
│   │                              VPC (10.0.0.0/16)  │                                   │    │
│   ├─────────────────────────────────────────────────┼──────────────────────────────────┤    │
│   │                                                 ▼                                   │    │
│   │   Private Subnets (Multi-AZ)                                                        │    │
│   │   ┌─────────────────────────────────────────────────────────────────────────────┐   │    │
│   │   │                                                                              │   │    │
│   │   │   ┌───────────────────────────────────────────────────────────────────────┐ │   │    │
│   │   │   │                    Amazon EKS with Fargate                             │ │   │    │
│   │   │   │                    (Serverless Pods - No EC2 Management)               │ │   │    │
│   │   │   ├───────────────────────────────────────────────────────────────────────┤ │   │    │
│   │   │   │                                                                        │ │   │    │
│   │   │   │   ┌─────────────────────────────────────────────────────────────────┐ │ │   │    │
│   │   │   │   │              Application Namespace (Fargate Profile)             │ │ │   │    │
│   │   │   │   ├─────────────────────────────────────────────────────────────────┤ │ │   │    │
│   │   │   │   │                                                                  │ │ │   │    │
│   │   │   │   │  ┌──────────────────────┐  ┌──────────────────────┐             │ │ │   │    │
│   │   │   │   │  │  Stock Signal API    │  │  Stock Signal API    │             │ │ │   │    │
│   │   │   │   │  │  Pod (AZ-1)          │  │  Pod (AZ-2)          │             │ │ │   │    │
│   │   │   │   │  │  ┌────────────────┐  │  │  ┌────────────────┐  │             │ │ │   │    │
│   │   │   │   │  │  │ FastAPI        │  │  │  │ FastAPI        │  │             │ │ │   │    │
│   │   │   │   │  │  │ Container      │  │  │  │ Container      │  │             │ │ │   │    │
│   │   │   │   │  │  │                │  │  │  │                │  │             │ │ │   │    │
│   │   │   │   │  │  │ • Orchestrator │  │  │  │ • Orchestrator │  │             │ │ │   │    │
│   │   │   │   │  │  │ • 47 Agents    │  │  │  │ • 47 Agents    │  │             │ │ │   │    │
│   │   │   │   │  │  └────────────────┘  │  │  └────────────────┘  │             │ │ │   │    │
│   │   │   │   │  └──────────────────────┘  └──────────────────────┘             │ │ │   │    │
│   │   │   │   │              │                        │                          │ │ │   │    │
│   │   │   │   │              └────────────┬───────────┘                          │ │ │   │    │
│   │   │   │   │                           │                                      │ │ │   │    │
│   │   │   │   └───────────────────────────┼──────────────────────────────────────┘ │ │   │    │
│   │   │   │                               │                                        │ │   │    │
│   │   │   │   HPA: 2-10 pods (Fargate auto-scales compute)                         │ │   │    │
│   │   │   │   PDB: minAvailable=2 for zero-downtime                                │ │   │    │
│   │   │   │                               │                                        │ │   │    │
│   │   │   └───────────────────────────────┼────────────────────────────────────────┘ │   │    │
│   │   │                                   │                                          │   │    │
│   │   │   ┌───────────────────────────────┼───────────────────────────────────────┐  │   │    │
│   │   │   │                               ▼                                        │  │   │    │
│   │   │   │   ┌──────────────────────────────────────────────────────────────┐    │  │   │    │
│   │   │   │   │                     Amazon Bedrock                            │    │  │   │    │
│   │   │   │   │                     (Native AWS LLM Service)                  │    │  │   │    │
│   │   │   │   ├──────────────────────────────────────────────────────────────┤    │  │   │    │
│   │   │   │   │                                                               │    │  │   │    │
│   │   │   │   │   Available Models:                                           │    │  │   │    │
│   │   │   │   │   • anthropic.claude-3-5-sonnet-20241022-v2:0                 │    │  │   │    │
│   │   │   │   │   • anthropic.claude-3-5-haiku-20241022-v1:0                  │    │  │   │    │
│   │   │   │   │   • meta.llama3-1-70b-instruct-v1:0                           │    │  │   │    │
│   │   │   │   │   • mistral.mistral-large-2407-v1:0                           │    │  │   │    │
│   │   │   │   │   • amazon.titan-text-premier-v1:0                            │    │  │   │    │
│   │   │   │   │                                                               │    │  │   │    │
│   │   │   │   │   Benefits: No infrastructure, pay-per-token, private VPC     │    │  │   │    │
│   │   │   │   │   endpoint, SOC2/HIPAA compliant, no data leaves AWS          │    │  │   │    │
│   │   │   │   │                                                               │    │  │   │    │
│   │   │   │   └──────────────────────────────────────────────────────────────┘    │  │   │    │
│   │   │   │                                                                        │  │   │    │
│   │   │   │   ┌─────────────────────┐  ┌─────────────────────┐                    │  │   │    │
│   │   │   │   │   ElastiCache       │  │   Amazon MSK        │                    │  │   │    │
│   │   │   │   │   (Redis Cluster)   │  │   (Managed Kafka)   │                    │  │   │    │
│   │   │   │   ├─────────────────────┤  ├─────────────────────┤                    │  │   │    │
│   │   │   │   │ • Signal caching    │  │ • stock-prices      │                    │  │   │    │
│   │   │   │   │ • TTL: 5 min        │  │ • stock-news        │                    │  │   │    │
│   │   │   │   │ • Reduce LLM costs  │  │ • sec-filings       │                    │  │   │    │
│   │   │   │   │ • Session store     │  │ • Multi-AZ, 3 nodes │                    │  │   │    │
│   │   │   │   └─────────────────────┘  └─────────────────────┘                    │  │   │    │
│   │   │   │                                                                        │  │   │    │
│   │   │   │   ┌─────────────────────┐  ┌─────────────────────┐                    │  │   │    │
│   │   │   │   │   OpenSearch        │  │   Amazon EFS        │                    │  │   │    │
│   │   │   │   │   (Vector DB)       │  │   (Model Storage)   │                    │  │   │    │
│   │   │   │   ├─────────────────────┤  ├─────────────────────┤                    │  │   │    │
│   │   │   │   │ • stock_news (384d) │  │ • ReadWriteMany     │                    │  │   │    │
│   │   │   │   │ • sec_filings       │  │ • For Ollama models │                    │  │   │    │
│   │   │   │   │ • Multi-AZ replicas │  │ • (if self-hosted)  │                    │  │   │    │
│   │   │   │   └─────────────────────┘  └─────────────────────┘                    │  │   │    │
│   │   │   │                                                                        │  │   │    │
│   │   │   │   Managed Services Layer                                               │  │   │    │
│   │   │   └────────────────────────────────────────────────────────────────────────┘  │   │    │
│   │   │                                                                               │   │    │
│   │   └───────────────────────────────────────────────────────────────────────────────┘   │    │
│   │                                                                                        │    │
│   └────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              Supporting Services                                          │  │
│   ├──────────────────────────────────────────────────────────────────────────────────────────┤  │
│   │                                                                                           │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│   │   │  Amazon ECR  │  │  Secrets     │  │  CloudWatch  │  │  X-Ray       │                │  │
│   │   │  (Container  │  │  Manager     │  │  (Logs &     │  │  (Tracing)   │                │  │
│   │   │   Registry)  │  │  (API Keys)  │  │   Metrics)   │  │              │                │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│   │                                                                                           │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │  │
│   │   │  S3          │  │  IAM Roles   │  │  KMS         │  │  Parameter   │                │  │
│   │   │  (Artifacts) │  │  (IRSA)      │  │  (Encrypt)   │  │  Store       │                │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘                │  │
│   │                                                                                           │  │
│   └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Using Amazon Bedrock:**

```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"

# Run with Bedrock models (via LiteLLM)
python main.py --ticker AAPL --model bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0

# Multi-agent with Bedrock
python main.py --ticker AAPL --multi-agent --model bedrock/meta.llama3-1-70b-instruct-v1:0
```

**Bedrock IAM Policy (required):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
```

---

### Option 2: Simplified (AWS App Runner)

Fully managed container service with automatic scaling. No Kubernetes knowledge required.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    AWS Cloud                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────┐    ┌──────────────────────────────────────────────────────────────┐  │
│   │   Route 53   │───▶│                    AWS App Runner                             │  │
│   │   (DNS)      │    │                    (Fully Managed)                            │  │
│   └──────────────┘    ├──────────────────────────────────────────────────────────────┤  │
│                       │                                                               │  │
│                       │   ┌─────────────────────────────────────────────────────────┐│  │
│                       │   │  Auto-managed:                                          ││  │
│                       │   │  • Load balancing    • TLS certificates                 ││  │
│                       │   │  • Auto-scaling      • Health checks                    ││  │
│                       │   │  • VPC connector     • CI/CD integration                ││  │
│                       │   └─────────────────────────────────────────────────────────┘│  │
│                       │                                                               │  │
│                       │   ┌──────────────────────┐  ┌──────────────────────┐         │  │
│                       │   │  Stock Signal API    │  │  Stock Signal API    │         │  │
│                       │   │  Instance (1)        │  │  Instance (2)        │         │  │
│                       │   │  ┌────────────────┐  │  │  ┌────────────────┐  │         │  │
│                       │   │  │ FastAPI + 44   │  │  │  │ FastAPI + 44   │  │         │  │
│                       │   │  │ Agents         │  │  │  │ Agents         │  │         │  │
│                       │   │  └────────────────┘  │  │  └────────────────┘  │         │  │
│                       │   └──────────┬───────────┘  └──────────┬───────────┘         │  │
│                       │              │                          │                     │  │
│                       │              └────────────┬─────────────┘                     │  │
│                       │                           │                                   │  │
│                       └───────────────────────────┼───────────────────────────────────┘  │
│                                                   │                                      │
│                                                   ▼                                      │
│                       ┌──────────────────────────────────────────────────────────────┐  │
│                       │                     Amazon Bedrock                            │  │
│                       │           (Claude, Llama, Mistral - No Setup)                 │  │
│                       └──────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Deploy to App Runner:**

```bash
# Create App Runner service (AWS Console or CLI)
aws apprunner create-service \
  --service-name stock-signal-api \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/stock-signal-api:latest",
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "Cpu": "1024",
    "Memory": "2048"
  }'
```

**App Runner Pros/Cons:**

| Pros | Cons |
|------|------|
| Zero infrastructure management | Less control over networking |
| Auto-scaling included | No GPU support (can't self-host LLMs) |
| Built-in CI/CD from ECR | Higher per-request cost at scale |
| $0.007/GB-hour pricing | Limited to 25 concurrent requests |

---

### Option 3: Serverless (Lambda + API Gateway)

True serverless, pay-per-request pricing. Ideal for low/variable traffic.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    AWS Cloud                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────────────────────┐  │
│   │   Route 53   │───▶│   CloudFront     │───▶│        API Gateway (HTTP API)        │  │
│   │   (DNS)      │    │   (Edge Cache)   │    │        (Serverless REST)             │  │
│   └──────────────┘    └──────────────────┘    ├──────────────────────────────────────┤  │
│                                               │  • Rate limiting: 1000 req/sec        │  │
│                                               │  • API keys & usage plans             │  │
│                                               │  • Response caching (TTL: 5 min)      │  │
│                                               │  • $1.00 per million requests         │  │
│                                               └──────────────────┬───────────────────┘  │
│                                                                  │                      │
│                                                                  ▼                      │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              AWS Lambda                                           │  │
│   │                              (Container Image)                                    │  │
│   ├──────────────────────────────────────────────────────────────────────────────────┤  │
│   │                                                                                   │  │
│   │   ┌───────────────────────────────────────────────────────────────────────────┐  │  │
│   │   │   POST /signal                                                             │  │  │
│   │   │   ┌──────────────────────┐  ┌──────────────────────┐                      │  │  │
│   │   │   │  Lambda Function     │  │  Lambda Function     │  (concurrent)        │  │  │
│   │   │   │  ┌────────────────┐  │  │  ┌────────────────┐  │                      │  │  │
│   │   │   │  │ FastAPI +      │  │  │  │ FastAPI +      │  │                      │  │  │
│   │   │   │  │ Mangum adapter │  │  │  │ Mangum adapter │  │                      │  │  │
│   │   │   │  │ + 47 Agents    │  │  │  │ + 47 Agents    │  │                      │  │  │
│   │   │   │  └────────────────┘  │  │  └────────────────┘  │                      │  │  │
│   │   │   │  Timeout: 5 min      │  │  Memory: 3008 MB     │                      │  │  │
│   │   │   └──────────────────────┘  └──────────────────────┘                      │  │  │
│   │   │                                                                            │  │  │
│   │   │   Provisioned Concurrency: 5 (optional, for cold start mitigation)        │  │  │
│   │   └───────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                          │                                        │  │
│   └──────────────────────────────────────────┼────────────────────────────────────────┘  │
│                                              │                                           │
│                                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              Amazon Bedrock                                       │  │
│   │                              (Claude 3.5, Llama 3.1, Mistral)                     │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Lambda Configuration:**

```yaml
# serverless.yml (Serverless Framework) or SAM template
StockSignalFunction:
  Type: AWS::Lambda::Function
  Properties:
    PackageType: Image
    Code:
      ImageUri: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/stock-signal-api:latest
    MemorySize: 3008
    Timeout: 300
    Environment:
      Variables:
        AWS_LWA_INVOKE_MODE: response_stream  # For streaming responses
```

**Lambda Pros/Cons:**

| Pros | Cons |
|------|------|
| Pay only when invoked | 15-min max timeout |
| Scales to 0 (no idle costs) | Cold starts (2-5 sec) |
| Up to 10,000 concurrent | 10GB max container size |
| $0.0000166667/GB-second | No persistent connections |

---

### Multi-Region Setup (Disaster Recovery)

Active-passive configuration with automatic failover.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Multi-Region Architecture                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│                           ┌──────────────────────┐                                       │
│                           │      Route 53        │                                       │
│                           │   (Failover Policy)  │                                       │
│                           │                      │                                       │
│                           │ Primary: us-east-1   │                                       │
│                           │ DR: us-west-2        │                                       │
│                           └──────────┬───────────┘                                       │
│                                      │                                                   │
│                    ┌─────────────────┴─────────────────┐                                 │
│                    │                                   │                                 │
│                    ▼                                   ▼                                 │
│   ┌────────────────────────────────┐   ┌────────────────────────────────┐               │
│   │       Primary (us-east-1)      │   │         DR (us-west-2)         │               │
│   │       ══════════════════       │   │         ════════════           │               │
│   ├────────────────────────────────┤   ├────────────────────────────────┤               │
│   │                                │   │                                │               │
│   │  ┌─────────────────────────┐  │   │  ┌─────────────────────────┐  │               │
│   │  │     API Gateway         │  │   │  │     API Gateway         │  │               │
│   │  └───────────┬─────────────┘  │   │  └───────────┬─────────────┘  │               │
│   │              │                 │   │              │                 │               │
│   │  ┌───────────▼─────────────┐  │   │  ┌───────────▼─────────────┐  │               │
│   │  │   EKS Fargate Cluster   │  │   │  │   EKS Fargate Cluster   │  │               │
│   │  │   (Active)              │  │   │  │   (Standby)             │  │               │
│   │  └───────────┬─────────────┘  │   │  └───────────┬─────────────┘  │               │
│   │              │                 │   │              │                 │               │
│   │  ┌───────────▼─────────────┐  │   │  ┌───────────▼─────────────┐  │               │
│   │  │     Amazon Bedrock      │  │   │  │     Amazon Bedrock      │  │               │
│   │  └─────────────────────────┘  │   │  └─────────────────────────┘  │               │
│   │                                │   │                                │               │
│   │  ┌─────────────────────────┐  │   │  ┌─────────────────────────┐  │               │
│   │  │   ElastiCache (Redis)   │◀─┼───┼─▶│   ElastiCache (Redis)   │  │               │
│   │  │   Global Datastore      │  │   │  │   Global Datastore      │  │               │
│   │  └─────────────────────────┘  │   │  └─────────────────────────┘  │               │
│   │                                │   │                                │               │
│   │  ┌─────────────────────────┐  │   │  ┌─────────────────────────┐  │               │
│   │  │   MSK (Kafka)           │──┼───┼──│   MSK (Kafka)           │  │               │
│   │  │   Cross-Region Repl.    │  │   │  │   Cross-Region Repl.    │  │               │
│   │  └─────────────────────────┘  │   │  └─────────────────────────┘  │               │
│   │                                │   │                                │               │
│   └────────────────────────────────┘   └────────────────────────────────┘               │
│                                                                                          │
│   Recovery Targets:                                                                      │
│   • RTO (Recovery Time Objective): < 5 minutes                                          │
│   • RPO (Recovery Point Objective): < 1 minute                                          │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Route 53 Health Check Configuration:**

```bash
# Create health check
aws route53 create-health-check \
  --caller-reference $(date +%s) \
  --health-check-config '{
    "Type": "HTTPS",
    "FullyQualifiedDomainName": "api.stock-signal.com",
    "Port": 443,
    "ResourcePath": "/health",
    "RequestInterval": 10,
    "FailureThreshold": 2
  }'

# Create failover record set
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456789 \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.stock-signal.com",
        "Type": "A",
        "SetIdentifier": "primary",
        "Failover": "PRIMARY",
        "HealthCheckId": "abc123",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "d111111abcdef8.cloudfront.net",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

---

### CI/CD Pipeline (CodePipeline + CodeBuild)

Automated build, test, and deployment pipeline.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              CI/CD Pipeline                                              │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────┐    ┌──────────────────────────────────────────────────────────────┐  │
│   │   GitHub     │    │                    AWS CodePipeline                           │  │
│   │   (Source)   │───▶│                                                               │  │
│   └──────────────┘    │   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐     │  │
│                       │   │ Source  │──▶│  Build  │──▶│  Test   │──▶│ Deploy  │     │  │
│                       │   │         │   │         │   │         │   │         │     │  │
│                       │   └─────────┘   └────┬────┘   └────┬────┘   └────┬────┘     │  │
│                       │                      │              │              │          │  │
│                       └──────────────────────┼──────────────┼──────────────┼──────────┘  │
│                                              │              │              │             │
│                                              ▼              ▼              ▼             │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                           AWS CodeBuild                                           │  │
│   ├──────────────────────────────────────────────────────────────────────────────────┤  │
│   │                                                                                   │  │
│   │   Build Stage:                    Test Stage:                 Deploy Stage:       │  │
│   │   ┌────────────────────┐         ┌────────────────────┐     ┌────────────────┐   │  │
│   │   │ • docker build     │         │ • pytest           │     │ • kubectl apply│   │  │
│   │   │ • docker push ECR  │         │ • coverage report  │     │ • helm upgrade │   │  │
│   │   │ • trivy scan       │         │ • integration tests│     │ • canary check │   │  │
│   │   │ • SBOM generation  │         │ • load tests       │     │ • promote/rollback│ │  │
│   │   └────────────────────┘         └────────────────────┘     └────────────────┘   │  │
│   │                                                                                   │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│                                              │                                           │
│                                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                    Deployment Strategies                                          │  │
│   ├──────────────────────────────────────────────────────────────────────────────────┤  │
│   │                                                                                   │  │
│   │   Blue/Green:                          Canary:                                    │  │
│   │   ┌───────────────────────┐           ┌───────────────────────┐                  │  │
│   │   │ Blue (current) ──────┐│           │ v1 (90%) ─────────────│                  │  │
│   │   │ Green (new)    ──────┘│           │ v2 (10%) → 50% → 100% │                  │  │
│   │   │ Instant cutover       │           │ Progressive rollout    │                  │  │
│   │   └───────────────────────┘           └───────────────────────┘                  │  │
│   │                                                                                   │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**buildspec.yml:**

```yaml
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO
      - COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=${COMMIT_HASH:=latest}

  build:
    commands:
      - echo Building Docker image...
      - docker build -t $ECR_REPO:$IMAGE_TAG .
      - docker tag $ECR_REPO:$IMAGE_TAG $ECR_REPO:latest

      # Security scan
      - echo Running Trivy security scan...
      - trivy image --exit-code 1 --severity HIGH,CRITICAL $ECR_REPO:$IMAGE_TAG

  post_build:
    commands:
      - echo Pushing Docker image...
      - docker push $ECR_REPO:$IMAGE_TAG
      - docker push $ECR_REPO:latest

      # Update EKS
      - aws eks update-kubeconfig --name stock-signal-cluster --region $AWS_REGION
      - helm upgrade stock-signal ./helm/stock-signal-api --set image.tag=$IMAGE_TAG

artifacts:
  files:
    - imagedefinitions.json
```

---

### AWS Services Reference

| Component | AWS Service | Purpose | Pricing Model |
|-----------|-------------|---------|---------------|
| **Compute** | EKS Fargate | Serverless Kubernetes pods | Per vCPU/memory-second |
| **Compute (Alt)** | App Runner | Fully managed containers | Per vCPU-hour + memory |
| **Compute (Alt)** | Lambda | Serverless functions | Per request + duration |
| **LLM** | Amazon Bedrock | Claude, Llama, Mistral | Per input/output token |
| **API** | API Gateway | REST/HTTP API management | Per request + data |
| **Edge** | CloudFront | CDN, edge caching | Per request + data |
| **DNS** | Route 53 | DNS, health checks, failover | Per hosted zone + queries |
| **Security** | WAF | DDoS, rate limiting, rules | Per rule + requests |
| **Cache** | ElastiCache | Redis caching layer | Per node-hour |
| **Streaming** | Amazon MSK | Managed Kafka | Per broker-hour |
| **Vector DB** | OpenSearch | Embeddings search | Per instance-hour |
| **Storage** | Amazon EFS | Shared file storage | Per GB-month |
| **Registry** | Amazon ECR | Docker images | Per GB-month + transfer |
| **Secrets** | Secrets Manager | API keys, credentials | Per secret + API calls |
| **Monitoring** | CloudWatch | Logs, metrics, alarms | Per metric + logs |
| **Tracing** | X-Ray | Distributed tracing | Per trace |
| **CI/CD** | CodePipeline | Pipeline orchestration | Per pipeline-month |
| **CI/CD** | CodeBuild | Build automation | Per build-minute |
| **Encryption** | AWS KMS | Key management | Per key + API calls |

---

### Cost Optimization Tips

| Strategy | Implementation | Savings |
|----------|----------------|---------|
| **Fargate Spot** | Use for non-critical workloads, batch jobs | Up to 70% |
| **Savings Plans** | 1 or 3-year commitment for Fargate compute | Up to 50% |
| **Graviton Processors** | ARM-based Fargate tasks | 20% cheaper |
| **ElastiCache** | Cache repeated LLM queries (5 min TTL) | 60-80% LLM costs |
| **API Gateway Caching** | Cache GET responses at edge | Reduced backend calls |
| **Bedrock Batch** | Use batch inference for non-realtime | 50% cheaper |
| **MSK Serverless** | Pay-per-use for variable streaming | No idle costs |
| **Reserved Capacity** | For predictable Bedrock usage | Up to 40% |
| **Right-sizing** | Start with Fargate 0.5vCPU/1GB, scale up | Avoid over-provisioning |

**Monthly Cost Estimates:**

| Configuration | Monthly Cost |
|---------------|--------------|
| **Minimal** (App Runner + Bedrock, 1000 req/day) | $50-100 |
| **Standard** (EKS Fargate + Bedrock + ElastiCache) | $300-600 |
| **Enterprise** (Multi-region, MSK, full HA) | $1,500-3,000 |

---

### External Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              External Dependencies                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐     │
│   │   Yahoo Finance API  │    │   SEC EDGAR API      │    │   Langfuse Cloud     │     │
│   │   (Market Data)      │    │   (SEC Filings)      │    │   (Observability)    │     │
│   │                      │    │                      │    │                      │     │
│   │   • OHLCV prices     │    │   • 10-K, 10-Q, 8-K  │    │   • LLM Tracing      │     │
│   │   • News articles    │    │   • Company filings  │    │   • Cost tracking    │     │
│   │   • Fundamentals     │    │   • Free, no key     │    │   • Prompt analytics │     │
│   └──────────────────────┘    └──────────────────────┘    └──────────────────────┘     │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Multi-Agent Architecture**: Up to 47 domain-specialized agents (feature-flag-enabled) analyzing different data sources
- **Machine Learning**: LSTM price prediction, XGBoost signal classification, Ensemble scoring
- **Streamlit Dashboard**: Interactive UI with technical charts, watchlists, and auto-refresh
- **Report Actions**: Download PDF reports, send SMS alerts, email reports with attachments
- **Agentic AI Pattern**: Plan → Perceive → Reason → Act lifecycle
- **Dual Mode**: Single-agent (backward compatible) or multi-agent orchestration
- **Signal Reconciliation**: Final signal includes LLM + majority-vote reconciliation metadata
- **REST API**: FastAPI-based API with automatic OpenAPI documentation
- **Observability**: Langfuse integration for LLM tracing and monitoring
- **Optional Infrastructure**: Kafka streaming, Qdrant vector storage, PostgreSQL historical cache, and n8n workflow automation
- **LLM Integration**: Uses LiteLLM for model-agnostic LLM calls (100+ providers)
- **Comprehensive Analysis**: Technical indicators, news sentiment, SEC filings, analyst ratings, social media, options flow

---

## Kafka, Qdrant, PostgreSQL, and n8n (Optional)

Kafka, Qdrant, PostgreSQL, and n8n are **optional infrastructure components** that enhance the system for enterprise use cases. The system is fully functional without them.

### Starting All Services

All containers have `restart: unless-stopped` — they come back automatically after Docker Desktop restarts.

**Start everything with one command (Kafka + Zookeeper + Qdrant + PostgreSQL + Kafka UI + Unleash):**

```bash
docker compose up -d
```

The `infra-init` service runs automatically on startup and eagerly creates all Qdrant collections (`stock_news`, `sec_filings`, `stock_prices`) and Kafka topics (`stock-prices`, `stock-news`, `sec-filings`) so they appear in the dashboards immediately without needing to run an analysis first.

---

#### Volume Storage

By default all data is stored in **named Docker volumes** managed by Docker (inside Docker Desktop's VM). Volumes survive `docker compose down` and are only removed with `docker compose down -v`.

**Option 1 — Named volumes (default, no config needed):**

```bash
docker compose up -d
```

| Volume | Service | Data |
|--------|---------|------|
| `stockaiassistant_postgres-data` | PostgreSQL | `stock_signal` + `unleash` databases |
| `stockaiassistant_qdrant-data` | Qdrant | `stock_news`, `sec_filings` collections |
| `stockaiassistant_kafka-data` | Kafka | Topic data and offsets |
| `stockaiassistant_zookeeper-data` | Zookeeper | Cluster metadata |
| `stockaiassistant_zookeeper-log` | Zookeeper | Transaction log |

**Option 2 — Custom host path (visible on your filesystem):**

Use the helper script to point all volumes at a directory of your choice:

```bash
./scripts/start.sh --data-path /your/custom/path
```

This creates subdirectories under the given path and mounts them as bind mounts:

```
/your/custom/path/
├── postgres/
├── kafka/
├── qdrant/
└── zookeeper/
    ├── data/
    └── log/
```

You can also set the env vars manually and call `docker compose` directly:

```bash
export DATA_PATH=/your/custom/path
export POSTGRES_VOLUME=$DATA_PATH/postgres
export KAFKA_VOLUME=$DATA_PATH/kafka
export QDRANT_VOLUME=$DATA_PATH/qdrant
export ZOOKEEPER_DATA_VOLUME=$DATA_PATH/zookeeper/data
export ZOOKEEPER_LOG_VOLUME=$DATA_PATH/zookeeper/log
mkdir -p $POSTGRES_VOLUME $KAFKA_VOLUME $QDRANT_VOLUME $ZOOKEEPER_DATA_VOLUME $ZOOKEEPER_LOG_VOLUME
docker compose up -d
```

Docker Compose treats absolute paths as bind mounts and plain names as named volumes automatically — no other config changes needed.

---

**Check all services are healthy:**

```bash
docker compose ps
# Expected: postgres (healthy), qdrant (Up), kafka (Up), zookeeper (Up), unleash (healthy), kafka-ui (Up), infra-init (Exit 0)
```

**View logs for a specific service:**

```bash
docker compose logs postgres --tail=50
docker compose logs kafka --tail=50
docker compose logs unleash --tail=50
```

**Stop services (data preserved):**

```bash
docker compose down
```

**Stop and wipe all data (destructive):**

```bash
docker compose down -v
```

---

**Run the application with infrastructure:**

```bash
# With both Kafka and Qdrant enabled
python main.py --ticker AAPL --multi-agent --kafka --qdrant

# Enable just Kafka (streaming)
python main.py --ticker AAPL --multi-agent --kafka

# Enable just Qdrant (vector search)
python main.py --ticker AAPL --multi-agent --qdrant
```

### Kafka (Event Streaming)

When enabled with `--kafka`, agents publish data to Kafka topics for downstream processing:

**Core Topics (High Priority):**

| Producer Agent | Kafka Topic | Data Published | Potential Consumers |
|----------------|-------------|----------------|---------------------|
| `TechnicalAnalysisAgent` | `stock-prices` | OHLCV, volume, indicators | Analytics DB, ML Pipeline |
| `NewsAgent` | `stock-news` | Headlines, publisher, links | Alert Service, Sentiment Analysis |
| `SECFilingAgent` | `sec-filings` | 10-K/10-Q/8-K excerpts | Compliance Systems, NLP Pipeline |

**Analyst Rating Topics:**

| Producer Agent | Kafka Topic | Data Published |
|----------------|-------------|----------------|
| `ZacksAgent` | `zacks-data` | Rank (1-5), VGM scores, target price |
| `TipRanksAgent` | `tipranks-data` | Analyst consensus, price targets |
| `SeekingAlphaAgent` | `seekingalpha-data` | Quant ratings, growth/value scores |
| `MotleyFoolAgent` | `motleyfool-data` | Quality scores, growth ratings |
| `MarketBeatAgent` | `marketbeat-data` | Analyst ratings, earnings beat rate |
| `StockStoryAgent` | `stockstory-data` | Business fundamentals, risk factors |

**Financial Data Topics:**

| Producer Agent | Kafka Topic | Data Published |
|----------------|-------------|----------------|
| `MorningstarAgent` | `morningstar-data` | Moat rating, fair value, financial health |
| `GuruFocusAgent` | `gurufocus-data` | Value investing metrics, DCF |
| `YahooFinanceAgent` | `yahoofinance-data` | Options data, dividends, trading activity |
| `TradingViewAgent` | `tradingview-data` | Technical oscillators, moving averages |
| `SimplyWallStAgent` | `simplywallst-data` | Snowflake analysis (value/growth/health) |
| `AlphaSpreadAgent` | `alphaspread-data` | Intrinsic value, DCF analysis |
| `FactSetAgent` | `factset-data` | Earnings quality, estimate revisions |
| `CapitalIQAgent` | `capitaliq-data` | Credit metrics, profitability ratios |
| `RefinitivAgent` | `refinitiv-data` | Consensus estimates, market data |
| `StockRoverAgent` | `stockrover-data` | Quality/value/sentiment scores |

**Use Cases:**
- Real-time streaming to data lakes (S3, Snowflake)
- Event-driven architectures for alert services
- Building historical data pipelines
- Audit trail of all fetched data

### Qdrant (Vector Database)

When enabled with `--qdrant`, agents store embeddings for semantic search:

**Embedding Model:** `all-MiniLM-L6-v2` (384 dimensions, sentence-transformers)
**Database namespace:** `stock-signal`

**Core Collections with Active Readers:**

| Collection | Writer Agent | Reader Agent | Search Use Case |
|------------|--------------|--------------|-----------------|
| `stock_news` | NewsAgent | **SentimentAgent**, NewsAgent | Find historically similar news for sentiment context |
| `sec_filings` | SECFilingAgent | (Future) | Search filings by content similarity |

> **Note:** `NewsAgent` and `SECFilingAgent` are **data-collection agents** — they produce `signal=None` by design and pass raw article/filing text to `SentimentAgent` for LLM scoring. The dashboard displays "Data Only" for these agents rather than a signal badge.

**Agent-Specific Collections (Future Cross-Reference):**

| Collection | Writer Agent | Data Stored |
|------------|--------------|-------------|
| `zacks_data` | ZacksAgent | Rank history, VGM score vectors |
| `tipranks_data` | TipRanksAgent | Analyst consensus embeddings |
| `seekingalpha_data` | SeekingAlphaAgent | Quant rating vectors |
| `morningstar_data` | MorningstarAgent | Moat/value analysis embeddings |
| `yahoofinance_data` | YahooFinanceAgent | Options/dividend pattern vectors |
| `gurufocus_data` | GuruFocusAgent | Value metric embeddings |
| `tradingview_data` | TradingViewAgent | Technical indicator vectors |
| `stockrover_data` | StockRoverAgent | Quality score embeddings |
| `simplywallst_data` | SimplyWallStAgent | Snowflake analysis vectors |
| `alphaspread_data` | AlphaSpreadAgent | DCF/intrinsic value embeddings |

**How SentimentAgent Uses Vector Search:**
```python
# SentimentAgent searches stock_news for historical context
def _search_historical_sentiment(self, query: str) -> list[dict]:
    vector = self.embedder.embed([query])[0]
    return self.qdrant_store.search(
        "stock_news",           # Collection name
        vector,                  # Query vector (384-dim)
        limit=5,                 # Return top 5 similar
        filter_conditions={"ticker": self.ticker}  # Filter by ticker
    )
```

**Use Cases:**
- Semantic search: "Find news similar to earnings surprises"
- Historical sentiment comparison by SentimentAgent
- Deduplication of similar articles
- Historical context retrieval for LLM prompts
- Cross-ticker similarity analysis

### PostgreSQL (Historical Price Cache)

When enabled via `application.yml` (`postgres.enabled: true`) or `POSTGRES_ENABLED=true`, the system uses a DB-first pattern for price history in:

- `TechnicalAnalysisAgent` (multi-agent mode)
- `StockSignalAgent` (single-agent mode)

Read/write behavior:

1. Read requested OHLCV range from PostgreSQL.
2. If data is missing or stale, fetch from Yahoo Finance.
3. Upsert fetched rows to PostgreSQL.
4. Return the requested range (re-read from DB).

Default table and retention policy:

- Table: `stock_prices_daily`
- Backfill window: `5` years (`postgres.backfill_years`)
- Primary key: `(ticker, price_date)`

### n8n Workflow Automation

Ready-to-import workflow files are under `n8n/`:

- `n8n/stock-signal-watchlist-workflow.json` — weekday 09:35 trigger, watchlist batch, BUY policy gate, alert + audit payloads
- `n8n/buy-now-scheduled-workflow.json` — polls `/schedules/due` every 5 min, runs `scheduled_buy_now_report.py` per row, marks success/failure in PostgreSQL
- `n8n/README.md` — full setup guide

The included workflows support:

- manual + scheduled runs
- watchlist batch processing (one ticker per batch)
- `/signal` API invocation with `ml_analysis` flag in the POST body
- retries (3×, 5s delay)
- high-conviction BUY policy routing (`confidence >= min_confidence`)
- alert payload includes ensemble signal + LSTM target price when `ml_analysis` is ON
- audit payload captures `ml_enabled`, `ensemble_signal`, `ensemble_confidence`, `target_price`
- per-agent feature flags managed server-side (no workflow changes needed)
- default model: `claude-sonnet-4-6`

### Data Flow with Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Infrastructure Data Flow                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌─────────────────┐                                                                   │
│   │   NewsAgent     │                                                                   │
│   │   fetches news  │                                                                   │
│   └────────┬────────┘                                                                   │
│            │                                                                             │
│            ├──────────────────────────────────────────────────────────────┐             │
│            │                                                               │             │
│            ▼                                                               ▼             │
│   ┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐   │
│   │           --kafka                    │    │           --qdrant                   │   │
│   ├─────────────────────────────────────┤    ├─────────────────────────────────────┤   │
│   │                                      │    │                                      │   │
│   │   Kafka Topic: stock-news            │    │   Qdrant Collection: stock_news      │   │
│   │   ┌────────────────────────────┐    │    │   ┌────────────────────────────┐    │   │
│   │   │ {                          │    │    │   │ Vector: [0.12, -0.34, ...]  │    │   │
│   │   │   "ticker": "AAPL",        │    │    │   │ Payload: {                  │    │   │
│   │   │   "title": "Apple Q4...",  │    │    │   │   "ticker": "AAPL",         │    │   │
│   │   │   "publisher": "Reuters",  │    │    │   │   "title": "Apple Q4...",   │    │   │
│   │   │   "text": "..."            │    │    │   │   "text": "..."             │    │   │
│   │   │ }                          │    │    │   │ }                           │    │   │
│   │   └────────────────────────────┘    │    │   └────────────────────────────┘    │   │
│   │                                      │    │                                      │   │
│   │   Downstream Consumers:              │    │   Capabilities:                      │   │
│   │   • Data Lake (S3/Snowflake)        │    │   • Semantic search                  │   │
│   │   • Alert Service                    │    │   • Find similar articles            │   │
│   │   • Analytics Pipeline               │    │   • Context retrieval for LLM        │   │
│   │   • Audit/Compliance                 │    │   • Cross-ticker analysis            │   │
│   │                                      │    │                                      │   │
│   └─────────────────────────────────────┘    └─────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Without Infrastructure

When running without `--kafka` and `--qdrant`:
- All agents still fetch and analyze data normally
- Data is processed in-memory only
- No persistence or streaming occurs
- Final signal generation works identically

This makes the system **zero-dependency for basic usage** - infrastructure is purely for enterprise features.

---

### Feature Flags (Unleash / AWS AppConfig)

The system supports feature flags for controlled rollout of features across environments.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Feature Flags Architecture                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│                            ┌─────────────────────────────┐                              │
│                            │   FeatureFlagService        │                              │
│                            │   (Auto-selects provider)   │                              │
│                            └─────────────┬───────────────┘                              │
│                                          │                                               │
│                    ┌─────────────────────┴─────────────────────┐                        │
│                    │                                           │                        │
│                    ▼                                           ▼                        │
│   ┌────────────────────────────────┐       ┌────────────────────────────────┐          │
│   │      Local Development         │       │      AWS Environments          │          │
│   │      (APP_ENV=local)           │       │      (APP_ENV=qa/stg/prod)     │          │
│   ├────────────────────────────────┤       ├────────────────────────────────┤          │
│   │                                │       │                                │          │
│   │   ┌────────────────────────┐   │       │   ┌────────────────────────┐   │          │
│   │   │    UnleashProvider     │   │       │   │   AppConfigProvider    │   │          │
│   │   └───────────┬────────────┘   │       │   └───────────┬────────────┘   │          │
│   │               │                │       │               │                │          │
│   │               ▼                │       │               ▼                │          │
│   │   ┌────────────────────────┐   │       │   ┌────────────────────────┐   │          │
│   │   │   Unleash Server       │   │       │   │   AWS AppConfig        │   │          │
│   │   │   (Docker :4242)       │   │       │   │   (Terraform managed)  │   │          │
│   │   │   ┌──────────────────┐ │   │       │   │   ┌──────────────────┐ │   │          │
│   │   │   │ PostgreSQL DB    │ │   │       │   │   │ Configuration    │ │   │          │
│   │   │   │ (unleash db)     │ │   │       │   │   │ Profile          │ │   │          │
│   │   │   └──────────────────┘ │   │       │   │   └──────────────────┘ │   │          │
│   │   └────────────────────────┘   │       │   └────────────────────────┘   │          │
│   │                                │       │                                │          │
│   │   UI: http://localhost:4242    │       │   Deployment: Gradual (prod)   │          │
│   │   Refresh: 15 seconds          │       │   Refresh: 60 seconds          │          │
│   │                                │       │                                │          │
│   └────────────────────────────────┘       └────────────────────────────────┘          │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**Provider Selection (Automatic):**

| Environment | APP_ENV | Provider | Server |
|-------------|---------|----------|--------|
| Local Development | `local` (default) | Unleash | Docker (localhost:4242) |
| QA | `qa` | AWS AppConfig | Terraform managed |
| Staging | `stg` | AWS AppConfig | Terraform managed |
| Production | `prod` | AWS AppConfig | Terraform managed (gradual deploy) |

**Available Feature Flags (53 total):**

| Flag | Default | Description |
|------|---------|-------------|
| `single_stock_analysis` | `true` | Core feature - single stock analysis |
| `watchlist_analysis` | `false` | Enable watchlist-based batch analysis |
| `premarket_analysis` | `false` | Enable pre-market analysis (4:00 AM - 9:30 AM ET) |
| `aftermarket_analysis` | `false` | Enable after-market analysis (4:00 PM - 8:00 PM ET) |
| `ml_analysis` | `true` | ML pipeline master switch — enables LSTM + XGBoost + Ensemble atomically. XGBoost auto-enabled when ON (no `ENABLE_XGBOOST` env var needed). Falls back to RandomForest if XGBoost is not installed. |
| `agent_<name>` × 48 | `true` | Per-agent flag for each of the 47 sub-agents (e.g. `agent_technical_analysis`, `agent_news`, `agent_sec_filing`, …). Orchestrator skips any agent whose flag is OFF. |

---

#### Enabling Feature Flags - Local Development (Unleash)

The `docker-compose.yml` uses `unleashorg/unleash-server:latest` (currently resolves to 7.5.1). Unleash starts automatically with all other services.

**Step 1: Start Unleash (with PostgreSQL)**

```bash
# Start all services including Unleash (postgres starts first due to healthcheck dependency)
docker compose up -d

# Validate health
docker compose ps
curl -s http://localhost:4242/health | jq
```

**Step 2: Configure Local App to use Unleash**

```bash
# Force local provider selection
export APP_ENV=local

# Optional: override Unleash connection settings
export UNLEASH_URL=http://localhost:4242/api
export UNLEASH_APP_NAME=stock-signal-api
export UNLEASH_API_TOKEN=default:development.unleash-insecure-api-token
```

`application.yml` equivalent:

```yaml
feature_flags:
  unleash:
    url: "http://localhost:4242/api"
    app_name: "stock-signal-api"
    refresh_interval_seconds: 15
  defaults:
    single_stock_analysis: true
    watchlist_analysis: false
    premarket_analysis: false
    aftermarket_analysis: false
```

**Step 3: Access Unleash Admin UI**

```bash
open http://localhost:4242
```

- **Default credentials:** `admin` / `unleash4all`
- Unleash environment to use for this project: `development`

**Step 4: Configure Feature Flags in Unleash**

Create these flags with the exact names below and enable/disable per your rollout:

| Feature flag | Recommended local setting | When to enable |
|--------------|---------------------------|----------------|
| `single_stock_analysis` | Enabled | Keep on for core single ticker analysis |
| `watchlist_analysis` | Disabled initially | Enable when testing batch/watchlist workflows |
| `premarket_analysis` | Disabled initially | Enable if you want 4:00 AM - 9:30 AM ET workflows |
| `aftermarket_analysis` | Disabled initially | Enable if you want 4:00 PM - 8:00 PM ET workflows |
| `ml_analysis` | Enabled | Keep on to enable LSTM + XGBoost + Ensemble ML pipeline; XGBoost auto-activates when this flag is ON |
| `agent_<name>` × 48 | All Enabled | Disable specific agent flags to skip individual sub-agents during testing |

Per-flag setup in UI:
1. Click **"New feature flag"**
2. Enter one flag name exactly (from the table above)
3. Select environment: **development**
4. Choose activation strategy (for local testing, **flexibleRollout** works well)
5. Toggle **Enabled** for the current test scenario
6. Repeat for each flag

**Step 5: API Tokens (Preconfigured for Local Docker)**

From `docker-compose.yml`:
- **Admin API:** `*:*.unleash-insecure-admin-api-token`
- **Client API:** `default:development.unleash-insecure-api-token`
- **Frontend API:** `default:development.unleash-insecure-frontend-token`

**Step 6: Test Feature Flags**

```bash
# Test from Python
python -c "
from infrastructure.feature_flags import is_feature_enabled, FeatureFlag, get_all_flags

print('All flags:', get_all_flags())
print('Watchlist enabled:', is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS))
print('Premarket enabled:', is_feature_enabled(FeatureFlag.PREMARKET_ANALYSIS))
"

# Test from API
curl http://localhost:8000/api/v1/features | jq
```

---

#### Enabling Feature Flags - AWS (AppConfig)

**Step 1: Deploy AppConfig with Terraform**

```bash
# Navigate to environment
cd terraform/environments/qa  # or stg, prod

# Initialize and apply
terraform init
terraform plan
terraform apply
```

**Step 2: Get AppConfig IDs from Terraform Output**

```bash
terraform output appconfig_application_id
terraform output appconfig_environment_id
terraform output appconfig_profile_id
```

**Step 3: Configure Environment Variables**

```bash
# Set environment
export APP_ENV=qa  # or stg, prod

# Set AppConfig IDs (from terraform output)
export APPCONFIG_APPLICATION_ID="abc123"
export APPCONFIG_ENVIRONMENT_ID="def456"
export APPCONFIG_PROFILE_ID="ghi789"
```

**Step 4: Enable Flags via Terraform Variables**

Edit `terraform/environments/qa/terraform.tfvars`:

```hcl
# Feature Flags
enable_watchlist_analysis   = true
enable_premarket_analysis   = true
enable_aftermarket_analysis = true
```

Then apply:

```bash
terraform apply
```

**Step 5: Verify in AWS Console**

1. Go to AWS Console → AppConfig
2. Select application: `stock-signal-qa`
3. View configuration profile: `feature-flags`
4. Check deployment status

---

#### Feature Flags API Reference

**Get All Flags:**
```bash
curl http://localhost:8000/api/v1/features
```

Response:
```json
{
  "flags": {
    "single_stock_analysis": true,
    "watchlist_analysis": false,
    "premarket_analysis": false,
    "aftermarket_analysis": false,
    "ml_analysis": true,
    "agent_technical_analysis": true,
    "agent_news": true
  },
  "provider": "unleash",
  "environment": "local"
}
```

**Check Specific Flag:**
```bash
curl -X POST http://localhost:8000/api/v1/features/check \
  -H "Content-Type: application/json" \
  -d '{"flag_name": "watchlist_analysis"}'
```

Response:
```json
{
  "flag_name": "watchlist_analysis",
  "enabled": false
}
```

**Check with Context (for targeting):**
```bash
curl -X POST http://localhost:8000/api/v1/features/check \
  -H "Content-Type: application/json" \
  -d '{"flag_name": "premarket_analysis", "context": {"user_id": "123"}}'
```

---

#### Usage in Code

```python
from infrastructure.feature_flags import is_feature_enabled, FeatureFlag, get_all_flags

# Simple boolean check
if is_feature_enabled(FeatureFlag.WATCHLIST_ANALYSIS):
    run_watchlist_analysis()

# With user targeting context
if is_feature_enabled(FeatureFlag.PREMARKET_ANALYSIS, context={"user_id": "123"}):
    run_premarket_analysis()

# Get all flags at once
all_flags = get_all_flags()
print(all_flags)
# {'single_stock_analysis': True, 'watchlist_analysis': False, ...}
```

---

#### Troubleshooting

| Issue | Solution |
|-------|----------|
| Unleash not starting | Check PostgreSQL is healthy: `docker compose logs postgres` |
| Flags returning defaults | Verify Unleash is reachable and flags are created in UI |
| AppConfig not working | Check IAM permissions and environment variables |
| Flag changes not reflecting | Wait for refresh interval (15s local, 60s AWS) |

**Debug Mode:**
```bash
# Check which provider is being used
python -c "
from infrastructure.feature_flags import get_feature_flag_service
svc = get_feature_flag_service()
print('Provider:', type(svc._provider).__name__)
"
```

---

## Local Kubernetes Development (Minikube)

Run the complete application stack locally in Kubernetes using Minikube. This is useful for testing Kubernetes deployments before deploying to AWS EKS.

### Prerequisites

```bash
# Install Minikube (macOS)
brew install minikube

# Install Minikube (Linux)
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Install kubectl
brew install kubectl  # macOS
# or
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install Helm
brew install helm  # macOS
# or
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Quick Start

```bash
# 1. Start Minikube with sufficient resources
minikube start --cpus=4 --memory=8192 --driver=docker

# 2. Enable required addons
minikube addons enable ingress
minikube addons enable metrics-server

# 3. Build Docker image inside Minikube
eval $(minikube docker-env)
docker build -t stock-signal-api:latest .

# 4. Deploy with Helm using local values
helm upgrade --install stock-signal ./helm/stock-signal-api \
  -f ./helm/stock-signal-api/values-local.yaml \
  --set secrets.llmApiKey="${OPENAI_API_KEY}"

# 5. Check deployment status
kubectl get pods -w

# 6. Access the API
minikube service stock-signal-api --url
```

### Detailed Setup

#### Step 1: Start Minikube

```bash
# Start with recommended resources
minikube start \
  --cpus=4 \
  --memory=8192 \
  --disk-size=30g \
  --driver=docker

# Verify cluster is running
minikube status
kubectl cluster-info
```

#### Step 2: Build Docker Image

```bash
# Point Docker CLI to Minikube's Docker daemon
eval $(minikube docker-env)

# Build the image (now available inside Minikube)
docker build -t stock-signal-api:latest .

# Verify image is available
docker images | grep stock-signal-api
```

#### Step 3: Deploy with Helm

```bash
# Deploy with local configuration
helm upgrade --install stock-signal ./helm/stock-signal-api \
  -f ./helm/stock-signal-api/values-local.yaml \
  --set secrets.llmApiKey="${OPENAI_API_KEY}"

# Watch pods come up
kubectl get pods -w

# Check logs
kubectl logs -f deployment/stock-signal-api
```

#### Step 4: Access the Application

```bash
# Method 1: Minikube service tunnel
minikube service stock-signal-api --url
# Returns something like: http://127.0.0.1:52345

# Method 2: Port forwarding
kubectl port-forward svc/stock-signal-api 8000:8000
# Access at: http://localhost:8000

# Method 3: Ingress (if configured)
# Add to /etc/hosts: $(minikube ip) stock-signal.local
echo "$(minikube ip) stock-signal.local" | sudo tee -a /etc/hosts
# Access at: http://stock-signal.local

# Test the API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/features
```

### Local Stack Options

The `values-local.yaml` file configures the following stack:

```yaml
# values-local.yaml highlights
appEnv: local                    # Uses Unleash for feature flags
replicaCount: 1                  # Single replica for local

# AWS services disabled
aws:
  bedrock: { enabled: false }
  msk: { enabled: false }
  secretsManager: { enabled: false }

# Local services enabled
config:
  kafka: { enabled: true }       # Local Kafka
  qdrant: { enabled: true }      # Local Qdrant

# Optional: Enable Ollama for fully local LLM
ollama:
  enabled: true
  models: [llama3.1]
```

#### Deploy with Local Ollama (No Cloud LLM)

```bash
# Deploy with Ollama enabled for fully local setup
helm upgrade --install stock-signal ./helm/stock-signal-api \
  -f ./helm/stock-signal-api/values-local.yaml \
  --set ollama.enabled=true \
  --set config.llm.model="ollama/llama3.1" \
  --set config.llm.apiBase="http://stock-signal-ollama:11434"

# Wait for Ollama to download the model (can take 5-10 min)
kubectl logs -f deployment/stock-signal-ollama
```

#### Deploy with Feature Flags (Unleash)

To use feature flags in Minikube, deploy Unleash alongside:

```bash
# Option 1: Use Docker Compose Unleash from host
# Start Unleash on host machine first
docker compose up -d

# Configure app to reach Unleash on host
# macOS: host.docker.internal works
# Linux: Use minikube's host IP
UNLEASH_HOST=$(minikube ssh -- ip route show default | awk '{print $3}')

helm upgrade --install stock-signal ./helm/stock-signal-api \
  -f ./helm/stock-signal-api/values-local.yaml \
  --set secrets.llmApiKey="${OPENAI_API_KEY}" \
  --set env.UNLEASH_URL="http://${UNLEASH_HOST}:4242/api"

# Option 2: Deploy Unleash in Minikube
# (Use a separate Helm chart for Unleash)
helm repo add unleash https://docs.getunleash.io/helm-charts
helm install unleash unleash/unleash --set postgresql.enabled=true
```

### Useful Commands

```bash
# View all resources
kubectl get all

# View pod logs
kubectl logs -f deployment/stock-signal-api

# Shell into pod
kubectl exec -it deployment/stock-signal-api -- /bin/sh

# View Helm release
helm list
helm get values stock-signal

# Restart deployment
kubectl rollout restart deployment/stock-signal-api

# Delete deployment
helm uninstall stock-signal

# Stop Minikube (preserves state)
minikube stop

# Delete Minikube cluster
minikube delete
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Image not found | Ensure `eval $(minikube docker-env)` was run before `docker build` |
| Pod CrashLoopBackOff | Check logs: `kubectl logs <pod-name>` |
| Out of memory | Increase Minikube memory: `minikube config set memory 12288` |
| Ingress not working | Ensure addon is enabled: `minikube addons enable ingress` |
| Can't reach services | Use `minikube tunnel` for LoadBalancer services |
| Ollama slow to start | First run downloads model (~4GB), subsequent starts are fast |

### Resource Requirements

| Component | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| Minikube minimum | 2 | 4GB | Basic functionality |
| Minikube recommended | 4 | 8GB | With Kafka + Qdrant |
| With Ollama | 4 | 12GB+ | LLM requires significant RAM |

---

## Installation

```bash
# Using pip
pip install -r requirements.txt

# Using Make
make install
```

## Makefile Commands

The project includes a Makefile for common tasks:

```bash
make help           # Show all available commands
```

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make run` | Run single-agent mode |
| `make run-multi` | Run multi-agent mode |
| `make run-full` | Run multi-agent with Kafka + Qdrant |
| `make api` | Start FastAPI server |
| `make test` | Run tests |
| `make test-cov` | Run tests with coverage |
| `make infra-up` | Start Kafka + Qdrant (Docker Compose) |
| `make infra-down` | Stop infrastructure |
| `make docker-build` | Build Docker image |
| `make docker-push` | Push image to registry |
| `make helm-install` | Install Helm chart to Kubernetes |
| `make helm-upgrade` | Upgrade Helm release |
| `make helm-uninstall` | Uninstall Helm release |

**With custom parameters:**
```bash
make run TICKER=MSFT DAYS=60 MODEL=gpt-4o
make docker-build IMAGE_TAG=v1.0.0
make helm-install NAMESPACE=production RELEASE_NAME=stock-api
```

---

## Configuration

### Application Configuration (application.yml)

The project uses `application.yml` for configuration with environment variable overrides.

**Step 1: Create your configuration file**
```bash
cp application.yml.example application.yml
```

**Step 2: Edit for your environment**
```yaml
# application.yml
kafka:
  bootstrap_servers: "kafka.your-domain.com:9092"

qdrant:
  host: "qdrant.your-domain.com"
  port: 6333

llm:
  model: "claude-sonnet-4-6"
  api_base: null  # Set for Ollama: "http://localhost:11434"

observability:
  langfuse:
    enabled: true
    host: "https://cloud.langfuse.com"
```

**Configuration Priority:**
1. Environment variables (highest priority)
2. `application.yml` values
3. Default values (fallback)

**Key Environment Variables:**
| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker(s) | `localhost:9092` |
| `QDRANT_HOST` | Qdrant server host | `localhost` |
| `QDRANT_PORT` | Qdrant server port | `6333` |
| `QDRANT_DATABASE` | Qdrant database namespace | `stock-signal` |
| `POSTGRES_ENABLED` | Enable PostgreSQL historical cache | `false` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DATABASE` | PostgreSQL database name | `stock_signal` |
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | - |
| `POSTGRES_PRICES_TABLE` | Daily OHLCV table | `stock_prices_daily` |
| `POSTGRES_BACKFILL_YEARS` | Backfill years on cache miss | `5` |
| `LLM_MODEL` | Default LLM model | `claude-sonnet-4-6` |
| `LLM_API_BASE` | API base URL (for Ollama) | `null` |
| `ENABLE_XGBOOST` | Override to force-enable XGBoost regardless of `ml_analysis` flag (optional) | auto via flag |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | - |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | - |

**Report Actions (SMS & Email) - Optional:**
| Variable | Description | Default |
|----------|-------------|---------|
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | - |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | - |
| `TWILIO_FROM_NUMBER` | Twilio sender phone number | - |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username/email | - |
| `SMTP_PASSWORD` | SMTP password or app password | - |
| `SMTP_FROM_EMAIL` | Sender email address | (same as SMTP_USER) |

---

## LLM Configuration

This project uses [LiteLLM](https://docs.litellm.ai/) for model-agnostic LLM calls, supporting 100+ LLM providers. Below are step-by-step instructions for popular options.

### Option 1: Local Llama 3.1 (via Ollama) - FREE

Run LLMs locally on your machine with no API costs.

**Step 1: Install Ollama**
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download
```

**Step 2: Pull and run Llama 3.1**
```bash
# Pull the model (one-time download, ~4.7GB for 8B model)
ollama pull llama3.1

# Start Ollama server (runs on http://localhost:11434)
ollama serve
```

**Step 3: Run the stock signal generator**
```bash
# Single-agent mode
python main.py --ticker AAPL --model ollama/llama3.1 --base-url http://localhost:11434

# Multi-agent mode (comprehensive analysis)
python main.py --ticker AAPL --multi-agent --model ollama/llama3.1 --base-url http://localhost:11434

# With verbose output
python main.py --ticker MSFT --multi-agent --verbose --model ollama/llama3.1 --base-url http://localhost:11434
```

**Available Ollama models:**
```bash
ollama pull llama3.1:70b      # Larger, more capable (requires 48GB+ RAM)
ollama pull llama3.1:8b       # Default, good balance
ollama pull mistral           # Fast, good for quick analysis
ollama pull codellama         # Code-focused model
ollama pull mixtral           # Mixture of experts model
```

---

### Option 2: OpenAI GPT-5.2 / GPT-4o

Use OpenAI's latest models for high-quality analysis.

**Step 1: Get API Key**
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Set it as an environment variable:

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

**Step 2: Run with OpenAI models**
```bash
# GPT-5.2 (latest, most capable)
python main.py --ticker AAPL --model gpt-5.2

# GPT-4o (fast, cost-effective)
python main.py --ticker AAPL --model gpt-4o

# GPT-4o-mini (fastest, cheapest)
python main.py --ticker AAPL --model gpt-4o-mini

# Multi-agent mode with GPT-5.2
python main.py --ticker GOOGL --multi-agent --verbose --model gpt-5.2
```

**Model comparison:**
| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| gpt-5.2 | Medium | $$$ | Complex analysis, highest accuracy |
| gpt-4o | Fast | $$ | Balanced performance |
| gpt-4o-mini | Fastest | $ | Quick scans, high volume |

---

### Option 3: Anthropic Claude 4.6 (Default)

Use Anthropic's Claude for nuanced financial analysis. **`claude-sonnet-4-6` is the default model** used by the dashboard and n8n workflows.

**Step 1: Get API Key**
1. Go to https://console.anthropic.com/
2. Create an API key
3. Set it as an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
```

**Step 2: Run with Claude models**
```bash
# Claude Sonnet 4.6 (default — balanced, fast)
python main.py --ticker AAPL --model claude-sonnet-4-6

# Claude Opus 4.6 (most capable)
python main.py --ticker AAPL --model claude-opus-4-6

# Claude Haiku 4.5 (fastest, lowest cost)
python main.py --ticker AAPL --model claude-haiku-4-5-20251001

# Multi-agent mode with Claude Sonnet 4.6
python main.py --ticker TSLA --multi-agent --verbose --model claude-sonnet-4-6
```

**Model comparison:**
| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| claude-opus-4-6 | Slow | $$$$ | Deep analysis, complex reasoning |
| claude-sonnet-4-6 | Medium | $$ | Default — balanced performance, production use |
| claude-haiku-4-5 | Fastest | $ | Quick scans, high volume |

---

### Option 4: Google Gemini

Use Google's Gemini models.

**Step 1: Get API Key**
1. Go to https://aistudio.google.com/apikey
2. Create an API key
3. Set it as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Step 2: Run with Gemini models**
```bash
# Gemini 2.0 Flash (recommended)
python main.py --ticker AAPL --model gemini/gemini-2.0-flash

# Gemini 1.5 Pro
python main.py --ticker AAPL --model gemini/gemini-1.5-pro

# Multi-agent mode
python main.py --ticker NVDA --multi-agent --model gemini/gemini-2.0-flash
```

---

### Option 5: Azure OpenAI

Use OpenAI models through Azure.

**Step 1: Configure Azure**
```bash
export AZURE_API_KEY="your-azure-api-key"
export AZURE_API_BASE="https://your-resource.openai.azure.com"
export AZURE_API_VERSION="2024-02-15-preview"
```

**Step 2: Run with Azure OpenAI**
```bash
# Use your deployment name
python main.py --ticker AAPL --model azure/your-deployment-name
```

---

### Option 6: AWS Bedrock

Use models through AWS Bedrock.

**Step 1: Configure AWS credentials**
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION_NAME="us-east-1"
```

**Step 2: Run with Bedrock models**
```bash
# Claude on Bedrock
python main.py --ticker AAPL --model bedrock/anthropic.claude-3-sonnet-20240229-v1:0

# Llama on Bedrock
python main.py --ticker AAPL --model bedrock/meta.llama3-70b-instruct-v1:0
```

---

### Option 7: Other Providers

LiteLLM supports 100+ providers. Here are more examples:

```bash
# Groq (ultra-fast inference)
export GROQ_API_KEY="your-key"
python main.py --ticker AAPL --model groq/llama-3.1-70b-versatile

# Together AI
export TOGETHER_API_KEY="your-key"
python main.py --ticker AAPL --model together_ai/meta-llama/Llama-3-70b-chat-hf

# Mistral AI
export MISTRAL_API_KEY="your-key"
python main.py --ticker AAPL --model mistral/mistral-large-latest

# Cohere
export COHERE_API_KEY="your-key"
python main.py --ticker AAPL --model cohere/command-r-plus

# Perplexity
export PERPLEXITY_API_KEY="your-key"
python main.py --ticker AAPL --model perplexity/llama-3.1-sonar-large-128k-online

# Fireworks AI
export FIREWORKS_API_KEY="your-key"
python main.py --ticker AAPL --model fireworks_ai/llama-v3p1-70b-instruct

# DeepSeek
export DEEPSEEK_API_KEY="your-key"
python main.py --ticker AAPL --model deepseek/deepseek-chat
```

---

### Environment Variables Summary

Create a `.env` file or export these variables:

```bash
# Choose ONE provider (or multiple for fallback)
export OPENAI_API_KEY="sk-..."           # OpenAI
export ANTHROPIC_API_KEY="sk-ant-..."    # Anthropic
export GEMINI_API_KEY="..."              # Google
export GROQ_API_KEY="..."                # Groq
export TOGETHER_API_KEY="..."            # Together AI
export MISTRAL_API_KEY="..."             # Mistral
export COHERE_API_KEY="..."              # Cohere

# Default model (optional)
export LLM_MODEL="claude-sonnet-4-6"     # Used when --model not specified
```

---

## Quick Start

```bash
# Launch Streamlit Dashboard (default)
python main.py

# Launch React Dashboard (alternative UI)
python main.py --react

# CLI mode without dashboard
python main.py --ticker AAPL --multi-agent --nogui

# Explicit multi-agent mode with verbose output
python main.py --ticker AAPL --multi-agent --verbose --nogui

# With specific LLM
python main.py --ticker MSFT --multi-agent --model claude-sonnet-4-5-20251101 --nogui

# With local Ollama
python main.py --ticker GOOGL --multi-agent --model ollama/llama3.1 --base-url http://localhost:11434 --nogui

# With infrastructure (Kafka + Qdrant + PostgreSQL + Unleash)
docker compose up -d
python main.py --ticker AAPL --multi-agent --kafka --qdrant --nogui
```

### Dashboard Options

| Dashboard | Port | Command | Best For |
|-----------|------|---------|----------|
| Streamlit | 8501 | `python main.py` | Quick local analysis |
| React | 3000 | `python main.py --react` | Modern UI, production |

**React Dashboard Setup:**
```bash
# First time setup
cd frontend && npm install && cd ..

# Launch React dashboard
python main.py --react

# In separate terminal, start API server
python -m uvicorn api:app --reload --port 8000
```

## CLI Reference

```bash
python main.py [OPTIONS]
```

| Option | Description | Default |
|--------|-------------|---------|
| `--ticker` | Stock ticker symbol (required for --nogui) | - |
| `--days` | Number of historical days to analyze | 365 |
| `--model` | LLM model to use | gpt-4o-mini |
| `--base-url` | API base URL (for Ollama/local models) | None |
| `--multi-agent` | Use up to 47 domain-specialized agents for comprehensive analysis | Enabled by default |
| `--verbose` | Show detailed agent outputs | False |
| `--kafka` | Enable Kafka streaming | False |
| `--qdrant` | Enable Qdrant vector storage | False |
| `--nogui` | Disable dashboard, run CLI only | False |
| `--react` | Use React dashboard instead of Streamlit | False |
| `--debug` | Enable debug mode for agent data | False |

**Examples:**
```bash
# Basic usage
python main.py --ticker AAPL

# Analyze 60 days of data
python main.py --ticker TSLA --days 60

# Full analysis with Claude
python main.py --ticker NVDA --multi-agent --verbose --model claude-opus-4-5-20251101

# Local LLM with infrastructure
python main.py --ticker MSFT --multi-agent --kafka --qdrant \
  --model ollama/llama3.1 --base-url http://localhost:11434
```

---

## REST API

Start the API server:

```bash
# Development
uvicorn api:app --reload

# Production
uvicorn api:app --host 0.0.0.0 --port 8000
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/signal` | Generate signal (full options) |
| GET | `/signal/{ticker}` | Quick signal generation |
| GET | `/docs` | Swagger UI documentation |

### Example Requests

```bash
# POST request with default model (gpt-4o-mini)
curl -X POST http://localhost:8000/signal \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "mode": "multi", "verbose": true}'

# POST request with specific model
curl -X POST http://localhost:8000/signal \
  -H "Content-Type: application/json" \
  -d '{"ticker": "GOOGL", "mode": "multi", "model": "claude-opus-4-5-20251101"}'

# POST request with GPT-5.2
curl -X POST http://localhost:8000/signal \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TSLA", "mode": "multi", "model": "gpt-5.2", "verbose": true}'

# GET request (simple, uses default model)
curl http://localhost:8000/signal/AAPL?mode=multi

# Validate a ticker before analysis
curl http://localhost:8000/validate/NVDA
```

### Response

```json
{
  "ticker": "AAPL",
  "signal": "BUY",
  "confidence": 0.85,
  "target_price": 185.50,
  "reasoning": "Detailed synthesis across active domain-specialized agents with ML cross-check and reconciliation context...",
  "mode": "multi",
  "agents_used": 42,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Observability

### Langfuse Integration

Enable Langfuse for LLM tracing and monitoring:

```bash
# Set environment variables
export LANGFUSE_ENABLED=true
export LANGFUSE_PUBLIC_KEY=pk-xxx
export LANGFUSE_SECRET_KEY=sk-xxx
export LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted

# Run with observability
python main.py --ticker AAPL --multi-agent
```

### LiteLLM Callbacks

Built-in observability without Langfuse:

```python
from observability import setup_observability, get_observability_stats

# Initialize
setup_observability()

# After execution
stats = get_observability_stats()
print(f"LLM calls: {stats['llm_stats']['call_count']}")
print(f"Total tokens: {stats['llm_stats']['total_tokens']}")
```

### What Gets Tracked

- LLM API calls (model, tokens, latency)
- Agent execution times
- Signal generation traces
- Errors and failures

## Output Format

```json
{
  "signal": "BUY",
  "confidence": 0.85,
  "target_price": 185.50,
  "potential_upside_pct": 12.5,
  "potential_downside_pct": 5.2,
  "stop_loss": 156.75,
  "sentiment_score": 0.72,
  "reasoning": "Detailed narrative including final decision source, ML/ensemble view, and agent-by-agent rationale...",
  "reasoning_brief": "Short synthesis summary...",
  "mode": "multi-agent",
  "agents_used": 42,
  "llm_signal": "BUY",
  "llm_confidence": 0.82,
  "majority_signal": "BUY",
  "majority_vote_ratio": 0.57,
  "majority_vote_counts": {"BUY": 27, "HOLD": 14, "SELL": 6},
  "decision_source": "llm_aligned_with_majority",
  "sources": [
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/quote/AAPL"},
    {"name": "SEC EDGAR", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=AAPL"},
    {"name": "Zacks Investment Research", "url": "https://www.zacks.com/stock/quote/AAPL"}
  ]
}
```

- Dashboard behavior: `Report Actions` render at the top of the results section.
- Status behavior: ML phase status shows start + active pipeline/model policy details.

## Project Structure

```
├── main.py                    # CLI entry point
├── api.py                     # FastAPI REST API
├── dashboard.py               # Streamlit dashboard
├── observability.py           # Langfuse/LiteLLM observability
├── agentic_ai_base.py         # Abstract base class for all agents
├── stock_signal_agent.py      # Single-agent implementation
├── Makefile                   # Common development commands
├── Dockerfile                 # Container image build
├── docker-compose.yml         # Kafka + Qdrant infrastructure
├── application.yml.example    # Configuration template
├── agents/                    # Multi-agent implementations (47 agents)
│   ├── orchestrator_agent.py  # Coordinates all sub-agents
│   ├── technical_analysis_agent.py
│   ├── news_agent.py
│   ├── sec_filing_agent.py
│   ├── sentiment_agent.py
│   ├── reddit_agent.py        # Reddit sentiment analysis
│   ├── stocktwits_agent.py    # StockTwits social data
│   ├── options_flow_agent.py  # Options flow analysis
│   └── ... (40+ more data source agents)
├── ml/                        # Machine Learning module
│   ├── __init__.py
│   ├── price_predictor.py     # LSTM 5-day price prediction
│   ├── signal_classifier.py   # RandomForest default, optional XGBoost BUY/SELL/HOLD classifier
│   └── ensemble_scorer.py     # Weighted ensemble voting
├── infrastructure/            # Optional infrastructure
│   ├── config.py              # YAML + env var configuration
│   ├── kafka_producer.py      # Kafka wrapper
│   ├── kafka_consumer.py
│   ├── qdrant_store.py        # Qdrant vector DB wrapper
│   └── embeddings.py          # Sentence transformers
├── schemas/                   # Pydantic models
│   └── messages.py
├── helm/                      # Kubernetes Helm chart
│   └── stock-signal-api/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
└── tests/                     # Test suite (87%+ coverage)
    ├── test_api.py
    ├── test_agents.py
    ├── test_ml.py             # ML module tests
    └── test_dashboard.py      # Dashboard tests
```

## Docker & Kubernetes Deployment

### Docker

**Build and run locally:**
```bash
# Build image
make docker-build
# or
docker build -t stock-signal-api:latest .

# Run container
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  stock-signal-api:latest

# Access API
curl http://localhost:8000/health
curl http://localhost:8000/signal/AAPL
```

**Push to registry:**
```bash
make docker-push REGISTRY=your-registry.com IMAGE_TAG=v1.0.0
# or
docker tag stock-signal-api:latest your-registry.com/stock-signal-api:v1.0.0
docker push your-registry.com/stock-signal-api:v1.0.0
```

---

### Kubernetes (Helm)

The project includes a Helm chart for Kubernetes deployment.

**Prerequisites:**
- Kubernetes cluster (minikube, EKS, GKE, AKS, etc.)
- Helm 3.x installed
- kubectl configured

**Step 1: Build and push Docker image**
```bash
make docker-build IMAGE_TAG=v1.0.0
make docker-push REGISTRY=your-registry.com IMAGE_TAG=v1.0.0
```

**Step 2: Install with Helm**
```bash
# Basic installation
helm install stock-signal helm/stock-signal-api \
  --set image.repository=your-registry.com/stock-signal-api \
  --set image.tag=v1.0.0 \
  --set secrets.llmApiKey=$OPENAI_API_KEY

# With custom namespace
helm install stock-signal helm/stock-signal-api \
  --namespace production \
  --create-namespace \
  --set image.repository=your-registry.com/stock-signal-api \
  --set image.tag=v1.0.0 \
  --set secrets.llmApiKey=$OPENAI_API_KEY

# Using Makefile
make helm-install NAMESPACE=production
```

**Step 3: Configure with values file**

Create `my-values.yaml`:
```yaml
replicaCount: 3

image:
  repository: your-registry.com/stock-signal-api
  tag: v1.0.0

config:
  kafka:
    enabled: true
    bootstrapServers: "kafka.your-domain.com:9092"
  qdrant:
    enabled: true
    host: "qdrant.your-domain.com"
  llm:
    model: "gpt-4o"

secrets:
  llmApiKey: "sk-your-openai-key"
  langfusePublicKey: "pk-xxx"
  langfuseSecretKey: "sk-xxx"

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: stock-signal.your-domain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: stock-signal-tls
      hosts:
        - stock-signal.your-domain.com

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 512Mi
```

Install with values file:
```bash
helm install stock-signal helm/stock-signal-api -f my-values.yaml
```

**Step 4: Access the API**
```bash
# Port forward for testing
kubectl port-forward svc/stock-signal-stock-signal-api 8000:8000

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/signal/AAPL?mode=multi
```

**Helm Commands:**
```bash
# Lint chart
make helm-lint

# Preview templates
make helm-template

# Upgrade release
make helm-upgrade NAMESPACE=production

# Uninstall
make helm-uninstall NAMESPACE=production

# View release status
helm status stock-signal -n production
```

**High Availability Configuration:**

The Helm chart includes HA features enabled by default:

```yaml
# Pod Disruption Budget - ensures minimum availability during node maintenance
podDisruptionBudget:
  enabled: true
  minAvailable: 1

# Pod Anti-Affinity - spreads pods across different nodes
podAntiAffinity:
  enabled: true
  type: "soft"  # or "hard" for strict enforcement
  topologyKey: "kubernetes.io/hostname"

# Topology Spread - distribute across availability zones
topologySpreadConstraints:
  enabled: true
  maxSkew: 1
  topologyKey: "topology.kubernetes.io/zone"
  whenUnsatisfiable: "ScheduleAnyway"
```

For production, recommended settings:
```yaml
replicaCount: 3

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10

podDisruptionBudget:
  enabled: true
  minAvailable: 2

podAntiAffinity:
  enabled: true
  type: "hard"
  topologyKey: "topology.kubernetes.io/zone"
```

---

### Self-Contained Deployment with Ollama (No External LLM)

Deploy a fully self-contained system using local Llama 3.1 with no external API dependencies:

```bash
helm install stock-signal helm/stock-signal-api \
  --set image.repository=your-registry.com/stock-signal-api \
  --set image.tag=v1.0.0 \
  --set ollama.enabled=true \
  --set ollama.replicaCount=2
```

Or with a values file (`ollama-values.yaml`):

```yaml
replicaCount: 3

image:
  repository: your-registry.com/stock-signal-api
  tag: v1.0.0

# Enable Ollama - local LLM server
ollama:
  enabled: true
  replicaCount: 2

  # Models to pre-load (pulled during init)
  models:
    - llama3.1
    # - llama3.1:70b  # Larger model (requires more resources)
    # - mistral

  # Persistent storage for models
  persistence:
    enabled: true
    size: 50Gi
    # For multiple replicas, use ReadWriteMany storage:
    # storageClass: "efs-sc"  # AWS EFS
    # storageClass: "nfs"     # NFS

  # Resource requirements (adjust for your model)
  resources:
    requests:
      cpu: 2000m
      memory: 8Gi
    limits:
      cpu: 8000m
      memory: 16Gi

  # High availability
  podDisruptionBudget:
    enabled: true
    minAvailable: 1

  podAntiAffinity:
    enabled: true
    type: "soft"

  # GPU support (optional)
  gpu:
    enabled: false
    # count: 1

# No API key needed - using local Ollama
secrets:
  llmApiKey: ""
```

Install:
```bash
helm install stock-signal helm/stock-signal-api -f ollama-values.yaml
```

**Architecture with Ollama:**
```
┌─────────────────────┐     ┌─────────────────────┐
│  FastAPI API        │────▶│  Ollama Service     │
│  (3 replicas, HA)   │     │  (2 replicas, HA)   │
└─────────────────────┘     └─────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│  PVC: Config        │     │  PVC: Models (50Gi) │
└─────────────────────┘     │  (ReadWriteMany)    │
                            └─────────────────────┘
```

**Important Notes:**
- For multiple Ollama replicas, use `ReadWriteMany` storage (EFS, NFS, Azure Files, GCP Filestore)
- Models are pulled once during init and shared across replicas
- Increase resources for larger models (70B needs ~48GB RAM)
- GPU support is optional but recommended for production performance

---

### Using Managed Services

For production, consider using managed services instead of self-hosted:

| Component | Managed Options |
|-----------|-----------------|
| Kafka | AWS MSK, Confluent Cloud, Azure Event Hubs |
| Qdrant | Qdrant Cloud |
| Kubernetes | EKS, GKE, AKS |

Configure via `application.yml` or Helm values:
```yaml
config:
  kafka:
    enabled: true
    bootstrapServers: "pkc-xxxxx.us-east-1.aws.confluent.cloud:9092"
  qdrant:
    enabled: true
    host: "xxxxx.us-east-1.aws.cloud.qdrant.io"
    port: 6333
```

---

### Terraform Deployment (AWS)

The project includes comprehensive Terraform infrastructure for deploying to AWS with EKS, MSK, OpenSearch, and Bedrock.

#### Prerequisites

```bash
# Required tools
aws --version         # AWS CLI v2.x
terraform --version   # Terraform >= 1.5.0
kubectl version       # kubectl >= 1.28
helm version          # Helm >= 3.12

# AWS credentials configured
aws configure
aws sts get-caller-identity
```

#### Environment Configuration

The application supports environment-based configuration via `APP_ENV`:

| Environment | APP_ENV | LLM | Kafka | Vector DB |
|------------|---------|-----|-------|-----------|
| Local | `local` | Ollama/OpenAI | Self-hosted | Qdrant |
| QA | `qa` | AWS Bedrock | Amazon MSK | OpenSearch |
| Staging | `stg` | AWS Bedrock | Amazon MSK | OpenSearch |
| Production | `prod` | AWS Bedrock | Amazon MSK | OpenSearch |

#### Step 1: Initialize Terraform Backend

```bash
# Create S3 bucket for Terraform state (one-time setup)
aws s3 mb s3://stock-signal-terraform-state-${AWS_ACCOUNT_ID} --region us-east-1

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name stock-signal-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

#### Step 2: Deploy Infrastructure

```bash
# Navigate to environment directory
cd terraform/environments/qa  # or stg, prod

# Initialize Terraform
terraform init

# Review the plan
terraform plan -out=tfplan

# Apply infrastructure
terraform apply tfplan

# Get EKS credentials
aws eks update-kubeconfig --name stock-signal-qa --region us-east-1
```

#### Step 3: Deploy Application with Helm

```bash
# Add required Helm repos
helm repo add aws-load-balancer-controller https://aws.github.io/eks-charts
helm repo update

# Install AWS Load Balancer Controller
helm install aws-load-balancer-controller aws-load-balancer-controller/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=stock-signal-qa \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

# Deploy Stock Signal API
helm upgrade --install stock-signal ./helm/stock-signal-api \
  -f ./helm/stock-signal-api/values-qa.yaml \
  --namespace stock-signal \
  --create-namespace
```

#### Step 4: Deploy React Frontend (Optional)

```bash
# Build frontend
cd frontend
npm install
npm run build

# Sync to S3 (bucket created by Terraform)
aws s3 sync dist/ s3://stock-signal-frontend-qa/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"
```

#### Environment Sizing Reference

| Component | QA | STG | PROD |
|-----------|-----|-----|------|
| **EKS Nodes** | 2x t3.large | 3x m5.large | 6x m5.xlarge |
| **MSK Brokers** | 3x kafka.m5.large | 3x kafka.m5.large | 6x kafka.m5.xlarge |
| **OpenSearch** | 2x t3.medium.search | 3x m5.large.search | 6x m5.xlarge.search |
| **API Replicas** | 2 | 3 | 6 |
| **Est. Monthly Cost** | ~$400 | ~$800 | ~$2,000+ |

#### Terraform Module Structure

```
terraform/
├── environments/
│   ├── qa/
│   │   ├── main.tf           # Module composition
│   │   ├── backend.tf        # S3 backend config
│   │   └── terraform.tfvars  # QA-specific values
│   ├── stg/
│   └── prod/
└── modules/
    ├── vpc/          # VPC, subnets, NAT gateways
    ├── eks/          # EKS cluster, node groups, IRSA
    ├── msk/          # Amazon MSK Kafka cluster
    ├── opensearch/   # OpenSearch with k-NN plugin
    ├── iam/          # IAM roles and policies
    ├── secrets/      # Secrets Manager secrets
    └── frontend/     # S3 + CloudFront for React
```

#### Verification Commands

```bash
# Verify EKS cluster
kubectl get nodes
kubectl get pods -n stock-signal

# Verify MSK connectivity
aws kafka list-clusters --region us-east-1

# Verify OpenSearch
aws opensearch describe-domain --domain-name stock-signal-qa

# Test API endpoint
curl https://$(kubectl get svc stock-signal-api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')/health

# Test frontend (if deployed)
curl https://$(terraform output -raw cloudfront_domain_name)/
```

#### Cleanup

```bash
# Remove Helm releases
helm uninstall stock-signal -n stock-signal

# Destroy infrastructure (careful!)
cd terraform/environments/qa
terraform destroy
```

---

## Supported Tickers

The system supports **any valid US market stock ticker**:

```bash
# Major stocks
python main.py --ticker AAPL    # Apple
python main.py --ticker MSFT    # Microsoft
python main.py --ticker GOOGL   # Alphabet
python main.py --ticker TSLA    # Tesla
python main.py --ticker NVDA    # NVIDIA
python main.py --ticker JPM     # JPMorgan Chase

# Class shares (dot notation supported)
python main.py --ticker BRK.B   # Berkshire Hathaway Class B
python main.py --ticker BRK.A   # Berkshire Hathaway Class A

# Validate any ticker
curl http://localhost:8000/validate/AAPL
# Response: {"ticker": "AAPL", "valid": true, "name": "Apple Inc."}
```

---

## Troubleshooting

### LLM Connection Issues

**Ollama not responding:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve

# Pull model if missing
ollama pull llama3.1
```

**API key errors:**
```bash
# Verify your API key is set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Rate limiting:**
- Use a smaller model (gpt-4o-mini, claude-3-5-haiku)
- Add delays between requests
- Use local Ollama for unlimited requests

### Common Errors

| Error | Solution |
|-------|----------|
| `Invalid ticker format` | Use 1-5 uppercase letters (e.g., AAPL, MSFT) |
| `Ticker not found` | Verify ticker exists on NYSE/NASDAQ |
| `API key not found` | Set the appropriate environment variable |
| `Connection refused (Ollama)` | Run `ollama serve` first |
| `Model not found` | Pull model: `ollama pull llama3.1` |

---

## Testing

```bash
# Run all tests
make test
# or
pytest tests/ -v

# Run with coverage
make test-cov
# or
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_api.py -v

# Run tests matching pattern
pytest tests/ -k "test_signal" -v
```

---

## License

MIT
