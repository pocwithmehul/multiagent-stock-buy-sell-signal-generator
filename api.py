"""FastAPI application for Stock Signal Generator API."""

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import yfinance as yf
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from observability import setup_observability, track_agent_execution
from stock_signal_agent import StockSignalAgent
from agents.orchestrator_agent import OrchestratorAgent
from infrastructure.schedule_store import PostgresScheduleStore
from infrastructure.watchlist_store import PostgresWatchlistStore


def validate_us_ticker(ticker: str) -> tuple[bool, str]:
    """
    Validate that a ticker symbol exists in the US market.

    Returns:
        tuple: (is_valid, message)
    """
    ticker = ticker.upper().strip()

    # Basic format check (1-5 uppercase letters, some have dots like BRK.A, BRK.B)
    if not re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', ticker):
        return False, f"Invalid ticker format: {ticker}. Must be 1-5 letters."

    def _check_ticker(t: str) -> tuple[bool, dict | None]:
        """Check if ticker has valid data. Returns (has_data, info_dict)."""
        try:
            tk = yf.Ticker(t)
            info = tk.info
            if not info:
                return False, None
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if price is None:
                return False, None
            return True, info
        except Exception:
            return False, None

    try:
        # Try the ticker as-is first
        has_data, info = _check_ticker(ticker)

        # If dot format fails, try dash format (e.g., BRK.B -> BRK-B)
        if not has_data and '.' in ticker:
            alt_ticker = ticker.replace('.', '-')
            has_data, info = _check_ticker(alt_ticker)

        if not has_data or info is None:
            return False, f"Ticker '{ticker}' not found in market data."

        # Check if it's a US market stock
        exchange = info.get('exchange', '')
        market = info.get('market', '')

        us_exchanges = ['NYQ', 'NMS', 'NGM', 'NCM', 'NYS', 'NAS', 'NASDAQ', 'NYSE', 'AMEX', 'PCX', 'ASE']

        if exchange and exchange not in us_exchanges and 'us_market' not in market.lower():
            # Still allow if it has USD currency
            currency = info.get('currency', '')
            if currency != 'USD':
                return False, f"Ticker '{ticker}' is not a US market stock (exchange: {exchange})."

        return True, info.get('shortName', ticker)

    except Exception as e:
        return False, f"Error validating ticker '{ticker}': {str(e)}"


# Request/Response models
class SignalRequest(BaseModel):
    """Request model for signal generation."""
    ticker: str = Field(..., description="Stock ticker symbol (any valid US market ticker)", example="AAPL")
    days: int = Field(default=30, ge=1, le=1825, description="Number of past days to analyze (1 day to 5 years)")
    model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    mode: str = Field(default="multi", pattern="^(single|multi)$", description="Agent mode: single or multi")
    verbose: bool = Field(default=False, description="Include detailed agent outputs")

    @field_validator('ticker')
    @classmethod
    def validate_ticker_format(cls, v: str) -> str:
        """Validate ticker format."""
        v = v.upper().strip()
        if not re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', v):
            raise ValueError(f"Invalid ticker format: {v}. Must be 1-5 uppercase letters.")
        return v


class SignalResponse(BaseModel):
    """Response model for signal generation."""
    ticker: str
    signal: Optional[str] = None
    confidence: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    potential_upside_pct: Optional[float] = None
    potential_downside_pct: Optional[float] = None
    sentiment_score: Optional[float] = None
    reasoning: Optional[str] = None
    mode: str
    agents_used: Optional[int] = None
    agent_details: Optional[dict] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str


class ScheduleConfigRequest(BaseModel):
    """Request model for dashboard-managed scheduler config."""
    name: str = Field(..., min_length=1, max_length=128)
    enabled: bool = True
    session_type: str = Field(..., pattern="^(pre_market|intraday|after_hours)$")
    run_time: str = Field(..., description="HH:MM in local timezone")
    timezone: str = Field(default="America/New_York")
    weekdays_only: bool = True
    email: str = Field(..., min_length=3, max_length=255)
    model: str = Field(default="gpt-4o-mini")
    days: int = Field(default=90, ge=7, le=1825)
    top_n: int = Field(default=10, ge=1, le=50)

class ScheduleRunResultRequest(BaseModel):
    """Request model for run status updates from orchestration."""
    status: str = Field(..., pattern="^(success|failed)$")
    error: Optional[str] = None


_schedule_store: Optional[PostgresScheduleStore] = None
_watchlist_store: Optional[PostgresWatchlistStore] = None


def _require_schedule_store() -> PostgresScheduleStore:
    """Create schedule store lazily and ensure schema exists."""
    global _schedule_store
    if _schedule_store is None:
        try:
            _schedule_store = PostgresScheduleStore()
            _schedule_store.ensure_schema()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Schedule store unavailable: {exc}")
    return _schedule_store


def _require_watchlist_store() -> PostgresWatchlistStore:
    """Create watchlist store lazily and ensure schema exists."""
    global _watchlist_store
    if _watchlist_store is None:
        try:
            _watchlist_store = PostgresWatchlistStore()
            _watchlist_store.ensure_schema()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Watchlist store unavailable: {exc}")
    return _watchlist_store


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_observability()
    print("Stock Signal API started")
    yield
    # Shutdown
    print("Stock Signal API shutting down")


# Create FastAPI app
app = FastAPI(
    title="Stock Signal Generator API",
    description="""
    Multi-agent AI system for generating stock buy/sell/hold signals.

    ## Features
    - **Single-agent mode**: Quick analysis using StockSignalAgent
    - **Multi-agent mode**: Comprehensive analysis using 44 specialized agents
    - **Observability**: Integrated with Langfuse for tracing and monitoring

    ## Agents
    The multi-agent system includes agents for:
    - Technical Analysis (RSI, MACD, Bollinger Bands)
    - News & Sentiment Analysis
    - SEC Filings Analysis
    - Analyst Ratings (Zacks, TipRanks, SeekingAlpha, etc.)
    - Insider & Institutional Activity
    - And 40+ more specialized data sources
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
    )


@app.post("/signal", response_model=SignalResponse, tags=["Signals"])
async def generate_signal(request: SignalRequest):
    """
    Generate a buy/sell/hold signal for a stock.

    - **ticker**: Any valid US market stock symbol (e.g., AAPL, GOOGL, MSFT, TSLA, JPM)
    - **days**: Number of historical days to analyze (1-365)
    - **model**: LLM model to use for analysis
    - **mode**: 'single' for quick analysis, 'multi' for comprehensive 44-agent analysis
    - **verbose**: Include detailed output from each agent
    """
    # Validate ticker exists in US market
    is_valid, message = validate_us_ticker(request.ticker)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    try:
        with track_agent_execution(request.ticker, request.mode):
            if request.mode == "single":
                output = await _run_single_agent(request)
            else:
                output = await _run_multi_agent(request)

        return SignalResponse(
            ticker=request.ticker.upper(),
            signal=output.get("signal"),
            confidence=output.get("confidence"),
            target_price=output.get("target_price"),
            stop_loss=output.get("stop_loss"),
            potential_upside_pct=output.get("potential_upside_pct"),
            potential_downside_pct=output.get("potential_downside_pct"),
            sentiment_score=output.get("sentiment_score"),
            reasoning=output.get("reasoning"),
            mode=request.mode,
            agents_used=output.get("agents_used"),
            agent_details=output.get("agent_details") if request.verbose else None,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signal/{ticker}", response_model=SignalResponse, tags=["Signals"])
async def get_signal_simple(
    ticker: str,
    days: int = 30,
    mode: str = "multi",
):
    """
    Simple GET endpoint for signal generation.

    Quick way to get a signal without POST body.
    Supports any valid US market ticker (e.g., AAPL, MSFT, GOOGL, TSLA, JPM, WMT).
    """
    request = SignalRequest(ticker=ticker, days=days, mode=mode)
    return await generate_signal(request)


class TickerValidationResponse(BaseModel):
    """Response for ticker validation."""
    ticker: str
    valid: bool
    name: Optional[str] = None
    message: str


@app.get("/validate/{ticker}", response_model=TickerValidationResponse, tags=["Utilities"])
async def validate_ticker(ticker: str):
    """
    Validate a stock ticker symbol.

    Checks if the ticker exists in the US market and returns company info.
    Useful for validating user input before generating signals.
    """
    ticker = ticker.upper().strip()
    is_valid, message = validate_us_ticker(ticker)

    return TickerValidationResponse(
        ticker=ticker,
        valid=is_valid,
        name=message if is_valid else None,
        message=message if not is_valid else f"Valid ticker: {message}",
    )


@app.get("/schedules", tags=["Schedules"])
async def list_schedules():
    """List all scheduler configurations stored in PostgreSQL."""
    store = _require_schedule_store()
    return {"schedules": store.list_schedules()}


@app.post("/schedules", tags=["Schedules"])
async def upsert_schedule(request: ScheduleConfigRequest):
    """Create or update schedule config from dashboard input."""
    store = _require_schedule_store()
    try:
        row = store.upsert_schedule(request.model_dump())
        return {"schedule": row}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/schedules/due", tags=["Schedules"])
async def get_due_schedules(limit: int = 25):
    """Get due schedules. n8n should call this before executing jobs."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    store = _require_schedule_store()
    return {"schedules": store.get_due_schedules(limit=limit)}


@app.post("/schedules/{schedule_id}/run-result", tags=["Schedules"])
async def mark_schedule_result(schedule_id: int, request: ScheduleRunResultRequest):
    """Mark run result and roll next_run_at forward."""
    store = _require_schedule_store()
    row = store.mark_schedule_run(schedule_id, status=request.status, error=request.error)
    if not row:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"schedule": row}


@app.delete("/schedules/{schedule_id}", tags=["Schedules"])
async def delete_schedule(schedule_id: int):
    """Delete a schedule config."""
    store = _require_schedule_store()
    deleted = store.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"deleted": True, "id": schedule_id}


class WatchlistRequest(BaseModel):
    tickers: list[str]

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip().upper() for t in value if t and t.strip()]
        if not cleaned:
            raise ValueError("tickers cannot be empty")
        return cleaned


@app.get("/watchlist", tags=["Watchlist"])
async def list_watchlist():
    store = _require_watchlist_store()
    return {"tickers": store.list_watchlist()}


@app.put("/watchlist", tags=["Watchlist"])
async def replace_watchlist(request: WatchlistRequest):
    store = _require_watchlist_store()
    return {"tickers": store.replace_watchlist(request.tickers)}


@app.post("/watchlist/{ticker}", tags=["Watchlist"])
async def add_watchlist_ticker(ticker: str):
    store = _require_watchlist_store()
    return {"tickers": store.add_ticker(ticker)}


@app.delete("/watchlist/{ticker}", tags=["Watchlist"])
async def remove_watchlist_ticker(ticker: str):
    store = _require_watchlist_store()
    return {"tickers": store.remove_ticker(ticker)}


# ─────────────────────────────────────────────────────────────────────────────
# Feature Flags API
# ─────────────────────────────────────────────────────────────────────────────


class FeatureFlagsResponse(BaseModel):
    """Response model for feature flags."""
    flags: dict[str, bool]
    provider: str
    environment: str


@app.get("/api/v1/features", response_model=FeatureFlagsResponse, tags=["Features"])
async def get_feature_flags():
    """
    Get all feature flags and their current values.

    Returns the current state of all feature flags based on the environment:
    - Local (APP_ENV=local): Uses Unleash self-hosted server
    - AWS (APP_ENV=qa/stg/prod): Uses AWS AppConfig
    """
    from infrastructure.feature_flags import get_all_flags
    from infrastructure.env_config import get_environment, is_aws_environment

    env = get_environment()
    provider = "appconfig" if is_aws_environment() else "unleash"

    return FeatureFlagsResponse(
        flags=get_all_flags(),
        provider=provider,
        environment=env.value,
    )


class FeatureFlagCheckRequest(BaseModel):
    """Request model for checking a specific feature flag."""
    flag_name: str
    context: Optional[dict] = None


class FeatureFlagCheckResponse(BaseModel):
    """Response model for feature flag check."""
    flag_name: str
    enabled: bool


@app.post("/api/v1/features/check", response_model=FeatureFlagCheckResponse, tags=["Features"])
async def check_feature_flag(request: FeatureFlagCheckRequest):
    """
    Check if a specific feature flag is enabled.

    Allows checking a feature flag with optional context for targeting.
    Context can include user_id, session_id, or other attributes.
    """
    from infrastructure.feature_flags import is_feature_enabled, FeatureFlag

    try:
        flag = FeatureFlag(request.flag_name)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown feature flag: {request.flag_name}. "
                   f"Valid flags: {[f.value for f in FeatureFlag]}"
        )

    enabled = is_feature_enabled(flag, context=request.context)
    return FeatureFlagCheckResponse(flag_name=request.flag_name, enabled=enabled)


async def _run_single_agent(request: SignalRequest) -> dict:
    """Run single-agent mode in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _execute_single_agent,
        request.ticker,
        request.days,
        request.model,
    )


async def _run_multi_agent(request: SignalRequest) -> dict:
    """Run multi-agent mode in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _execute_multi_agent,
        request.ticker,
        request.days,
        request.model,
        request.verbose,
    )


def _execute_single_agent(ticker: str, days: int, model: str) -> dict:
    """Execute single agent synchronously."""
    agent = StockSignalAgent(
        stock_ticker=ticker,
        past_days=days,
        model=model,
    )
    agent.execute()
    return agent.get_signal()


def _execute_multi_agent(ticker: str, days: int, model: str, verbose: bool) -> dict:
    """Execute multi-agent orchestrator synchronously."""
    orchestrator = OrchestratorAgent(
        ticker=ticker,
        past_days=days,
        model=model,
        verbose=verbose,
    )
    orchestrator.execute()
    return orchestrator.get_signal()


# Run with: uvicorn api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
