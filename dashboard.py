"""Streamlit dashboard for Stock Signal Generator."""

import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import tempfile
import time
from contextlib import nullcontext
from datetime import datetime, timedelta
import sys
from io import StringIO
from zoneinfo import ZoneInfo

# Note: report_utils are imported lazily in display_action_buttons() to avoid crashes

# Constants
MAX_WATCHLIST_SIZE = 20
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM"]
LLM_MODEL_OPTIONS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "claude-3-sonnet-20240229",
    "ollama/llama3",
    "ollama/llama3.1",
    "ollama/mistral",
]

# Schedule options (in seconds)
SCHEDULE_OPTIONS = {
    "Off": None,
    "Pre-Market (4:00 AM - 9:30 AM ET)": "pre_market",
    "Intra-Day (Every 5 min)": 300,
    "Intra-Day (Every 15 min)": 900,
    "Intra-Day (Every 30 min)": 1800,
    "After Hours (4:00 PM - 8:00 PM ET)": "after_hours",
    "Custom Interval": "custom",
}

DEFAULT_FEATURE_FLAGS = {
    "single_stock_analysis": True,
    "watchlist_analysis": False,
    "premarket_analysis": False,
    "aftermarket_analysis": False,
}


def get_dashboard_feature_flags() -> dict[str, bool]:
    """Load feature flags for UI gating with safe defaults."""
    try:
        from infrastructure.feature_flags import get_all_flags

        flags = get_all_flags()
        return {
            "single_stock_analysis": bool(
                flags.get("single_stock_analysis", DEFAULT_FEATURE_FLAGS["single_stock_analysis"])
            ),
            "watchlist_analysis": bool(
                flags.get("watchlist_analysis", DEFAULT_FEATURE_FLAGS["watchlist_analysis"])
            ),
            "premarket_analysis": bool(
                flags.get("premarket_analysis", DEFAULT_FEATURE_FLAGS["premarket_analysis"])
            ),
            "aftermarket_analysis": bool(
                flags.get("aftermarket_analysis", DEFAULT_FEATURE_FLAGS["aftermarket_analysis"])
            ),
        }
    except Exception:
        return DEFAULT_FEATURE_FLAGS.copy()


def display_disclaimer():
    """Display disclaimer at the top of the page."""
    st.warning("""
    **⚠️ DISCLAIMER: NOT FINANCIAL ADVICE**

    The information provided by this Stock Signal Generator is for **educational and informational purposes only**.
    It should **not** be construed as financial, investment, trading, or any other type of advice.

    - Past performance is not indicative of future results
    - Always conduct your own research before making investment decisions
    - Consult with a qualified financial advisor before investing
    - The creators of this tool are not responsible for any financial losses

    By using this tool, you acknowledge that you understand and accept these terms.
    """)


def init_session_state():
    """Initialize session state variables."""
    if "watchlist" not in st.session_state:
        try:
            from infrastructure.watchlist_store import PostgresWatchlistStore
            store = PostgresWatchlistStore()
            store.ensure_schema()
            db_watchlist = store.list_watchlist()
            if not db_watchlist:
                db_watchlist = store.replace_watchlist(DEFAULT_WATCHLIST.copy())
            st.session_state.watchlist = db_watchlist
        except Exception as e:
            import sys
            print(f"  [Dashboard] Watchlist PostgreSQL error: {e}", file=sys.stderr)
            st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
    if "schedule_enabled" not in st.session_state:
        st.session_state.schedule_enabled = False
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = None
    if "auto_refresh_interval" not in st.session_state:
        st.session_state.auto_refresh_interval = None
    if "show_sms_dialog" not in st.session_state:
        st.session_state.show_sms_dialog = False
    if "show_email_dialog" not in st.session_state:
        st.session_state.show_email_dialog = False
    if "buy_now_rankings" not in st.session_state:
        st.session_state.buy_now_rankings = []
    if "buy_now_generated_at" not in st.session_state:
        st.session_state.buy_now_generated_at = None
    if "show_buy_now_email_dialog" not in st.session_state:
        st.session_state.show_buy_now_email_dialog = False
    if "run_buy_now_rank" not in st.session_state:
        st.session_state.run_buy_now_rank = False


def add_to_watchlist(ticker: str) -> tuple[bool, str]:
    """Add a ticker to the watchlist."""
    ticker = ticker.upper().strip()
    if not ticker:
        return False, "Please enter a valid ticker symbol"
    if len(ticker) > 5:
        return False, "Ticker symbol must be 5 characters or less"
    if ticker in st.session_state.watchlist:
        return False, f"{ticker} is already in your watchlist"
    if len(st.session_state.watchlist) >= MAX_WATCHLIST_SIZE:
        return False, f"Watchlist is full (maximum {MAX_WATCHLIST_SIZE} stocks)"

    st.session_state.watchlist.append(ticker)
    try:
        from infrastructure.watchlist_store import PostgresWatchlistStore
        store = PostgresWatchlistStore()
        store.ensure_schema()
        st.session_state.watchlist = store.add_ticker(ticker)
    except Exception:
        pass
    return True, f"{ticker} added to watchlist"


def remove_from_watchlist(ticker: str) -> tuple[bool, str]:
    """Remove a ticker from the watchlist."""
    ticker = ticker.upper().strip()
    if ticker in st.session_state.watchlist:
        st.session_state.watchlist.remove(ticker)
        try:
            from infrastructure.watchlist_store import PostgresWatchlistStore
            store = PostgresWatchlistStore()
            store.ensure_schema()
            st.session_state.watchlist = store.remove_ticker(ticker)
        except Exception:
            pass
        return True, f"{ticker} removed from watchlist"
    return False, f"{ticker} is not in your watchlist"


def is_market_hours(hour_type: str) -> bool:
    """Check if current time is within specified market hours (ET timezone)."""
    try:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        et_hour = now_et.hour
        et_minute = now_et.minute
        if hour_type == "pre_market":
            # Pre-market: 4:00 AM - 9:30 AM ET
            return 4 <= et_hour < 9 or (et_hour == 9 and et_minute < 30)
        elif hour_type == "after_hours":
            # After hours: 4:00 PM - 8:00 PM ET
            return 16 <= et_hour < 20
        elif hour_type == "market_hours":
            # Regular market: 9:30 AM - 4:00 PM ET
            return (et_hour == 9 and et_minute >= 30) or (10 <= et_hour < 16)
    except Exception:
        pass
    return True  # Default to allowing refresh


def should_auto_refresh(schedule_type, custom_interval: int = None) -> bool:
    """Determine if dashboard should auto-refresh based on schedule."""
    if schedule_type is None:
        return False

    last_refresh = st.session_state.get("last_refresh")
    now = datetime.now()

    if isinstance(schedule_type, int):
        # Fixed interval in seconds
        if last_refresh is None:
            return True
        elapsed = (now - last_refresh).total_seconds()
        return elapsed >= schedule_type

    elif schedule_type == "custom" and custom_interval:
        if last_refresh is None:
            return True
        elapsed = (now - last_refresh).total_seconds()
        return elapsed >= custom_interval

    elif schedule_type in ["pre_market", "after_hours"]:
        # Check if within the specified hours
        if not is_market_hours(schedule_type):
            return False
        # Refresh every 5 minutes during these periods
        if last_refresh is None:
            return True
        elapsed = (now - last_refresh).total_seconds()
        return elapsed >= 300

    return False


def render_db_schedule_manager(
    default_model: str,
    default_days: int,
    allowed_session_types: list[str] | None = None,
):
    """Render PostgreSQL-backed schedule configuration controls."""
    st.subheader("🗓️ DB Scheduler")
    st.caption("Save schedules to PostgreSQL. n8n reads due jobs from this table.")

    try:
        from infrastructure.schedule_store import PostgresScheduleStore
        schedule_store = PostgresScheduleStore()
        schedule_store.ensure_schema()
    except Exception as exc:
        st.warning(f"Schedule DB unavailable: {exc}")
        return

    if allowed_session_types is None:
        allowed_session_types = ["pre_market", "intraday", "after_hours"]
    if not allowed_session_types:
        st.info("No schedule session types are enabled by feature flags.")
        return

    with st.form("db_schedule_form", clear_on_submit=False):
        name = st.text_input("Schedule Name", value="weekday_buy_now")
        session_type = st.selectbox("Session", options=allowed_session_types)
        run_time = st.time_input("Run Time", value=datetime.now().replace(second=0, microsecond=0).time())
        timezone_name = st.text_input("Timezone", value="America/New_York")
        weekdays_only = st.checkbox("Weekdays Only", value=True)
        email = st.text_input("Report Email", placeholder="alerts@example.com")
        model = st.text_input("Model", value=default_model)
        months = st.number_input("Analysis Period (Months)", min_value=3, max_value=120, value=max(3, int(default_days) // 30))
        days = int(months) * 30
        top_n = st.number_input("Top N", min_value=1, max_value=50, value=10)
        enabled = st.checkbox("Enabled", value=True)

        save_clicked = st.form_submit_button("Save Schedule", type="primary", width='stretch')
        if save_clicked:
            if not email or "@" not in email:
                st.error("Enter a valid report email")
            else:
                payload = {
                    "name": name.strip(),
                    "enabled": enabled,
                    "session_type": session_type,
                    "run_time": run_time.strftime("%H:%M:%S"),
                    "timezone": timezone_name.strip() or "America/New_York",
                    "weekdays_only": weekdays_only,
                    "email": email.strip(),
                    "model": model.strip() or "gpt-4o-mini",
                    "days": int(days),
                    "top_n": int(top_n),
                }
                try:
                    schedule_store.upsert_schedule(payload)
                    st.success("Schedule saved to PostgreSQL")
                except Exception as exc:
                    st.error(f"Failed to save schedule: {exc}")

    try:
        schedules = schedule_store.list_schedules()
        if schedules:
            rows = []
            for row in schedules:
                rows.append({
                    "ID": row.get("id"),
                    "Name": row.get("name"),
                    "Session": row.get("session_type"),
                    "Run Time": str(row.get("run_time")),
                    "Timezone": row.get("timezone"),
                    "Enabled": row.get("enabled"),
                    "Next Run (UTC)": row.get("next_run_at"),
                    "Email": row.get("email"),
                    "Watchlist": ",".join(row.get("watchlist") or []),
                })
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        else:
            st.info("No schedules in database yet.")
    except Exception as exc:
        st.warning(f"Could not load schedules: {exc}")

# Page config
st.set_page_config(
    page_title="Stock Signal Generator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    /* Reduce metric value font size to prevent truncation */
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* Reduce metric label font size */
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
    }

    /* Reduce metric delta font size */
    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
    }

    .signal-buy {
        background-color: #28a745;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        font-size: 24px;
        font-weight: bold;
        text-align: center;
    }
    .signal-sell {
        background-color: #dc3545;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        font-size: 24px;
        font-weight: bold;
        text-align: center;
    }
    .signal-hold {
        background-color: #ffc107;
        color: black;
        padding: 10px 20px;
        border-radius: 5px;
        font-size: 24px;
        font-weight: bold;
        text-align: center;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #dee2e6;
    }
    .agent-card {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


def get_signal_class(signal: str) -> str:
    """Get CSS class for signal."""
    signal = signal.upper() if signal else ""
    if signal == "BUY" or signal == "BULLISH":
        return "signal-buy"
    elif signal == "SELL" or signal == "BEARISH":
        return "signal-sell"
    return "signal-hold"


def normalize_signal(signal: str) -> str:
    """Normalize BUY/SELL/HOLD and BULLISH/BEARISH variants."""
    sig = (signal or "").upper().strip()
    if sig in ("BUY", "BULLISH"):
        return "BUY"
    if sig in ("SELL", "BEARISH"):
        return "SELL"
    return "HOLD"


def reconcile_signal_decision(result: dict, ensemble_result: dict | None = None) -> dict:
    """
    Reconcile orchestrator/single-agent signal with ensemble signal.

    Design:
    - Orchestrator signal remains primary unless ensemble is materially more confident.
    - On near-tie conflicts, downgrade to HOLD to avoid overconfident disagreement.
    """
    primary_signal = normalize_signal(result.get("signal"))
    primary_conf = float(result.get("confidence") or 0.0)

    if not ensemble_result:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": primary_conf,
            "decision_source": "primary",
            "signal_alignment": "primary_only",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": None,
            "ensemble_confidence": None,
        }

    ensemble_signal = normalize_signal(ensemble_result.get("ensemble_signal"))
    ensemble_conf = float(ensemble_result.get("ensemble_confidence") or 0.0)

    if primary_signal == ensemble_signal:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": max(primary_conf, ensemble_conf),
            "decision_source": "aligned",
            "signal_alignment": "aligned",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }

    # Material confidence edge threshold for override.
    edge = 0.20
    if ensemble_conf >= primary_conf + edge:
        return {
            "reconciled_signal": ensemble_signal,
            "reconciled_confidence": ensemble_conf,
            "decision_source": "ensemble_override",
            "signal_alignment": "conflict",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }
    if primary_conf >= ensemble_conf + edge:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": primary_conf,
            "decision_source": "primary_override",
            "signal_alignment": "conflict",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }

    return {
        "reconciled_signal": "HOLD",
        "reconciled_confidence": max(0.55, (primary_conf + ensemble_conf) / 2),
        "decision_source": "tie_break_hold",
        "signal_alignment": "conflict",
        "primary_signal": primary_signal,
        "primary_confidence": primary_conf,
        "ensemble_signal": ensemble_signal,
        "ensemble_confidence": ensemble_conf,
    }


def build_detailed_reasoning(result: dict, ensemble_result: dict | None = None) -> str:
    """Build a detailed, auditable narrative from agent + ML + reconciliation outputs."""
    lines = []

    final_signal = result.get("reconciled_signal") or result.get("signal", "HOLD")
    final_conf = result.get("reconciled_confidence")
    if final_conf is None:
        final_conf = result.get("confidence", 0.0)
    decision_source = result.get("decision_source", "primary")

    lines.append("Final Decision")
    lines.append(f"- Signal: {final_signal}")
    lines.append(f"- Confidence: {float(final_conf or 0.0):.2f}")
    lines.append(f"- Decision source: {decision_source}")

    llm_signal = result.get("llm_signal")
    majority_signal = result.get("majority_signal")
    if llm_signal or majority_signal:
        lines.append("")
        lines.append("Primary Synthesis")
        if llm_signal:
            lines.append(f"- LLM signal: {llm_signal} ({float(result.get('llm_confidence') or 0.0):.2f})")
        if majority_signal:
            lines.append(
                f"- Majority signal: {majority_signal} "
                f"(vote ratio: {float(result.get('majority_vote_ratio') or 0.0):.2f}, "
                f"votes: {result.get('majority_vote_counts', {})})"
            )

    lines.append("")
    lines.append("ML / Ensemble")
    if ensemble_result:
        lines.append(
            f"- Ensemble signal: {ensemble_result.get('ensemble_signal', 'HOLD')} "
            f"({float(ensemble_result.get('ensemble_confidence') or 0.0):.2f})"
        )
        lines.append(f"- Ensemble score: {float(ensemble_result.get('ensemble_score') or 0.0):+.3f}")
        lines.append(f"- Vote distribution: {ensemble_result.get('signal_distribution', {})}")
    else:
        lines.append("- Ensemble analysis unavailable for this run.")

    brief_reason = result.get("reasoning")
    if brief_reason:
        lines.append("")
        lines.append("Synthesis Summary")
        lines.append(f"- {brief_reason}")

    agent_details = result.get("agent_details") or {}
    if agent_details:
        lines.append("")
        lines.append("Agent-by-Agent View")
        for agent_name in sorted(agent_details.keys()):
            details = agent_details.get(agent_name) or {}
            raw_sig = details.get("signal")
            sig = raw_sig if raw_sig else "Data Only"
            conf = float(details.get("confidence") or 0.0)
            summary = details.get("summary") or "No summary provided"
            if raw_sig:
                lines.append(f"- {agent_name}: {sig} ({conf:.2f}) | {summary}")
            else:
                lines.append(f"- {agent_name}: {sig} | {summary}")

    lines.append("")
    lines.append(
        "Final signal rationale: The system combines primary multi-agent synthesis with a consensus/ML cross-check "
        "and then applies reconciliation rules to select BUY/SELL/HOLD."
    )
    return "\n".join(lines)


def run_analysis(ticker: str, days: int, mode: str, model: str, verbose: bool, api_base: str = None, status_container=None):
    """Run stock analysis with progress updates."""
    # Use provided container or default to st
    container = status_container if status_container else st

    class _NoOpProgress:
        def progress(self, *_args, **_kwargs):
            return None

    class _NoOpText:
        def write(self, *_args, **_kwargs):
            return None

    class _NoOpStatus(_NoOpText):
        def progress(self, *_args, **_kwargs):
            return _NoOpProgress()

        def empty(self):
            return _NoOpText()

        def update(self, *_args, **_kwargs):
            return None

    def _status_context(label: str):
        if not hasattr(container, "status"):
            return nullcontext(_NoOpStatus())
        try:
            return container.status(label, expanded=True)
        except Exception:
            return nullcontext(_NoOpStatus())

    if mode == "Multi-Agent":
        from agents.orchestrator_agent import OrchestratorAgent
        from infrastructure.config import Config

        # Initialize Kafka if enabled via config
        kafka_producer = None
        if Config.KAFKA_ENABLED:
            try:
                from infrastructure.kafka_producer import KafkaProducerWrapper
                kafka_producer = KafkaProducerWrapper()
            except Exception:
                pass

        # Initialize Qdrant if enabled via config
        qdrant_store = None
        embedder = None
        if Config.QDRANT_ENABLED:
            try:
                from infrastructure.qdrant_store import QdrantStore
                from infrastructure.embeddings import Embedder
                qdrant_store = QdrantStore()
                embedder = Embedder()
                if not embedder.is_available():
                    qdrant_store = None
                    embedder = None
            except Exception:
                pass

        with _status_context(f"🚀 Analyzing {ticker}...") as status:
            status = status or _NoOpStatus()
            status.write("🔄 **Starting multi-agent analysis...**")
            status.write(f"🧠 **LLM model:** `{model}`")
            status.write("📊 **Mode:** Multi-agent")

            progress_bar = status.progress(0, text="Initializing agents...")
            current_agent_text = status.empty()

            # Progress callback for real-time updates
            def progress_callback(agent_name: str, current: int, total: int):
                progress = current / total
                progress_bar.progress(progress, text=f"Agent {current}/{total}")
                current_agent_text.write(f"🔄 Running **{agent_name}** agent...")

            # Save uploaded earnings call audio to a temp file if provided
            _audio_tmp = None
            _earnings_audio_path = None
            uploaded_audio = st.session_state.get("earnings_audio_upload")
            if uploaded_audio is not None:
                suffix = os.path.splitext(uploaded_audio.name)[-1] or ".mp3"
                _audio_tmp = tempfile.NamedTemporaryFile(
                    suffix=suffix, delete=False
                )
                _audio_tmp.write(uploaded_audio.getvalue())
                _audio_tmp.flush()
                _earnings_audio_path = _audio_tmp.name

            orchestrator = OrchestratorAgent(
                ticker=ticker,
                past_days=days,
                model=model,
                api_base=api_base,
                verbose=verbose,
                progress_callback=progress_callback,
                kafka_enabled=kafka_producer is not None,
                kafka_producer=kafka_producer,
                qdrant_enabled=qdrant_store is not None,
                qdrant_store=qdrant_store,
                embedder=embedder,
                earnings_audio_file=_earnings_audio_path,
            )

            orchestrator.execute()

            agents_ran = len(orchestrator.agent_outputs)
            progress_bar.progress(1.0, text=f"✅ {agents_ran} agents completed!")
            current_agent_text.write(f"✅ **{agents_ran} agents completed!**")

            status.update(label=f"✅ Analysis of {ticker} complete!", state="complete", expanded=False)

            if kafka_producer:
                kafka_producer.close()

            # Clean up temp audio file
            if _audio_tmp is not None:
                try:
                    _audio_tmp.close()
                    os.unlink(_audio_tmp.name)
                except Exception:
                    pass

            return orchestrator.get_signal()
    else:
        from stock_signal_agent import StockSignalAgent

        with _status_context(f"🚀 Analyzing {ticker}...") as status:
            status = status or _NoOpStatus()
            status.write("🔄 **Starting single-agent analysis...**")
            status.write(f"🧠 **LLM model:** `{model}`")
            status.write("📊 **Mode:** Single-agent")

            progress_bar = status.progress(0, text="Initializing...")

            agent = StockSignalAgent(
                stock_ticker=ticker,
                past_days=days,
                model=model,
                api_base=api_base,
            )

            progress_bar.progress(0.25, text="📊 Fetching price data...")
            progress_bar.progress(0.50, text="📰 Fetching news...")
            progress_bar.progress(0.75, text="🤖 Running LLM analysis...")

            agent.execute()

            progress_bar.progress(1.0, text="✅ Analysis complete!")
            status.write("✅ **Analysis complete!**")
            status.update(label=f"✅ Analysis of {ticker} complete!", state="complete", expanded=False)

            return agent.get_signal()


def get_stock_info(ticker: str):
    """Get basic stock information."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1mo")
        return info, hist
    except Exception as e:
        return None, None


def _safe_float(value):
    """Convert value to float when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_market_session_data(info: dict) -> dict:
    """Extract pre-market, intraday, and after-hours session metrics from quote info."""
    info = info or {}
    prev_close = _safe_float(info.get("regularMarketPreviousClose")) or _safe_float(info.get("previousClose"))

    pre_price = _safe_float(info.get("preMarketPrice"))
    pre_change_pct = _safe_float(info.get("preMarketChangePercent"))
    if pre_change_pct is None and pre_price is not None and prev_close:
        pre_change_pct = ((pre_price - prev_close) / prev_close) * 100

    intraday_price = _safe_float(info.get("regularMarketPrice")) or _safe_float(info.get("currentPrice"))
    intraday_change_pct = _safe_float(info.get("regularMarketChangePercent"))
    if intraday_change_pct is None and intraday_price is not None and prev_close:
        intraday_change_pct = ((intraday_price - prev_close) / prev_close) * 100

    after_price = _safe_float(info.get("postMarketPrice"))
    after_change_pct = _safe_float(info.get("postMarketChangePercent"))
    if after_change_pct is None and after_price is not None and intraday_price:
        after_change_pct = ((after_price - intraday_price) / intraday_price) * 100

    if is_market_hours("pre_market"):
        active_session = "pre_market"
    elif is_market_hours("market_hours"):
        active_session = "intraday"
    elif is_market_hours("after_hours"):
        active_session = "after_hours"
    else:
        active_session = "closed"

    return {
        "pre_market_price": pre_price,
        "pre_market_change_pct": pre_change_pct,
        "intraday_price": intraday_price,
        "intraday_change_pct": intraday_change_pct,
        "after_hours_price": after_price,
        "after_hours_change_pct": after_change_pct,
        "prev_close": prev_close,
        "active_session": active_session,
    }


def calculate_buy_now_score(result: dict, session_data: dict) -> float:
    """Calculate buy-now score combining signal strength and session momentum."""
    signal = normalize_signal(result.get("reconciled_signal") or result.get("signal"))
    confidence = float(result.get("reconciled_confidence") or result.get("confidence") or 0.0)
    upside = float(result.get("potential_upside_pct") or 0.0)

    signal_component = {"BUY": 35.0, "HOLD": 5.0, "SELL": -30.0}.get(signal, 0.0)
    confidence_component = min(max(confidence, 0.0), 1.0) * 50.0

    momentum_values = [
        (session_data.get("pre_market_change_pct"), 0.20),
        (session_data.get("intraday_change_pct"), 0.60),
        (session_data.get("after_hours_change_pct"), 0.20),
    ]
    weighted_sum = 0.0
    weight_total = 0.0
    for value, weight in momentum_values:
        if value is not None:
            weighted_sum += float(value) * weight
            weight_total += weight
    avg_momentum = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    momentum_component = max(min(avg_momentum * 2.0, 15.0), -15.0)

    upside_component = max(min(upside * 0.5, 15.0), 0.0)
    return round(signal_component + confidence_component + momentum_component + upside_component, 2)


def rank_watchlist_buy_now(
    watchlist: list[str],
    days: int,
    mode: str,
    model: str,
    api_base: str = None,
) -> list[dict]:
    """Analyze watchlist stocks and rank best buy-now candidates."""
    ranked = []
    status = st.status("🏁 Ranking watchlist for best buy-now opportunities...", expanded=True)
    progress = status.progress(0)

    for idx, watch_ticker in enumerate(watchlist):
        progress.progress((idx + 1) / max(len(watchlist), 1), text=f"Analyzing {watch_ticker} ({idx + 1}/{len(watchlist)})")
        status.write(f"Fetching signal + session data for `{watch_ticker}`")
        try:
            result = run_analysis(
                ticker=watch_ticker,
                days=days,
                mode=mode,
                model=model,
                verbose=False,
                api_base=api_base,
                status_container=object(),
            )
            if not result:
                continue

            info, _ = get_stock_info(watch_ticker)
            session_data = extract_market_session_data(info or {})
            signal = normalize_signal(result.get("reconciled_signal") or result.get("signal"))
            confidence = float(result.get("reconciled_confidence") or result.get("confidence") or 0.0)
            buy_now_score = calculate_buy_now_score(result, session_data)

            ranked.append({
                "ticker": watch_ticker,
                "company_name": (info or {}).get("shortName", watch_ticker),
                "signal": signal,
                "confidence": confidence,
                "buy_now_score": buy_now_score,
                "target_price": result.get("target_price"),
                "potential_upside_pct": result.get("potential_upside_pct"),
                "session_data": session_data,
            })
        except Exception as exc:
            status.write(f"Skipping `{watch_ticker}` due to error: {exc}")

    status.update(label="✅ Watchlist ranking complete", state="complete", expanded=False)
    ranked.sort(key=lambda x: x.get("buy_now_score", 0.0), reverse=True)
    return ranked


def compute_technical_indicators(hist: pd.DataFrame) -> dict:
    """Compute technical indicators from price history."""
    if hist is None or hist.empty or len(hist) < 14:
        return {}

    closes = hist["Close"]
    current_price = float(closes.iloc[-1])

    indicators = {
        "current_price": round(current_price, 2),
    }

    # RSI (14-period)
    if len(closes) >= 15:
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        indicators["rsi"] = round(float(rsi_val), 2) if not np.isnan(rsi_val) else None
    else:
        indicators["rsi"] = None

    # SMAs
    for period in [20, 50, 200]:
        if len(closes) >= period:
            sma = closes.rolling(window=period).mean().iloc[-1]
            indicators[f"sma_{period}"] = round(float(sma), 2) if not np.isnan(sma) else None
        else:
            indicators[f"sma_{period}"] = None

    # EMAs
    for span in [12, 26]:
        if len(closes) >= span:
            ema = closes.ewm(span=span, adjust=False).mean().iloc[-1]
            indicators[f"ema_{span}"] = round(float(ema), 2) if not np.isnan(ema) else None
        else:
            indicators[f"ema_{span}"] = None

    # MACD
    if len(closes) >= 35:
        ema_12 = closes.ewm(span=12, adjust=False).mean()
        ema_26 = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        indicators["macd"] = round(float(macd_line.iloc[-1]), 4)
        indicators["macd_signal"] = round(float(signal_line.iloc[-1]), 4)
        indicators["macd_histogram"] = round(float(histogram.iloc[-1]), 4)
    else:
        indicators["macd"] = None
        indicators["macd_signal"] = None
        indicators["macd_histogram"] = None

    # Bollinger Bands
    if len(closes) >= 20:
        sma_20 = closes.rolling(window=20).mean()
        std_20 = closes.rolling(window=20).std()
        indicators["bollinger_upper"] = round(float((sma_20 + 2 * std_20).iloc[-1]), 2)
        indicators["bollinger_middle"] = round(float(sma_20.iloc[-1]), 2)
        indicators["bollinger_lower"] = round(float((sma_20 - 2 * std_20).iloc[-1]), 2)
    else:
        indicators["bollinger_upper"] = None
        indicators["bollinger_middle"] = None
        indicators["bollinger_lower"] = None

    # Price vs SMA signals
    if indicators.get("sma_20"):
        indicators["above_sma_20"] = current_price > indicators["sma_20"]
    if indicators.get("sma_50"):
        indicators["above_sma_50"] = current_price > indicators["sma_50"]
    if indicators.get("sma_200"):
        indicators["above_sma_200"] = current_price > indicators["sma_200"]

    # RSI Signal
    if indicators.get("rsi"):
        if indicators["rsi"] < 30:
            indicators["rsi_signal"] = "OVERSOLD"
        elif indicators["rsi"] > 70:
            indicators["rsi_signal"] = "OVERBOUGHT"
        else:
            indicators["rsi_signal"] = "NEUTRAL"

    # MACD Signal
    if indicators.get("macd_histogram") is not None:
        if indicators["macd_histogram"] > 0:
            indicators["macd_signal_trend"] = "BULLISH"
        elif indicators["macd_histogram"] < 0:
            indicators["macd_signal_trend"] = "BEARISH"
        else:
            indicators["macd_signal_trend"] = "NEUTRAL"

    return indicators


def get_extended_history(ticker: str, days: int = 365) -> pd.DataFrame:
    """Get extended price history for technical analysis."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        # Fetch extra days for SMA200 calculation
        fetch_days = max(days, 250) + 50
        end = datetime.now()
        start = end - timedelta(days=fetch_days)
        hist = stock.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        return hist
    except Exception:
        return pd.DataFrame()


def display_stock_header(info: dict, ticker: str):
    """Display stock header information."""
    if info:
        # Company name and current price header
        company_name = info.get("shortName", info.get("longName", ticker))
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')

        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"{company_name} ({ticker})")
            # Company website
            website = info.get('website')
            if website:
                st.markdown(f"🌐 [{website}]({website})")
        with col2:
            if current_price:
                change = info.get('regularMarketChangePercent', 0)
                st.metric(
                    label="Current Price",
                    value=f"${current_price:.2f}",
                    delta=f"{change:.2f}%" if change else None,
                )

        # Industry and Sector
        col1, col2, col3 = st.columns(3)
        with col1:
            industry = info.get('industry', 'N/A')
            st.markdown(f"**Industry:** {industry}")
        with col2:
            sector = info.get('sector', 'N/A')
            st.markdown(f"**Sector:** {sector}")
        with col3:
            exchange = info.get('exchange', 'N/A')
            st.markdown(f"**Exchange:** {exchange}")

        st.divider()

        # Key Metrics - Row 1
        st.markdown("**📊 Key Metrics**")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            pe_ratio = info.get('trailingPE') or info.get('forwardPE')
            st.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")

        with col2:
            peg_ratio = info.get('pegRatio')
            st.metric("PEG Ratio", f"{peg_ratio:.2f}" if peg_ratio else "N/A")

        with col3:
            eps = info.get('trailingEps')
            st.metric("EPS (TTM)", f"${eps:.2f}" if eps else "N/A")

        with col4:
            book_value = info.get('bookValue')
            st.metric("Book Value", f"${book_value:.2f}" if book_value else "N/A")

        with col5:
            beta = info.get('beta')
            st.metric("Beta (5Y)", f"{beta:.2f}" if beta else "N/A")

        with col6:
            market_cap = info.get('marketCap')
            st.metric("Market Cap", format_large_number(market_cap))

        # Key Metrics - Row 2
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            st.metric("Prev Close", f"${prev_close:.2f}" if prev_close else "N/A")

        with col2:
            bid = info.get('bid')
            bid_size = info.get('bidSize', '')
            bid_text = f"${bid:.2f}" if bid else "N/A"
            if bid and bid_size:
                bid_text += f" x {bid_size}"
            st.metric("Bid", bid_text)

        with col3:
            ask = info.get('ask')
            ask_size = info.get('askSize', '')
            ask_text = f"${ask:.2f}" if ask else "N/A"
            if ask and ask_size:
                ask_text += f" x {ask_size}"
            st.metric("Ask", ask_text)

        with col4:
            volume = info.get('volume') or info.get('regularMarketVolume')
            st.metric("Volume", format_volume(volume))

        with col5:
            avg_volume = info.get('averageVolume') or info.get('averageDailyVolume10Day')
            st.metric("Avg Vol", format_volume(avg_volume))

        with col6:
            day_low = info.get('dayLow') or info.get('regularMarketDayLow')
            day_high = info.get('dayHigh') or info.get('regularMarketDayHigh')
            if day_low and day_high:
                st.metric("Day's Range", f"${day_low:.2f} - ${day_high:.2f}")
            else:
                st.metric("Day's Range", "N/A")

        # Key Metrics - Row 3
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            fifty_two_low = info.get('fiftyTwoWeekLow')
            st.metric("52W Low", f"${fifty_two_low:.2f}" if fifty_two_low else "N/A")

        with col2:
            fifty_two_high = info.get('fiftyTwoWeekHigh')
            st.metric("52W High", f"${fifty_two_high:.2f}" if fifty_two_high else "N/A")

        with col3:
            # Earnings date
            earnings_dates = info.get('earningsTimestamp') or info.get('earningsDate')
            if earnings_dates:
                if isinstance(earnings_dates, (list, tuple)) and len(earnings_dates) > 0:
                    earnings_date = datetime.fromtimestamp(earnings_dates[0]).strftime('%Y-%m-%d')
                elif isinstance(earnings_dates, (int, float)):
                    earnings_date = datetime.fromtimestamp(earnings_dates).strftime('%Y-%m-%d')
                else:
                    earnings_date = str(earnings_dates)
                st.metric("Earnings Date", earnings_date)
            else:
                st.metric("Earnings Date", "N/A")

        with col4:
            dividend_yield = info.get('dividendYield')
            if dividend_yield:
                st.metric("Div Yield", f"{dividend_yield*100:.2f}%")
            else:
                st.metric("Div Yield", "N/A")

        with col5:
            target_price = info.get('targetMeanPrice')
            st.metric("Target Price", f"${target_price:.2f}" if target_price else "N/A")

        with col6:
            recommendation = info.get('recommendationKey', 'N/A')
            st.metric("Recommendation", recommendation.upper() if recommendation else "N/A")


def format_large_number(num):
    """Format large numbers for display (with $ prefix)."""
    if num is None or num == 0:
        return "N/A"
    if num >= 1e12:
        return f"${num/1e12:.2f}T"
    if num >= 1e9:
        return f"${num/1e9:.2f}B"
    if num >= 1e6:
        return f"${num/1e6:.2f}M"
    return f"${num:,.0f}"


def format_volume(num):
    """Format volume numbers for display (no $ prefix)."""
    if num is None or num == 0:
        return "N/A"
    if num >= 1e9:
        return f"{num/1e9:.2f}B"
    if num >= 1e6:
        return f"{num/1e6:.2f}M"
    if num >= 1e3:
        return f"{num/1e3:.1f}K"
    return f"{num:,.0f}"


def display_signal_result(result: dict):
    """Display the signal result."""
    signal = result.get("reconciled_signal") or result.get("signal", "HOLD")
    confidence = result.get("reconciled_confidence")
    if confidence is None:
        confidence = result.get("confidence", 0)

    # Main signal display
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        signal_class = get_signal_class(signal)
        st.markdown(f'<div class="{signal_class}">{signal}</div>', unsafe_allow_html=True)

    with col2:
        st.metric("Confidence", f"{confidence*100:.1f}%" if confidence else "N/A")

    with col3:
        agents_used = result.get("agents_used", 1)
        # Handle both list and int formats
        if isinstance(agents_used, list):
            st.metric("Agents Used", len(agents_used))
        else:
            st.metric("Agents Used", agents_used)

    primary_signal = result.get("primary_signal")
    ensemble_signal = result.get("ensemble_signal")
    alignment = result.get("signal_alignment")
    if primary_signal and ensemble_signal:
        st.caption(
            f"Primary: {primary_signal} ({(result.get('primary_confidence') or 0)*100:.1f}%) | "
            f"Ensemble: {ensemble_signal} ({(result.get('ensemble_confidence') or 0)*100:.1f}%)"
        )
    if alignment == "conflict":
        st.warning("Primary and ML ensemble signals disagree. Reconciled decision is shown above.")

    st.divider()

    # Price targets and metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        target = result.get("target_price")
        st.metric("Target Price", f"${target:.2f}" if target else "N/A")

    with col2:
        stop_loss = result.get("stop_loss")
        st.metric("Stop Loss", f"${stop_loss:.2f}" if stop_loss else "N/A")

    with col3:
        upside = result.get("potential_upside_pct")
        st.metric("Upside Potential", f"{upside:.1f}%" if upside else "N/A")

    with col4:
        downside = result.get("potential_downside_pct")
        st.metric("Downside Risk", f"{downside:.1f}%" if downside else "N/A")

    # Sentiment
    sentiment = result.get("sentiment_score")
    if sentiment is not None:
        st.progress(min(max((sentiment + 1) / 2, 0), 1), text=f"Sentiment Score: {sentiment:.2f}")

    # Reasoning
    reasoning = result.get("reasoning")
    if reasoning:
        st.subheader("Analysis Reasoning")
        st.write(reasoning)


def display_action_buttons(ticker: str, result: dict, company_name: str = None, indicators: dict = None, ml_results: dict = None):
    """Display action buttons for download PDF, send SMS, and send email."""
    # Lazy import to avoid startup issues
    try:
        from infrastructure.report_utils import (
            generate_pdf_report,
            generate_report_text,
            generate_email_body,
            send_sms,
            send_email,
        )
        report_utils_available = True
    except ImportError as e:
        report_utils_available = False
        import_error = str(e)

    st.subheader("Report Actions")

    col1, col2, col3 = st.columns(3)

    # Download PDF button
    with col1:
        if not report_utils_available:
            st.button("Download PDF", disabled=True, width='stretch', help=f"Error: {import_error}")
            st.caption("report_utils not available")
        else:
            try:
                pdf_bytes = generate_pdf_report(
                    ticker=ticker,
                    result=result,
                    company_name=company_name,
                    indicators=indicators,
                    ml_results=ml_results,
                )
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=f"{ticker}_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    width='stretch',
                )
            except ImportError as e:
                st.button("Download PDF", disabled=True, width='stretch', help="Install reportlab: pip install reportlab")
                st.caption("reportlab not installed")
            except Exception as e:
                st.button("Download PDF", disabled=True, width='stretch')
                st.caption(f"Error: {str(e)[:50]}")

    # Send SMS button
    with col2:
        if st.button("Send Text", type="secondary", width='stretch'):
            st.session_state["show_sms_dialog"] = True

    # Send Email button
    with col3:
        if st.button("Send Email", type="secondary", width='stretch'):
            st.session_state["show_email_dialog"] = True

    # SMS Dialog
    if st.session_state.get("show_sms_dialog", False):
        with st.expander("Send SMS Report", expanded=True):
            if not report_utils_available:
                st.error(f"Report utilities not available: {import_error}")
                if st.button("Close", key="close_sms_error"):
                    st.session_state["show_sms_dialog"] = False
                    st.rerun()
            else:
                st.markdown("**Send analysis summary via SMS**")

                phone_number = st.text_input(
                    "Phone Number",
                    placeholder="+1234567890",
                    help="Enter phone number with country code (e.g., +1 for US)",
                    key="sms_phone_input"
                )

                # Show preview
                sms_text = generate_report_text(ticker, result, company_name)
                st.text_area("Message Preview", value=sms_text, height=150, disabled=True)
                st.caption(f"Character count: {len(sms_text)}")

                col_send, col_cancel = st.columns(2)

                with col_send:
                    if st.button("Send SMS", type="primary", key="send_sms_btn"):
                        if not phone_number:
                            st.error("Please enter a phone number")
                        elif not phone_number.startswith("+"):
                            st.error("Phone number must include country code (e.g., +1)")
                        else:
                            with st.spinner("Sending SMS..."):
                                success, message = send_sms(phone_number, sms_text)
                                if success:
                                    st.success(message)
                                    st.session_state["show_sms_dialog"] = False
                                    st.rerun()
                                else:
                                    st.error(message)

                with col_cancel:
                    if st.button("Cancel", key="cancel_sms_btn"):
                        st.session_state["show_sms_dialog"] = False
                        st.rerun()

                # Configuration help
                if st.checkbox("Show SMS Configuration Help", key="show_sms_config"):
                    st.info("""
                    **Required Environment Variables:**
                    - `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
                    - `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
                    - `TWILIO_FROM_NUMBER`: Your Twilio phone number

                    Get credentials at [twilio.com/console](https://www.twilio.com/console)
                    """)

    # Email Dialog
    if st.session_state.get("show_email_dialog", False):
        with st.expander("Send Email Report", expanded=True):
            if not report_utils_available:
                st.error(f"Report utilities not available: {import_error}")
                if st.button("Close", key="close_email_error"):
                    st.session_state["show_email_dialog"] = False
                    st.rerun()
            else:
                st.markdown("**Send analysis report via Email**")

                email_address = st.text_input(
                    "Email Address",
                    placeholder="recipient@example.com",
                    key="email_input"
                )

                include_pdf = st.checkbox("Attach PDF Report", value=True, key="email_pdf_checkbox")

                # Show preview
                email_body = generate_email_body(ticker, result, company_name)
                st.text_area("Email Preview", value=email_body, height=200, disabled=True)

                col_send, col_cancel = st.columns(2)

                with col_send:
                    if st.button("Send Email", type="primary", key="send_email_btn"):
                        if not email_address:
                            st.error("Please enter an email address")
                        elif "@" not in email_address:
                            st.error("Please enter a valid email address")
                        else:
                            with st.spinner("Sending email..."):
                                pdf_attachment = None
                                if include_pdf:
                                    try:
                                        pdf_attachment = generate_pdf_report(
                                            ticker=ticker,
                                            result=result,
                                            company_name=company_name,
                                            indicators=indicators,
                                            ml_results=ml_results,
                                        )
                                    except Exception:
                                        pass

                                signal = result.get("signal", "N/A")
                                subject = f"Stock Analysis Report: {ticker} - {signal}"

                                success, message = send_email(
                                    to_email=email_address,
                                    subject=subject,
                                    body=email_body,
                                    pdf_attachment=pdf_attachment,
                                    pdf_filename=f"{ticker}_analysis_report.pdf",
                                )

                                if success:
                                    st.success(message)
                                    st.session_state["show_email_dialog"] = False
                                    st.rerun()
                                else:
                                    st.error(message)

                with col_cancel:
                    if st.button("Cancel", key="cancel_email_btn"):
                        st.session_state["show_email_dialog"] = False
                        st.rerun()

                # Configuration help
                if st.checkbox("Show Email Configuration Help", key="show_email_config"):
                    st.info("""
                    **Required Environment Variables:**
                    - `SMTP_HOST`: SMTP server (default: smtp.gmail.com)
                    - `SMTP_PORT`: SMTP port (default: 587)
                    - `SMTP_USER`: Your email username
                    - `SMTP_PASSWORD`: Your email password or app-specific password
                    - `SMTP_FROM_EMAIL`: Sender email (optional, defaults to SMTP_USER)

                    **For Gmail:**
                    1. Enable 2-Factor Authentication
                    2. Generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
                    3. Use the App Password as SMTP_PASSWORD
                    """)

    st.divider()


def display_buy_now_rankings(ranked: list[dict]):
    """Display ranked buy-now candidates with PDF and email actions."""
    if not ranked:
        st.info("No watchlist ranking available yet. Click 'Rank Best Stocks Now' in the sidebar.")
        return

    st.subheader("🏆 Best Stocks to Buy Now")
    if st.session_state.get("buy_now_generated_at"):
        st.caption(f"Generated at: {st.session_state['buy_now_generated_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    rows = []
    for index, item in enumerate(ranked, 1):
        session = item.get("session_data", {})
        rows.append({
            "Rank": index,
            "Ticker": item.get("ticker"),
            "Company": item.get("company_name"),
            "Signal": item.get("signal"),
            "Confidence %": round(float(item.get("confidence") or 0.0) * 100, 1),
            "Buy Score": round(float(item.get("buy_now_score") or 0.0), 2),
            "Pre-Mkt %": round(float(session.get("pre_market_change_pct") or 0.0), 2) if session.get("pre_market_change_pct") is not None else None,
            "Intraday %": round(float(session.get("intraday_change_pct") or 0.0), 2) if session.get("intraday_change_pct") is not None else None,
            "After-Hrs %": round(float(session.get("after_hours_change_pct") or 0.0), 2) if session.get("after_hours_change_pct") is not None else None,
            "Upside %": round(float(item.get("potential_upside_pct") or 0.0), 2) if item.get("potential_upside_pct") is not None else None,
        })

    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    try:
        from infrastructure.report_utils import generate_buy_now_pdf_report, generate_buy_now_email_body, send_email
        report_utils_available = True
    except ImportError as err:
        report_utils_available = False
        import_error = str(err)

    col1, col2 = st.columns(2)
    with col1:
        if report_utils_available:
            pdf_bytes = generate_buy_now_pdf_report(ranked)
            st.download_button(
                "Download Buy-Now PDF",
                data=pdf_bytes,
                file_name=f"buy_now_rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf",
                type="primary",
                width='stretch',
            )
        else:
            st.button("Download Buy-Now PDF", disabled=True, width='stretch', help=import_error)
    with col2:
        if st.button("Email Buy-Now Report", width='stretch'):
            st.session_state["show_buy_now_email_dialog"] = True

    if st.session_state.get("show_buy_now_email_dialog", False):
        with st.expander("Send Buy-Now Report by Email", expanded=True):
            if not report_utils_available:
                st.error(f"Report utilities not available: {import_error}")
            else:
                email_address = st.text_input("Email Address", placeholder="recipient@example.com", key="buy_now_email_input")
                include_pdf = st.checkbox("Attach PDF", value=True, key="buy_now_email_pdf_checkbox")
                email_body = generate_buy_now_email_body(ranked)
                st.text_area("Email Preview", value=email_body, height=220, disabled=True)

                send_col, cancel_col = st.columns(2)
                with send_col:
                    if st.button("Send", type="primary", key="send_buy_now_email_btn"):
                        if not email_address or "@" not in email_address:
                            st.error("Please enter a valid email address")
                        else:
                            pdf_attachment = generate_buy_now_pdf_report(ranked) if include_pdf else None
                            success, message = send_email(
                                to_email=email_address,
                                subject="Best Stocks to Buy Now - Watchlist Ranking",
                                body=email_body,
                                pdf_attachment=pdf_attachment,
                                pdf_filename="buy_now_rankings.pdf",
                            )
                            if success:
                                st.success(message)
                                st.session_state["show_buy_now_email_dialog"] = False
                                st.rerun()
                            else:
                                st.error(message)
                with cancel_col:
                    if st.button("Cancel", key="cancel_buy_now_email_btn"):
                        st.session_state["show_buy_now_email_dialog"] = False
                        st.rerun()

    st.divider()


def display_agent_details(agent_details: dict):
    """Display detailed agent outputs."""
    if not agent_details:
        return

    st.subheader("Agent Details")

    # Group agents by category
    categories = {
        "Technical Analysis": ["TechnicalAnalysisAgent"],
        "News & Sentiment": ["NewsAgent", "SentimentAgent", "RedditAgent", "StockTwitsAgent", "XTwitterAgent"],
        "Analyst Ratings": ["ZacksAgent", "TipRanksAgent", "SeekingAlphaAgent", "MotleyFoolAgent",
                           "MorningstarAgent", "StockStoryAgent"],
        "Insider Activity": ["InsiderInstitutionalAgent", "OpenInsiderAgent", "WhaleWisdomAgent"],
        "Fundamentals": ["YahooFinanceAgent", "GuruFocusAgent", "FactSetAgent", "SimplyWallStAgent"],
        "SEC Filings": ["SECFilingAgent"],
        "Other": [],
    }

    # Categorize agents
    categorized = {cat: [] for cat in categories}
    for agent_name, details in agent_details.items():
        found = False
        for cat, agents in categories.items():
            if cat != "Other" and any(a.lower() in agent_name.lower() for a in agents):
                categorized[cat].append((agent_name, details))
                found = True
                break
        if not found:
            categorized["Other"].append((agent_name, details))

    # Display by category
    for category, agents in categorized.items():
        if not agents:
            continue

        with st.expander(f"{category} ({len(agents)} agents)", expanded=False):
            for agent_name, details in agents:
                signal = details.get("signal") or "Data Only"
                confidence = details.get("confidence", 0)
                signal_class = get_signal_class(signal) if signal not in ["Data Only", None] else "signal-hold"

                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"**{agent_name}**")
                with col2:
                    display_signal = signal if signal not in [None, "None"] else "Data Only"
                    st.markdown(f"<span style='padding: 2px 8px; border-radius: 3px;' class='{signal_class}'>{display_signal}</span>", unsafe_allow_html=True)
                with col3:
                    st.write(f"Conf: {confidence*100:.0f}%" if confidence else "—")

                # Show additional details if available
                if details.get("reasoning"):
                    st.caption(details["reasoning"][:200] + "..." if len(details.get("reasoning", "")) > 200 else details.get("reasoning", ""))

                st.divider()


def display_price_chart(hist, ticker: str = ""):
    """Display stock price chart with SMAs using Plotly with labels at line ends."""
    if hist is not None and not hist.empty:
        st.subheader(f"Price Chart - {ticker}" if ticker else "Price Chart")

        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            annotations = []
            last_date = hist.index[-1]

            # Add price line
            last_price = hist["Close"].iloc[-1]
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist["Close"],
                mode='lines',
                name='Price',
                line=dict(color='#1f77b4', width=2),
                showlegend=False
            ))
            annotations.append(dict(
                x=last_date, y=last_price,
                xanchor='left', yanchor='middle',
                text=f' Price ${last_price:.2f}',
                font=dict(color='#1f77b4', size=11),
                showarrow=False
            ))

            # Add SMAs if we have enough data
            if len(hist) >= 20:
                sma_20 = hist["Close"].rolling(window=20).mean()
                last_sma20 = sma_20.iloc[-1]
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=sma_20,
                    mode='lines',
                    name='SMA 20',
                    line=dict(color='#ff7f0e', width=1.5),
                    showlegend=False
                ))
                annotations.append(dict(
                    x=last_date, y=last_sma20,
                    xanchor='left', yanchor='middle',
                    text=f' SMA 20 ${last_sma20:.2f}',
                    font=dict(color='#ff7f0e', size=11),
                    showarrow=False
                ))

            if len(hist) >= 50:
                sma_50 = hist["Close"].rolling(window=50).mean()
                last_sma50 = sma_50.iloc[-1]
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=sma_50,
                    mode='lines',
                    name='SMA 50',
                    line=dict(color='#2ca02c', width=1.5),
                    showlegend=False
                ))
                annotations.append(dict(
                    x=last_date, y=last_sma50,
                    xanchor='left', yanchor='middle',
                    text=f' SMA 50 ${last_sma50:.2f}',
                    font=dict(color='#2ca02c', size=11),
                    showarrow=False
                ))

            if len(hist) >= 200:
                sma_200 = hist["Close"].rolling(window=200).mean()
                last_sma200 = sma_200.iloc[-1]
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=sma_200,
                    mode='lines',
                    name='SMA 200',
                    line=dict(color='#d62728', width=1.5),
                    showlegend=False
                ))
                annotations.append(dict(
                    x=last_date, y=last_sma200,
                    xanchor='left', yanchor='middle',
                    text=f' SMA 200 ${last_sma200:.2f}',
                    font=dict(color='#d62728', size=11),
                    showarrow=False
                ))

            # Add Bollinger Bands if we have enough data
            if len(hist) >= 20:
                sma_20 = hist["Close"].rolling(window=20).mean()
                std_20 = hist["Close"].rolling(window=20).std()
                bb_upper = sma_20 + 2 * std_20
                bb_lower = sma_20 - 2 * std_20
                last_bb_upper = bb_upper.iloc[-1]
                last_bb_lower = bb_lower.iloc[-1]

                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=bb_upper,
                    mode='lines',
                    name='BB Upper',
                    line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dash'),
                    showlegend=False
                ))
                annotations.append(dict(
                    x=last_date, y=last_bb_upper,
                    xanchor='left', yanchor='middle',
                    text=f' BB Upper ${last_bb_upper:.2f}',
                    font=dict(color='gray', size=10),
                    showarrow=False
                ))

                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=bb_lower,
                    mode='lines',
                    name='BB Lower',
                    line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(128, 128, 128, 0.1)',
                    showlegend=False
                ))
                annotations.append(dict(
                    x=last_date, y=last_bb_lower,
                    xanchor='left', yanchor='middle',
                    text=f' BB Lower ${last_bb_lower:.2f}',
                    font=dict(color='gray', size=10),
                    showarrow=False
                ))

            fig.update_layout(
                title=f"{ticker} Price with Technical Indicators" if ticker else "Price with Technical Indicators",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                annotations=annotations,
                hovermode='x unified',
                height=500,
                margin=dict(r=120)  # Extra right margin for labels
            )

            st.plotly_chart(fig, width='stretch')

        except ImportError:
            # Fallback to basic streamlit chart if plotly not available
            chart_data = pd.DataFrame({"Price": hist["Close"]})
            if len(hist) >= 20:
                chart_data["SMA 20"] = hist["Close"].rolling(window=20).mean()
            if len(hist) >= 50:
                chart_data["SMA 50"] = hist["Close"].rolling(window=50).mean()
            if len(hist) >= 200:
                chart_data["SMA 200"] = hist["Close"].rolling(window=200).mean()
            st.line_chart(chart_data)


def display_technical_indicators(indicators: dict):
    """Display technical analysis indicators."""
    if not indicators:
        st.warning("Not enough data to calculate technical indicators")
        return

    st.subheader("Technical Analysis")

    # Current Price
    current_price = indicators.get("current_price")
    if current_price:
        st.metric("Current Price", f"${current_price:.2f}")

    st.divider()

    # RSI Section
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**RSI (14)**")
        rsi = indicators.get("rsi")
        if rsi is not None:
            # RSI gauge-like display
            rsi_color = "green" if rsi < 30 else "red" if rsi > 70 else "gray"
            rsi_signal = indicators.get("rsi_signal", "NEUTRAL")
            st.metric("RSI Value", f"{rsi:.1f}", delta=rsi_signal)
            st.progress(min(rsi / 100, 1.0), text=f"RSI: {rsi:.1f}")
            if rsi < 30:
                st.success("Oversold - Potential buying opportunity")
            elif rsi > 70:
                st.error("Overbought - Potential selling opportunity")
            else:
                st.info("Neutral range (30-70)")
        else:
            st.write("N/A - Insufficient data")

    with col2:
        st.markdown("**MACD**")
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        macd_hist = indicators.get("macd_histogram")
        if macd is not None:
            st.metric("MACD Line", f"{macd:.4f}")
            st.metric("Signal Line", f"{macd_signal:.4f}" if macd_signal else "N/A")
            if macd_hist is not None:
                trend = indicators.get("macd_signal_trend", "NEUTRAL")
                delta_color = "normal" if macd_hist >= 0 else "inverse"
                st.metric("Histogram", f"{macd_hist:.4f}", delta=trend)
        else:
            st.write("N/A - Insufficient data")

    st.divider()

    # Moving Averages Section
    st.markdown("**Moving Averages**")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        sma20 = indicators.get("sma_20")
        above_sma20 = indicators.get("above_sma_20")
        st.metric(
            "SMA 20",
            f"${sma20:.2f}" if sma20 else "N/A",
            delta="Above" if above_sma20 else "Below" if above_sma20 is not None else None,
            delta_color="normal" if above_sma20 else "inverse" if above_sma20 is not None else "off"
        )

    with col2:
        sma50 = indicators.get("sma_50")
        above_sma50 = indicators.get("above_sma_50")
        st.metric(
            "SMA 50",
            f"${sma50:.2f}" if sma50 else "N/A",
            delta="Above" if above_sma50 else "Below" if above_sma50 is not None else None,
            delta_color="normal" if above_sma50 else "inverse" if above_sma50 is not None else "off"
        )

    with col3:
        sma200 = indicators.get("sma_200")
        above_sma200 = indicators.get("above_sma_200")
        st.metric(
            "SMA 200",
            f"${sma200:.2f}" if sma200 else "N/A",
            delta="Above" if above_sma200 else "Below" if above_sma200 is not None else None,
            delta_color="normal" if above_sma200 else "inverse" if above_sma200 is not None else "off"
        )

    with col4:
        ema12 = indicators.get("ema_12")
        st.metric("EMA 12", f"${ema12:.2f}" if ema12 else "N/A")

    with col5:
        ema26 = indicators.get("ema_26")
        st.metric("EMA 26", f"${ema26:.2f}" if ema26 else "N/A")

    st.divider()

    # Bollinger Bands Section
    st.markdown("**Bollinger Bands (20, 2)**")
    col1, col2, col3 = st.columns(3)

    with col1:
        bb_upper = indicators.get("bollinger_upper")
        st.metric("Upper Band", f"${bb_upper:.2f}" if bb_upper else "N/A")

    with col2:
        bb_middle = indicators.get("bollinger_middle")
        st.metric("Middle Band", f"${bb_middle:.2f}" if bb_middle else "N/A")

    with col3:
        bb_lower = indicators.get("bollinger_lower")
        st.metric("Lower Band", f"${bb_lower:.2f}" if bb_lower else "N/A")

    # Bollinger position interpretation
    if current_price and bb_upper and bb_lower:
        if current_price >= bb_upper:
            st.warning("Price at/above upper band - Potentially overbought")
        elif current_price <= bb_lower:
            st.success("Price at/below lower band - Potentially oversold")
        else:
            bb_range = bb_upper - bb_lower
            position = (current_price - bb_lower) / bb_range if bb_range > 0 else 0.5
            st.progress(position, text=f"Position within bands: {position*100:.1f}%")


def run_ml_analysis(hist: pd.DataFrame, agent_results: dict = None) -> dict:
    """Run ML analysis on historical data."""
    results = {}

    try:
        from ml import PricePredictor, SignalClassifier, EnsembleScorer

        # 1. Price Prediction (LSTM)
        with st.spinner("Running LSTM price prediction..."):
            predictor = PricePredictor(sequence_length=60)
            predictor.fit(hist, epochs=5, verbose=0)
            results["price_prediction"] = predictor.predict(hist)

        # 2. Signal Classification (XGBoost)
        with st.spinner("Running XGBoost signal classification..."):
            classifier = SignalClassifier()
            classifier.fit(hist)
            results["signal_classification"] = classifier.predict(hist)

        # 3. Ensemble Scoring
        if agent_results:
            with st.spinner("Running ensemble scoring..."):
                scorer = EnsembleScorer()
                results["ensemble"] = scorer.score(agent_results)
        else:
            results["ensemble"] = None

    except ImportError as e:
        st.warning(f"ML modules not fully available: {e}")
        results["error"] = str(e)
    except Exception as e:
        st.error(f"ML analysis error: {e}")
        results["error"] = str(e)

    return results


def display_ml_analysis(ml_results: dict):
    """Display ML analysis results on the dashboard."""
    st.subheader("🤖 Machine Learning Analysis")

    # Create tabs for different ML components
    tab1, tab2, tab3 = st.tabs(["📈 Price Prediction", "🎯 Signal Classifier", "⚖️ Ensemble Score"])

    # Tab 1: Price Prediction (LSTM)
    with tab1:
        price_pred = ml_results.get("price_prediction", {})
        if price_pred and "error" not in price_pred:
            st.markdown("**LSTM Neural Network - 5-Day Price Forecast**")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                current = price_pred.get("current_price", 0)
                st.metric("Current Price", f"${current:.2f}")

            with col2:
                predicted = price_pred.get("predicted_5d_price", 0)
                change_pct = price_pred.get("predicted_change_pct", 0)
                st.metric("5-Day Forecast", f"${predicted:.2f}",
                         delta=f"{change_pct:+.2f}%")

            with col3:
                trend = price_pred.get("trend", "NEUTRAL")
                trend_color = "green" if trend == "BULLISH" else "red" if trend == "BEARISH" else "gray"
                st.metric("Trend", trend)

            with col4:
                confidence = price_pred.get("confidence", 0)
                st.metric("Confidence", f"{confidence*100:.1f}%")

            # Daily predictions chart
            predictions = price_pred.get("predictions", [])
            if predictions:
                st.markdown("**Daily Predictions:**")
                pred_df = pd.DataFrame(predictions)
                pred_df.set_index('date', inplace=True)

                # Display as line chart
                try:
                    import plotly.graph_objects as go

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=pred_df.index,
                        y=pred_df['price'],
                        mode='lines+markers',
                        name='Predicted Price',
                        line=dict(color='#1f77b4', width=2),
                        marker=dict(size=8)
                    ))

                    # Add current price line
                    fig.add_hline(y=current, line_dash="dash",
                                 line_color="gray", annotation_text="Current")

                    # Add support/resistance
                    support = price_pred.get("support", 0)
                    resistance = price_pred.get("resistance", 0)
                    if support:
                        fig.add_hline(y=support, line_dash="dot",
                                     line_color="green", annotation_text="Support")
                    if resistance:
                        fig.add_hline(y=resistance, line_dash="dot",
                                     line_color="red", annotation_text="Resistance")

                    fig.update_layout(
                        title="5-Day Price Forecast",
                        xaxis_title="Date",
                        yaxis_title="Price ($)",
                        height=300,
                        showlegend=False
                    )

                    st.plotly_chart(fig, width='stretch')
                except ImportError:
                    st.dataframe(pred_df)

            # Support/Resistance levels
            col1, col2 = st.columns(2)
            with col1:
                support = price_pred.get("support", 0)
                st.metric("Support Level", f"${support:.2f}" if support else "N/A")
            with col2:
                resistance = price_pred.get("resistance", 0)
                st.metric("Resistance Level", f"${resistance:.2f}" if resistance else "N/A")

            st.caption(f"Model: {price_pred.get('model_type', 'Unknown')}")
        else:
            st.info("Price prediction not available. Ensure sufficient historical data.")

    # Tab 2: Signal Classifier (XGBoost)
    with tab2:
        signal_class = ml_results.get("signal_classification", {})
        if signal_class and "error" not in signal_class:
            st.markdown("**XGBoost Classification - Signal Prediction**")

            signal = signal_class.get("signal", "HOLD")
            confidence = signal_class.get("confidence", 0.5)
            probabilities = signal_class.get("probabilities", {})

            # Main signal display
            col1, col2 = st.columns([1, 2])

            with col1:
                signal_color = "green" if signal == "BUY" else "red" if signal == "SELL" else "orange"
                st.markdown(f"""
                <div style="background-color: {signal_color}; color: white; padding: 20px;
                            border-radius: 10px; text-align: center;">
                    <h2 style="margin: 0;">{signal}</h2>
                    <p style="margin: 5px 0 0 0;">Confidence: {confidence*100:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                # Probability bars
                st.markdown("**Signal Probabilities:**")
                for sig, prob in sorted(probabilities.items(), key=lambda x: x[1], reverse=True):
                    color = "green" if sig == "BUY" else "red" if sig == "SELL" else "orange"
                    st.progress(prob, text=f"{sig}: {prob*100:.1f}%")

            # Feature values used
            feature_values = signal_class.get("feature_values", {})
            if feature_values:
                st.markdown("**Key Features Used:**")
                cols = st.columns(len(feature_values))
                for i, (name, value) in enumerate(feature_values.items()):
                    with cols[i]:
                        st.metric(name.replace('_', ' ').title(), f"{value:.4f}")

            # Reasons (for rule-based)
            reasons = signal_class.get("reasons", [])
            if reasons:
                st.markdown("**Analysis Factors:**")
                for reason in reasons:
                    st.write(f"• {reason}")

            st.caption(f"Model: {signal_class.get('model_type', 'Unknown')}")
        else:
            st.info("Signal classification not available.")

    # Tab 3: Ensemble Score
    with tab3:
        ensemble = ml_results.get("ensemble")
        if ensemble:
            st.markdown("**Ensemble Scoring - Agent Consensus**")

            signal = ensemble.get("ensemble_signal", "HOLD")
            confidence = ensemble.get("ensemble_confidence", 0.5)
            score = ensemble.get("ensemble_score", 0)

            # Main display
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                signal_color = "#28a745" if signal == "BUY" else "#dc3545" if signal == "SELL" else "#ffc107"
                st.markdown(f"""
                <div style="background-color: {signal_color}; color: white; padding: 15px;
                            border-radius: 8px; text-align: center;">
                    <h3 style="margin: 0;">{signal}</h3>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.metric("Confidence", f"{confidence*100:.1f}%")

            with col3:
                st.metric("Score", f"{score:+.3f}")

            with col4:
                agreement = ensemble.get("agreement_ratio", 0)
                st.metric("Agreement", f"{agreement*100:.1f}%")

            # Signal distribution
            dist = ensemble.get("signal_distribution", {})
            if dist:
                st.markdown("**Agent Signal Distribution:**")
                total = sum(dist.values())
                cols = st.columns(3)
                for i, (sig, count) in enumerate(dist.items()):
                    with cols[i]:
                        pct = count / total * 100 if total > 0 else 0
                        color = "green" if sig == "BUY" else "red" if sig == "SELL" else "orange"
                        st.metric(sig, f"{count} ({pct:.0f}%)")

            # Top contributors
            col1, col2 = st.columns(2)

            with col1:
                bullish = ensemble.get("top_bullish_agents", [])
                if bullish:
                    st.markdown("**🟢 Top Bullish Agents:**")
                    for agent in bullish[:5]:
                        st.write(f"• {agent}")

            with col2:
                bearish = ensemble.get("top_bearish_agents", [])
                if bearish:
                    st.markdown("**🔴 Top Bearish Agents:**")
                    for agent in bearish[:5]:
                        st.write(f"• {agent}")

            # Agent contributions (collapsible via checkbox)
            if st.checkbox("View All Agent Contributions", value=False):
                contributions = ensemble.get("agent_contributions", {})
                if contributions:
                    contrib_data = []
                    for agent, data in contributions.items():
                        raw_sig = data.get("signal")
                        contrib_data.append({
                            "Agent": agent,
                            "Signal": raw_sig if raw_sig else "Data Only",
                            "Confidence": f"{data.get('confidence', 0)*100:.1f}%" if raw_sig else "—",
                            "Weight": f"{data.get('weight', 0)*100:.2f}%",
                            "Contribution": f"{data.get('contribution', 0):+.4f}"
                        })
                    st.dataframe(pd.DataFrame(contrib_data), width='stretch')

            st.caption(f"Weights: {ensemble.get('weights_used', 'default')}")
        else:
            st.info("Run stock analysis first to see ensemble scoring from all agents.")


def parse_options_query(question: str, model: str = None, api_base: str = None,
                        watchlist: list = None) -> dict:
    """
    Use LLM to extract structured options screening parameters from a natural language question.

    Returns dict with keys:
        ticker (str|None), max_price (float), option_type (str),
        min_volume (int), min_vol_oi_ratio (float), max_expirations (int),
        use_watchlist (bool), parsed (bool)
    """
    defaults = {
        "ticker": None,
        "max_price": 0.25,
        "option_type": "both",
        "min_volume": 100,
        "min_vol_oi_ratio": 0.5,
        "max_expirations": 3,
        "use_watchlist": False,
        "parsed": False,
    }
    try:
        import litellm, json as _json
        from infrastructure.config import Config as _Config
        _model = model or _Config.DEFAULT_MODEL

        watchlist_hint = f"User's watchlist tickers: {watchlist}" if watchlist else ""
        prompt = (
            f"Extract options screening parameters from this question:\n"
            f'"{question}"\n\n'
            f"{watchlist_hint}\n\n"
            "Return a JSON object with these fields:\n"
            '  "ticker": stock ticker symbol if mentioned (e.g. "AAPL"), or null if not mentioned\n'
            '  "max_price": maximum option premium in dollars (float, default 0.25)\n'
            '  "option_type": "calls", "puts", or "both" (default "both")\n'
            '  "min_volume": minimum volume as integer (default 100)\n'
            '  "min_vol_oi_ratio": minimum volume/OI ratio as float (default 0.5)\n'
            '  "max_expirations": number of nearest expirations to scan as integer 1-6 (default 3)\n'
            '  "use_watchlist": true if user mentions watchlist or all tickers, else false\n\n'
            "Examples:\n"
            '  "calls under $0.10 on TSLA" → ticker=TSLA, max_price=0.10, option_type=calls\n'
            '  "puts with vol/OI above 2x" → option_type=puts, min_vol_oi_ratio=2.0\n'
            '  "scan my watchlist for options under $0.50" → use_watchlist=true, max_price=0.50\n'
            '  "options expiring this week under $0.25" → max_expirations=1, max_price=0.25\n\n'
            "Return ONLY valid JSON, no markdown."
        )
        kwargs = {"model": _model, "messages": [{"role": "user", "content": prompt}]}
        if api_base:
            kwargs["api_base"] = api_base
        resp = litellm.completion(**kwargs)
        raw = resp.choices[0].message.content.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        parsed = _json.loads(raw)

        # Merge with defaults and validate
        result = {**defaults, **parsed, "parsed": True}
        result["max_price"] = float(result.get("max_price") or 0.25)
        result["min_volume"] = int(result.get("min_volume") or 100)
        result["min_vol_oi_ratio"] = float(result.get("min_vol_oi_ratio") or 0.5)
        result["max_expirations"] = max(1, min(6, int(result.get("max_expirations") or 3)))
        if result.get("option_type") not in ("calls", "puts", "both"):
            result["option_type"] = "both"
        if result.get("ticker"):
            result["ticker"] = str(result["ticker"]).upper().strip()
        return result
    except Exception:
        return defaults


def fetch_unusual_cheap_options(
    tickers: list[str],
    max_price: float = 0.25,
    option_type: str = "both",       # "calls" | "puts" | "both"
    min_volume: int = 100,
    min_volume_oi_ratio: float = 0.5,  # volume / openInterest — high ratio = unusual
    max_expirations: int = 3,
) -> pd.DataFrame:
    """
    Fetch options chains for each ticker, filter by price and unusual activity.

    Unusual activity criteria (ANY of):
      - volume >= min_volume AND volume/openInterest >= min_volume_oi_ratio
      - volume is in top 10% for that ticker/expiration

    Returns a DataFrame with columns:
      ticker, type, expiration, strike, lastPrice, bid, ask,
      volume, openInterest, vol_oi_ratio, impliedVolatility,
      inTheMoney, contractSymbol
    """
    import yfinance as yf

    rows = []
    for ticker in tickers:
        try:
            tk = yf.Ticker(ticker)
            expirations = tk.options or []
            for exp in expirations[:max_expirations]:
                try:
                    chain = tk.option_chain(exp)
                    for side, df in [("call", chain.calls), ("put", chain.puts)]:
                        if option_type == "calls" and side == "put":
                            continue
                        if option_type == "puts" and side == "call":
                            continue
                        if df is None or df.empty:
                            continue

                        # Price filter
                        df = df.copy()
                        price_col = "lastPrice" if "lastPrice" in df.columns else None
                        if price_col is None:
                            continue
                        df = df[df[price_col] <= max_price]
                        df = df[df[price_col] > 0]
                        if df.empty:
                            continue

                        # Volume filter
                        if "volume" in df.columns:
                            df = df[df["volume"].fillna(0) >= min_volume]
                        if df.empty:
                            continue

                        # Unusual activity — vol/OI ratio
                        if "openInterest" in df.columns:
                            df["vol_oi_ratio"] = df["volume"].fillna(0) / df["openInterest"].replace(0, 1)
                            unusual = df[df["vol_oi_ratio"] >= min_volume_oi_ratio]
                            # Also include top-10% volume even if OI is low
                            if len(df) >= 5:
                                top_vol = df[df["volume"] >= df["volume"].quantile(0.90)]
                                unusual = pd.concat([unusual, top_vol]).drop_duplicates()
                        else:
                            df["vol_oi_ratio"] = 0.0
                            unusual = df

                        if unusual.empty:
                            continue

                        for _, row in unusual.iterrows():
                            rows.append({
                                "ticker":          ticker,
                                "type":            side.upper(),
                                "expiration":      exp,
                                "strike":          row.get("strike", 0),
                                "lastPrice":       round(float(row.get("lastPrice", 0)), 4),
                                "bid":             round(float(row.get("bid", 0)), 4),
                                "ask":             round(float(row.get("ask", 0)), 4),
                                "volume":          int(row.get("volume", 0) or 0),
                                "openInterest":    int(row.get("openInterest", 0) or 0),
                                "vol_oi_ratio":    round(float(row.get("vol_oi_ratio", 0)), 2),
                                "impliedVolatility": round(float(row.get("impliedVolatility", 0)), 4),
                                "inTheMoney":      bool(row.get("inTheMoney", False)),
                                "contractSymbol":  row.get("contractSymbol", ""),
                            })
                except Exception:
                    continue
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df_result = pd.DataFrame(rows)
    # Sort by vol_oi_ratio desc, then volume desc
    df_result = df_result.sort_values(["vol_oi_ratio", "volume"], ascending=[False, False]).reset_index(drop=True)
    return df_result


def main():
    """Main dashboard function."""
    # Initialize session state
    init_session_state()
    feature_flags = get_dashboard_feature_flags()

    single_stock_enabled = feature_flags["single_stock_analysis"]
    watchlist_enabled = feature_flags["watchlist_analysis"]
    premarket_enabled = feature_flags["premarket_analysis"]
    aftermarket_enabled = feature_flags["aftermarket_analysis"]

    if not watchlist_enabled:
        st.session_state["run_buy_now_rank"] = False

    available_schedule_options = dict(SCHEDULE_OPTIONS)
    if not premarket_enabled:
        available_schedule_options.pop("Pre-Market (4:00 AM - 9:30 AM ET)", None)
    if not aftermarket_enabled:
        available_schedule_options.pop("After Hours (4:00 PM - 8:00 PM ET)", None)

    allowed_session_types = ["intraday"]
    if premarket_enabled:
        allowed_session_types.insert(0, "pre_market")
    if aftermarket_enabled:
        allowed_session_types.append("after_hours")

    # Sidebar
    with st.sidebar:
        st.title("📈 Stock Signal Generator")
        st.divider()

        # Input fields
        # Initialise from query params so the ticker survives a page reload.
        # First run: read ?ticker= from URL (empty string if absent).
        # Subsequent re-runs: session_state key keeps the value intact.
        if "ticker_input" not in st.session_state:
            st.session_state.ticker_input = st.query_params.get("ticker", "")

        ticker = st.text_input(
            "Stock Ticker",
            key="ticker_input",
            max_chars=5,
            placeholder="e.g. AAPL",
            help="Enter a US stock ticker symbol (e.g., AAPL, MSFT, GOOGL)",
        ).upper().strip()

        # Keep the URL query param in sync so reloading restores the ticker.
        if ticker:
            st.query_params["ticker"] = ticker
        elif "ticker" in st.query_params:
            del st.query_params["ticker"]

        months = st.slider(
            "Analysis Period (Months)",
            min_value=3,
            max_value=120,
            value=12,
            format="%d months",
            help="Historical data window: 3 months to 10 years",
        )
        days = months * 30

        mode = st.radio(
            "Analysis Mode",
            ["Multi-Agent", "Single-Agent"],
            help="Multi-Agent uses domain-specialized agents for comprehensive analysis",
        )

        analysis_model = st.selectbox(
            "LLM Model (Single Stock)",
            LLM_MODEL_OPTIONS,
            help="Model used when you click Analyze Stock",
        )
        watchlist_model = analysis_model

        # Show API base URL input for local models
        api_base = None
        if analysis_model.startswith("ollama/") or watchlist_model.startswith("ollama/"):
            api_base = st.text_input(
                "Ollama URL",
                value="http://localhost:11434",
                help="Ollama server URL",
            )

        verbose = st.checkbox(
            "Show Agent Details",
            value=True,
            help="Display detailed output from each agent",
        )

        st.divider()

        analyze_btn = st.button(
            "🔍 Analyze Stock",
            type="primary",
            width='stretch',
            disabled=(not ticker) or (not single_stock_enabled),
            help="Enter a ticker symbol to enable" if not ticker else "Click to analyze"
        )
        if not single_stock_enabled:
            st.info("`single_stock_analysis` is disabled by feature flag.")

        st.divider()

        # ── Earnings Call Audio Upload ──
        with st.expander("Earnings Call Audio (optional)", expanded=False):
            st.caption(
                "Upload an MP3, M4A, WAV, or OGG recording of an earnings call. "
                "The file will be transcribed with Whisper and analysed for a signal."
            )
            uploaded_audio = st.file_uploader(
                "Upload audio file",
                type=["mp3", "m4a", "wav", "ogg", "flac", "mp4"],
                key="earnings_audio_upload",
                label_visibility="collapsed",
            )
            if uploaded_audio:
                st.success(f"Loaded: {uploaded_audio.name} ({uploaded_audio.size // 1024} KB)")

        st.divider()

        # ── Watchlist Section ──
        if watchlist_enabled:
            st.subheader(f"📋 Watchlist ({len(st.session_state.watchlist)}/{MAX_WATCHLIST_SIZE})")
            watchlist_model = st.selectbox(
                "LLM Model (Watchlist Ranking)",
                LLM_MODEL_OPTIONS,
                index=LLM_MODEL_OPTIONS.index(analysis_model) if analysis_model in LLM_MODEL_OPTIONS else 0,
                help="Model used when you click Rank Best Stocks Now",
            )
            if watchlist_model.startswith("ollama/") and not api_base:
                api_base = st.text_input(
                    "Ollama URL (Watchlist)",
                    value="http://localhost:11434",
                    help="Ollama server URL for watchlist ranking",
                )
            st.caption(
                f"Single stock uses `{analysis_model}`. Watchlist ranking uses `{watchlist_model}`."
            )

            # Add to watchlist
            col1, col2 = st.columns([3, 1])
            with col1:
                new_ticker = st.text_input(
                    "Add ticker",
                    max_chars=5,
                    placeholder="TICKER",
                    label_visibility="collapsed",
                    key="new_watchlist_ticker"
                )
            with col2:
                if st.button("➕", key="add_watchlist", help="Add to watchlist"):
                    if new_ticker:
                        success, msg = add_to_watchlist(new_ticker)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            # Display watchlist as quick pick buttons
            if st.session_state.watchlist:
                # Calculate number of rows needed (4 columns)
                watchlist = st.session_state.watchlist
                num_cols = 4
                for row_start in range(0, len(watchlist), num_cols):
                    cols = st.columns(num_cols)
                    for i, col in enumerate(cols):
                        idx = row_start + i
                        if idx < len(watchlist):
                            t = watchlist[idx]
                            if col.button(t, key=f"quick_{t}_{idx}", width='stretch'):
                                st.session_state["quick_ticker"] = t
                                st.rerun()

                # Remove from watchlist
                st.caption("Remove from watchlist:")
                remove_ticker = st.selectbox(
                    "Select to remove",
                    options=[""] + st.session_state.watchlist,
                    label_visibility="collapsed",
                    key="remove_watchlist_select"
                )
                if remove_ticker and st.button("🗑️ Remove", key="remove_watchlist"):
                    success, msg = remove_from_watchlist(remove_ticker)
                    if success:
                        st.success(msg)
                        st.rerun()
            else:
                st.caption("No stocks in watchlist")

            if st.button("🏆 Rank Best Stocks Now", type="primary", width='stretch'):
                st.session_state["run_buy_now_rank"] = True
        else:
            st.subheader("📋 Watchlist")
            st.info("`watchlist_analysis` is disabled by feature flag.")

        st.divider()

        # ── Schedule/Auto-Refresh Section ──
        st.subheader("⏰ Auto-Refresh Schedule")

        schedule_option = st.selectbox(
            "Refresh Schedule",
            options=list(available_schedule_options.keys()),
            help="Automatically refresh dashboard on schedule"
        )

        schedule_value = available_schedule_options[schedule_option]
        custom_interval = None

        if schedule_value == "custom":
            custom_interval = st.number_input(
                "Custom interval (minutes)",
                min_value=1,
                max_value=1440,
                value=60,
                help="Enter refresh interval in minutes"
            ) * 60  # Convert to seconds

        # Display schedule status
        if schedule_value is not None:
            st.session_state.schedule_enabled = True
            st.session_state.auto_refresh_interval = custom_interval if schedule_value == "custom" else schedule_value

            if st.session_state.last_refresh:
                st.caption(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

            if schedule_value == "pre_market":
                st.info("🌅 Refreshes every 5 min during pre-market (4:00 AM - 9:30 AM ET)")
            elif schedule_value == "after_hours":
                st.info("🌙 Refreshes every 5 min during after-hours (4:00 PM - 8:00 PM ET)")
            elif isinstance(schedule_value, int):
                st.info(f"🔄 Refreshes every {schedule_value // 60} minutes")
            elif schedule_value == "custom" and custom_interval:
                st.info(f"🔄 Refreshes every {custom_interval // 60} minutes")
        else:
            st.session_state.schedule_enabled = False
            st.session_state.auto_refresh_interval = None

        st.divider()
        render_db_schedule_manager(watchlist_model, days, allowed_session_types=allowed_session_types)

        st.divider()

        # Info
        st.caption("Powered by Multi-Agent AI System")
        st.caption("Domain-specialized agents for comprehensive analysis")

    # Handle quick picks
    if watchlist_enabled and "quick_ticker" in st.session_state:
        ticker = st.session_state["quick_ticker"]
        del st.session_state["quick_ticker"]
        analyze_btn = True

    # Main content area
    # Status container at the very top for analysis progress
    status_container = st.container()

    # Display disclaimer
    with st.expander("⚠️ Important Disclaimer", expanded=False):
        display_disclaimer()

    st.title(f"Stock Analysis: {ticker}")
    top_actions_container = st.container()

    if watchlist_enabled and st.session_state.get("run_buy_now_rank", False):
        watchlist = st.session_state.get("watchlist", [])
        if not watchlist:
            st.warning("Watchlist is empty. Add tickers first.")
        else:
            ranked = rank_watchlist_buy_now(
                watchlist=watchlist,
                days=days,
                mode=mode,
                model=watchlist_model,
                api_base=api_base,
            )
            st.session_state["buy_now_rankings"] = ranked
            st.session_state["buy_now_generated_at"] = datetime.now()
        st.session_state["run_buy_now_rank"] = False

    if watchlist_enabled:
        display_buy_now_rankings(st.session_state.get("buy_now_rankings", []))

    # Get and display stock info
    info, hist = get_stock_info(ticker)
    if info:
        display_stock_header(info, ticker)

    # Get extended history for technical analysis (need more data for SMA200)
    extended_hist = get_extended_history(ticker, days=max(days, 250))

    # Display price chart with SMAs
    if extended_hist is not None and not extended_hist.empty:
        display_price_chart(extended_hist, ticker)

        # Calculate and display technical indicators
        with st.expander("Technical Indicators", expanded=True):
            indicators = compute_technical_indicators(extended_hist)
            display_technical_indicators(indicators)

        # ML Analysis section
        with st.expander("🤖 Machine Learning Analysis", expanded=False):
            # Get agent results if available for ensemble scoring
            agent_results = None
            if "last_result" in st.session_state and st.session_state.get("last_ticker") == ticker:
                agent_results = st.session_state["last_result"].get("agent_details")

            # Run ML analysis (guarded by ml_analysis feature flag)
            from infrastructure.feature_flags import is_feature_enabled, FeatureFlag
            if is_feature_enabled(FeatureFlag.ML_ANALYSIS):
                ml_results = run_ml_analysis(extended_hist, agent_results)
                if ml_results and "error" not in ml_results:
                    display_ml_analysis(ml_results)
                else:
                    st.info("Click 'Analyze Stock' to run full ML analysis with agent ensemble scoring.")
            else:
                st.info("ML analysis is currently disabled.")

    # Knowledge Graph Explorer
    from infrastructure.feature_flags import is_feature_enabled, FeatureFlag
    if is_feature_enabled(FeatureFlag.KNOWLEDGE_GRAPH):
        with st.expander("🧠 Knowledge Graph Explorer", expanded=False):
            st.caption("Ask a natural language question about stocks, sectors, and macro factors.")
            kg_question = st.text_input(
                "Ask a question",
                placeholder="e.g. Which stocks are sensitive to interest rates?",
                key="kg_question_input",
            )
            kg_ask_btn = st.button("Ask", key="kg_ask_btn", type="primary")

            if kg_ask_btn and kg_question:
                with st.spinner("Querying knowledge graph..."):
                    try:
                        from infrastructure.knowledge_graph import StockKnowledgeGraph
                        kg = StockKnowledgeGraph()
                        kg_result = kg.query(kg_question, model=analysis_model, api_base=api_base)

                        st.markdown(f"**Answer:** {kg_result['answer']}")

                        with st.expander("Cypher Query", expanded=False):
                            st.code(kg_result["cypher"], language="cypher")

                        if kg_result["results"]:
                            with st.expander(f"Raw Results ({len(kg_result['results'])} rows)", expanded=False):
                                st.dataframe(kg_result["results"])

                        st.caption(f"Source: {kg_result['source']}")
                    except Exception as e:
                        st.error(f"Knowledge graph query failed: {e}")
            elif kg_ask_btn and not kg_question:
                st.warning("Please enter a question.")

    # Kafka Stream Explorer
    with st.expander("📨 Kafka Stream Explorer", expanded=False):
        st.caption("Ask a natural language question about Kafka topics, message counts, and recent stream data.")
        kafka_question = st.text_input(
            "Ask a question",
            placeholder="e.g. How many messages are in the stock-news topic?",
            key="kafka_question_input",
        )
        kafka_max_msgs = st.slider("Max messages to sample", min_value=3, max_value=50, value=10, key="kafka_max_msgs")
        kafka_ask_btn = st.button("Ask", key="kafka_ask_btn", type="primary")

        if kafka_ask_btn and kafka_question:
            with st.spinner("Querying Kafka..."):
                try:
                    from infrastructure.config import Config
                    if not Config.KAFKA_ENABLED:
                        st.warning("Kafka is not enabled. Set `kafka.enabled: true` in application.yml.")
                    else:
                        from infrastructure.kafka_consumer import KafkaExplorer
                        explorer = KafkaExplorer()
                        kafka_result = explorer.query(
                            kafka_question,
                            model=analysis_model,
                            api_base=api_base,
                            max_messages=kafka_max_msgs,
                        )

                        st.markdown(f"**Answer:** {kafka_result['answer']}")
                        st.caption(
                            f"Action: `{kafka_result['action']}`"
                            + (f" | Topic: `{kafka_result['topic']}`" if kafka_result.get('topic') else "")
                        )

                        if kafka_result.get("data"):
                            with st.expander("Raw Data", expanded=False):
                                st.json(kafka_result["data"])
                except Exception as e:
                    st.error(f"Kafka query failed: {e}")
        elif kafka_ask_btn and not kafka_question:
            st.warning("Please enter a question.")

    # PostgreSQL Explorer
    with st.expander("🗄️ PostgreSQL Explorer", expanded=False):
        st.caption("Ask a natural language question about stock prices, watchlist, and schedules.")
        pg_question = st.text_input(
            "Ask a question",
            placeholder="e.g. Which ticker has the most price history?",
            key="pg_question_input",
        )
        pg_ask_btn = st.button("Ask", key="pg_ask_btn", type="primary")

        if pg_ask_btn and pg_question:
            with st.spinner("Querying PostgreSQL..."):
                try:
                    from infrastructure.postgres_store import PostgresPriceStore
                    from infrastructure.config import Config
                    if not Config.POSTGRES_ENABLED:
                        st.warning("PostgreSQL is not enabled. Set `postgres.enabled: true` in application.yml.")
                    else:
                        store = PostgresPriceStore()
                        pg_result = store.query(pg_question, model=analysis_model, api_base=api_base)

                        st.markdown(f"**Answer:** {pg_result['answer']}")

                        with st.expander("SQL Query", expanded=False):
                            st.code(pg_result["sql"], language="sql")

                        if pg_result["results"]:
                            with st.expander(f"Raw Results ({len(pg_result['results'])} rows)", expanded=False):
                                st.dataframe(pg_result["results"])
                except Exception as e:
                    st.error(f"PostgreSQL query failed: {e}")
        elif pg_ask_btn and not pg_question:
            st.warning("Please enter a question.")

    # Qdrant Semantic Search Explorer
    with st.expander("🔍 Qdrant Semantic Search", expanded=False):
        st.caption("Ask a natural language question — searches vector embeddings across news, filings, transcripts, and more.")
        qdrant_question = st.text_input(
            "Ask a question",
            placeholder="e.g. What did analysts say about AAPL earnings?",
            key="qdrant_question_input",
        )
        qdrant_limit = st.slider("Max results", min_value=3, max_value=20, value=5, key="qdrant_limit")
        qdrant_ask_btn = st.button("Search", key="qdrant_ask_btn", type="primary")

        if qdrant_ask_btn and qdrant_question:
            with st.spinner("Searching Qdrant..."):
                try:
                    from infrastructure.config import Config
                    if not Config.QDRANT_ENABLED:
                        st.warning("Qdrant is not enabled. Set `qdrant.enabled: true` in application.yml.")
                    else:
                        from infrastructure.qdrant_store import QdrantStore
                        store = QdrantStore()
                        qdrant_result = store.query(
                            qdrant_question,
                            model=analysis_model,
                            api_base=api_base,
                            limit=qdrant_limit,
                        )

                        st.markdown(f"**Answer:** {qdrant_result['answer']}")
                        st.caption(
                            f"Collection: `{qdrant_result['collection']}` | "
                            f"Search phrase: *{qdrant_result['search_phrase']}* | "
                            f"Results: {qdrant_result['total_found']}"
                        )

                        if qdrant_result["results"]:
                            with st.expander(f"Retrieved Documents ({qdrant_result['total_found']})", expanded=False):
                                for i, r in enumerate(qdrant_result["results"]):
                                    st.markdown(f"**#{i+1}** — score: `{r['score']:.3f}`")
                                    st.json(r["payload"])
                                    st.divider()
                except Exception as e:
                    st.error(f"Qdrant query failed: {e}")
        elif qdrant_ask_btn and not qdrant_question:
            st.warning("Please enter a question.")

    # Options Screener
    from infrastructure.feature_flags import is_feature_enabled, FeatureFlag
    if is_feature_enabled(FeatureFlag.OPTIONS_SCREENER):
        with st.expander("🎯 Unusual Options Screener", expanded=False):
            st.caption("Screen for cheap options with unusual activity — type a question or set filters manually.")

            # Natural language input
            nl_col, btn_col = st.columns([5, 1])
            with nl_col:
                nl_options_query = st.text_input(
                    "Ask in plain English",
                    placeholder='e.g. "show me puts under $0.10 on TSLA with vol/OI above 2x"',
                    key="nl_options_query",
                    label_visibility="collapsed",
                )
            with btn_col:
                nl_parse_btn = st.button("Parse", key="nl_parse_btn", type="secondary")

            # Parse NL query and populate session state overrides
            if nl_parse_btn and nl_options_query:
                with st.spinner("Parsing your question..."):
                    _wl = st.session_state.get("watchlist", [])
                    parsed_params = parse_options_query(
                        nl_options_query, model=analysis_model,
                        api_base=api_base, watchlist=_wl
                    )
                if parsed_params.get("parsed"):
                    st.session_state["screen_parsed"] = parsed_params
                    st.success(
                        f"Parsed → price≤${parsed_params['max_price']:.2f} | "
                        f"type={parsed_params['option_type']} | "
                        f"vol≥{parsed_params['min_volume']} | "
                        f"vol/OI≥{parsed_params['min_vol_oi_ratio']}x | "
                        f"expirations={parsed_params['max_expirations']}"
                        + (f" | ticker={parsed_params['ticker']}" if parsed_params.get('ticker') else "")
                        + (" | watchlist=yes" if parsed_params.get('use_watchlist') else "")
                    )
                else:
                    st.warning("Could not parse the question. Please adjust filters manually.")

            # Read parsed values as widget defaults
            _p = st.session_state.get("screen_parsed", {})

            st.caption("Filters (auto-populated from your question, or set manually):")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                screen_max_price = st.number_input(
                    "Max option price ($)",
                    min_value=0.01, max_value=10.0,
                    value=float(_p.get("max_price", 0.25)), step=0.05,
                    key="screen_max_price",
                    help="Only show options with last price ≤ this amount"
                )
                _type_opts = ["both", "calls", "puts"]
                _type_default = _p.get("option_type", "both")
                screen_opt_type = st.selectbox(
                    "Option type",
                    options=_type_opts,
                    index=_type_opts.index(_type_default) if _type_default in _type_opts else 0,
                    key="screen_opt_type"
                )
            with col_b:
                screen_min_volume = st.number_input(
                    "Min volume",
                    min_value=1, max_value=100000,
                    value=int(_p.get("min_volume", 100)), step=50,
                    key="screen_min_volume",
                    help="Minimum contracts traded today"
                )
                screen_vol_oi_ratio = st.number_input(
                    "Min volume/OI ratio",
                    min_value=0.1, max_value=10.0,
                    value=float(_p.get("min_vol_oi_ratio", 0.5)), step=0.1,
                    key="screen_vol_oi_ratio",
                    help="Volume ÷ Open Interest — values >1 mean more volume than existing open interest (very unusual)"
                )
            with col_c:
                screen_expirations = st.slider(
                    "Expirations to scan",
                    min_value=1, max_value=6,
                    value=int(_p.get("max_expirations", 3)),
                    key="screen_expirations",
                    help="How many nearest expiration dates to scan per ticker"
                )
                use_watchlist_screen = st.checkbox(
                    "Scan entire watchlist",
                    value=bool(_p.get("use_watchlist", False)),
                    key="use_watchlist_screen",
                    help="If unchecked, scans only the ticker entered above"
                )

            # Override ticker from parsed query if present
            _parsed_ticker = _p.get("ticker")

            screen_btn = st.button("🔍 Screen Options", key="screen_options_btn", type="primary")

            if screen_btn:
                _effective_ticker = _parsed_ticker or ticker
                tickers_to_scan = (
                    st.session_state.get("watchlist", [])
                    if use_watchlist_screen
                    else ([_effective_ticker] if _effective_ticker else [])
                )
                if not tickers_to_scan:
                    st.warning("Enter a ticker symbol above or enable watchlist scanning.")
                else:
                    with st.spinner(f"Scanning options for {', '.join(tickers_to_scan[:5])}{'...' if len(tickers_to_scan) > 5 else ''}..."):
                        results_df = fetch_unusual_cheap_options(
                            tickers=tickers_to_scan,
                            max_price=screen_max_price,
                            option_type=screen_opt_type,
                            min_volume=int(screen_min_volume),
                            min_volume_oi_ratio=screen_vol_oi_ratio,
                            max_expirations=screen_expirations,
                        )

                    if results_df.empty:
                        st.info("No options found matching your criteria. Try increasing the max price or lowering the min volume/OI ratio.")
                    else:
                        st.success(f"Found **{len(results_df)}** unusual cheap option(s)")

                        # Highlight unusual activity (runs after rename, so use "vol/OI")
                        def _highlight(row):
                            if row["vol/OI"] >= 2.0:
                                return ["background-color: #ffe0b2"] * len(row)
                            elif row["vol/OI"] >= 1.0:
                                return ["background-color: #fff9c4"] * len(row)
                            return [""] * len(row)

                        display_df = results_df[[
                            "ticker", "type", "expiration", "strike",
                            "lastPrice", "bid", "ask",
                            "volume", "openInterest", "vol_oi_ratio",
                            "impliedVolatility", "inTheMoney", "contractSymbol"
                        ]].rename(columns={
                            "lastPrice": "price",
                            "openInterest": "OI",
                            "vol_oi_ratio": "vol/OI",
                            "impliedVolatility": "IV",
                            "inTheMoney": "ITM",
                            "contractSymbol": "contract",
                        })

                        st.dataframe(
                            display_df.style.apply(_highlight, axis=1),
                            width="stretch",
                            hide_index=True,
                        )

                        # Summary stats
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Calls", int((results_df["type"] == "CALL").sum()))
                        col2.metric("Puts", int((results_df["type"] == "PUT").sum()))
                        col3.metric("Avg Price", f"${results_df['lastPrice'].mean():.3f}")
                        col4.metric("Max Vol/OI", f"{results_df['vol_oi_ratio'].max():.1f}x")

                        st.caption(
                            "🟠 Orange = vol/OI ≥ 2x (extremely unusual)  |  "
                            "🟡 Yellow = vol/OI ≥ 1x (unusual)  |  "
                            "vol/OI > 1 means today's volume exceeds all existing open interest"
                        )

                        # LLM summary of results
                        if nl_options_query:
                            with st.spinner("Summarising results..."):
                                try:
                                    import litellm
                                    from infrastructure.config import Config as _Cfg
                                    top = results_df.head(10).to_dict(orient="records")
                                    summary_prompt = (
                                        f'User asked: "{nl_options_query}"\n'
                                        f"Found {len(results_df)} options. Top results:\n{top}\n\n"
                                        "Write 2-3 sentences summarising what was found, "
                                        "highlighting the most unusual contracts and what they might signal."
                                    )
                                    _kwargs = {
                                        "model": analysis_model or _Cfg.DEFAULT_MODEL,
                                        "messages": [{"role": "user", "content": summary_prompt}]
                                    }
                                    if api_base:
                                        _kwargs["api_base"] = api_base
                                    _resp = litellm.completion(**_kwargs)
                                    st.info(_resp.choices[0].message.content.strip())
                                except Exception:
                                    pass

    st.divider()

    # Run analysis on button click
    if analyze_btn:
        try:
            result = run_analysis(ticker, days, mode, analysis_model, verbose, api_base, status_container)

            if result:
                # Run and display ML analysis with progress (guarded by ml_analysis feature flag)
                ensemble_result = None
                from infrastructure.feature_flags import is_feature_enabled, FeatureFlag
                if result.get("agent_details") and is_feature_enabled(FeatureFlag.ML_ANALYSIS):
                    with status_container.status("🤖 Running Machine Learning Analysis...", expanded=True) as ml_status:
                        import sys

                        ml_status.write("🚀 **ML analysis started**")
                        ml_status.write("🧠 **Pipeline:** `EnsembleScorer` (weighted consensus over agent outputs)")
                        ml_status.write("ℹ️ **Model policy:** `SignalClassifier` uses **XGBoost** automatically when `ml_analysis` flag is ON; falls back to RandomForest if XGBoost is not installed.")

                        ml_progress = ml_status.progress(0, text="Initializing ML modules...")
                        ml_step = ml_status.empty()

                        try:
                            from ml import EnsembleScorer

                            # Step 1: Ensemble Scoring
                            print("  [ML] Running Ensemble Scoring...", file=sys.stderr)
                            ml_progress.progress(0.33, text="Step 1/3: Ensemble Scoring")
                            ml_step.write("🔄 Running **Ensemble Scoring** (combining all active agent signals)...")

                            scorer = EnsembleScorer()
                            ensemble_result = scorer.score(result["agent_details"])
                            st.session_state["ensemble_result"] = ensemble_result
                            print("  [ML] Ensemble Scoring complete.", file=sys.stderr)

                            # Step 2: Signal weighting
                            ml_progress.progress(0.66, text="Step 2/3: Signal Weighting")
                            ml_step.write("🔄 Running **Signal Weighting** (calculating confidence)...")
                            print("  [ML] Running Signal Weighting...", file=sys.stderr)

                            # Step 3: Final aggregation
                            ml_progress.progress(1.0, text="Step 3/3: Final Aggregation")
                            ml_step.write("🔄 Running **Final Aggregation**...")
                            print("  [ML] Running Final Aggregation...", file=sys.stderr)

                            ml_progress.progress(1.0, text="✅ ML Analysis complete!")
                            ml_step.write("✅ **Machine Learning Analysis complete!**")
                            print("  [ML] Machine Learning Analysis complete.", file=sys.stderr)

                            ml_status.update(label="✅ ML Analysis complete!", state="complete", expanded=False)

                        except Exception as e:
                            print(f"  [ML] Error: {e}", file=sys.stderr)
                            ml_status.update(label="⚠️ ML Analysis failed", state="error", expanded=False)
                            st.warning(f"ML analysis not available: {e}")
                            ensemble_result = None

                # Reconcile final decision and persist enriched result
                decision = reconcile_signal_decision(result, ensemble_result)
                result.update(decision)
                brief_reasoning = result.get("reasoning", "")
                result["reasoning_brief"] = brief_reasoning
                result["reasoning"] = build_detailed_reasoning(result, ensemble_result)

                st.session_state["last_result"] = result
                st.session_state["last_ticker"] = ticker
                st.session_state["last_timestamp"] = datetime.now()

                # Display results after reconciliation so UI shows a single clear decision.
                st.success("✅ Analysis Complete!")

                # Display action buttons at the top of the result section.
                company_name = info.get("shortName") if info else None
                current_indicators = compute_technical_indicators(extended_hist) if extended_hist is not None and not extended_hist.empty else None
                ml_results_for_report = {}
                if st.session_state.get("ensemble_result"):
                    ml_results_for_report["ensemble"] = st.session_state["ensemble_result"]
                with top_actions_container:
                    display_action_buttons(ticker, result, company_name, current_indicators, ml_results_for_report)
                display_signal_result(result)

                # Display ensemble details (supporting evidence)
                if ensemble_result:
                    st.subheader("⚖️ Ensemble Score")

                    signal = ensemble_result.get("ensemble_signal", "HOLD")
                    conf = ensemble_result.get("ensemble_confidence", 0.5)
                    score = ensemble_result.get("ensemble_score", 0)

                    signal_colors = {"BUY": "green", "SELL": "red", "HOLD": "orange"}
                    color = signal_colors.get(signal, "gray")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Ensemble Signal", signal)
                        st.markdown(f"<div style='background-color:{color};padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;font-size:24px;'>{signal}</div>", unsafe_allow_html=True)
                    with col2:
                        st.metric("Confidence", f"{conf*100:.1f}%")
                    with col3:
                        st.metric("Score", f"{score:+.2f}")

                    dist = ensemble_result.get("signal_distribution", {})
                    if dist:
                        st.caption(f"Agent votes: 🟢 BUY: {dist.get('BUY', 0)} | 🟡 HOLD: {dist.get('HOLD', 0)} | 🔴 SELL: {dist.get('SELL', 0)}")

                # Display agent details if verbose
                if verbose and result.get("agent_details"):
                    display_agent_details(result["agent_details"])

                # Raw JSON output
                with st.expander("Raw JSON Output"):
                    st.json(result)
            else:
                st.error("Analysis returned no results. Please try again.")

        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")
            st.exception(e)

    # Show last result if exists
    elif "last_result" in st.session_state and st.session_state.get("last_ticker") == ticker:
        st.info(f"Showing cached result from {st.session_state['last_timestamp'].strftime('%H:%M:%S')}")

        # Display action buttons at the top for cached results.
        company_name = info.get("shortName") if info else None
        current_indicators = compute_technical_indicators(extended_hist) if extended_hist is not None and not extended_hist.empty else None
        ml_results_for_report = {}
        if st.session_state.get("ensemble_result"):
            ml_results_for_report["ensemble"] = st.session_state["ensemble_result"]
        cached_result = st.session_state["last_result"]
        if "reasoning_detailed" not in cached_result and "reasoning_brief" not in cached_result:
            cached_result["reasoning_brief"] = cached_result.get("reasoning", "")
            cached_result["reasoning"] = build_detailed_reasoning(cached_result, st.session_state.get("ensemble_result"))
        with top_actions_container:
            display_action_buttons(ticker, cached_result, company_name, current_indicators, ml_results_for_report)
        display_signal_result(cached_result)

        if verbose and st.session_state["last_result"].get("agent_details"):
            display_agent_details(st.session_state["last_result"]["agent_details"])
    else:
        # Show instructions
        st.info("👈 Enter a ticker symbol and click 'Analyze Stock' to get started!")

        # Show example output
        with st.expander("Example Output"):
            example = {
                "signal": "BUY",
                "confidence": 0.78,
                "target_price": 195.50,
                "stop_loss": 165.00,
                "potential_upside_pct": 12.5,
                "potential_downside_pct": 5.2,
                "sentiment_score": 0.45,
                "reasoning": "Strong technical indicators with RSI at 55, positive MACD crossover. Analyst consensus is bullish with 85% buy ratings. Recent earnings beat expectations.",
                "agents_used": 47,
            }
            display_signal_result(example)

    # ── Auto-Refresh Logic ──
    if st.session_state.schedule_enabled and st.session_state.auto_refresh_interval is not None:
        schedule_type = st.session_state.auto_refresh_interval

        # Calculate refresh interval in seconds
        if isinstance(schedule_type, int):
            refresh_interval = schedule_type
        elif schedule_type in ["pre_market", "after_hours"]:
            refresh_interval = 300  # 5 minutes during market periods
        else:
            refresh_interval = 300  # Default 5 minutes

        # Check if we should refresh
        if should_auto_refresh(schedule_type, refresh_interval if schedule_type == "custom" else None):
            st.session_state.last_refresh = datetime.now()
            st.toast("🔄 Auto-refreshing dashboard...", icon="🔄")
            time.sleep(1)
            st.rerun()

        # Display countdown to next refresh
        if st.session_state.last_refresh:
            elapsed = (datetime.now() - st.session_state.last_refresh).total_seconds()
            remaining = max(0, refresh_interval - elapsed)
            if remaining > 0:
                mins, secs = divmod(int(remaining), 60)
                st.sidebar.caption(f"⏱️ Next refresh in: {mins:02d}:{secs:02d}")

        # Use Streamlit's auto-rerun feature (checks periodically)
        # This will rerun the script after the specified interval
        try:
            # st.experimental_rerun() is deprecated, use fragment or manual approach
            # For auto-refresh, we'll use a JavaScript-based approach
            import streamlit.components.v1 as components
            components.html(
                f"""
                <script>
                    setTimeout(function() {{
                        window.parent.location.reload();
                    }}, {min(refresh_interval * 1000, 60000)});
                </script>
                """,
                height=0
            )
        except Exception:
            pass  # Fallback: manual refresh required


if __name__ == "__main__":
    main()
