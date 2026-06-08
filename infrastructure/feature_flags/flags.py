"""
Feature flag definitions and defaults.

This module defines the available feature flags for the Stock Signal application
and their default values. Feature flags allow controlled rollout of features
across different environments.

Architecture:
    FeatureFlag (Enum) --> FEATURE_FLAG_DEFAULTS (Dict) --> get_default()

Usage:
    from infrastructure.feature_flags.flags import FeatureFlag, get_default

    # Get a flag enum
    flag = FeatureFlag.WATCHLIST_ANALYSIS

    # Get its default value
    default = get_default(flag)  # Returns False

Adding New Flags:
    1. Add a new enum member to FeatureFlag class
    2. Add default value to FEATURE_FLAG_DEFAULTS dict
    3. Create the flag in Unleash UI (local) or Terraform (AWS)

References:
    - Unleash Feature Flags: https://docs.getunleash.io/
    - AWS AppConfig: https://docs.aws.amazon.com/appconfig/
"""

from enum import Enum
from typing import Dict


class FeatureFlag(str, Enum):
    """
    Available feature flags for the Stock Signal application.

    This enum extends both str and Enum to allow easy string conversion
    when sending flag names to external providers (Unleash, AppConfig).

    Naming Convention:
        - Use snake_case for flag names
        - Flag names should be descriptive of the feature
        - Prefix with feature area if needed (e.g., 'analysis_', 'ui_')

    Attributes:
        SINGLE_STOCK_ANALYSIS: Core feature for analyzing individual stocks.
            Always enabled by default as it's the primary functionality.

        WATCHLIST_ANALYSIS: Batch analysis of multiple stocks from a watchlist.
            Disabled by default to control resource usage.

        PREMARKET_ANALYSIS: Analysis during pre-market hours (4:00 AM - 9:30 AM ET).
            Disabled by default; enable for users who trade pre-market.

        AFTERMARKET_ANALYSIS: Analysis during after-hours (4:00 PM - 8:00 PM ET).
            Disabled by default; enable for users who trade after-hours.

    Example:
        >>> flag = FeatureFlag.WATCHLIST_ANALYSIS
        >>> flag.value
        'watchlist_analysis'
        >>> str(flag)
        'watchlist_analysis'
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Core Analysis Features
    # ─────────────────────────────────────────────────────────────────────────

    # Core feature - single stock analysis capability
    # This is the primary feature and should always be enabled
    SINGLE_STOCK_ANALYSIS = "single_stock_analysis"

    # Enable watchlist-based batch analysis
    # When enabled, users can analyze multiple stocks at once from their watchlist
    # This increases API/LLM usage, so it's disabled by default
    WATCHLIST_ANALYSIS = "watchlist_analysis"

    # ─────────────────────────────────────────────────────────────────────────
    # Time-Based Analysis Features
    # ─────────────────────────────────────────────────────────────────────────

    # Enable pre-market analysis (4:00 AM - 9:30 AM ET)
    # Pre-market data is more volatile and less liquid
    # Useful for day traders who want early signals
    PREMARKET_ANALYSIS = "premarket_analysis"

    # Enable after-market analysis (4:00 PM - 8:00 PM ET)
    # After-hours data reflects earnings announcements and news
    # Useful for swing traders reacting to after-hours events
    AFTERMARKET_ANALYSIS = "aftermarket_analysis"

    # ─────────────────────────────────────────────────────────────────────────
    # Per-Agent Flags (Multi-Agent Mode)
    # Each flag controls whether that agent runs during orchestration.
    # All default to True so existing behavior is unchanged.
    # Toggle individual agents off in Unleash/AppConfig without code changes.
    # ─────────────────────────────────────────────────────────────────────────

    AGENT_TECHNICAL = "agent_technical"
    AGENT_NEWS = "agent_news"
    AGENT_SEC = "agent_sec"
    AGENT_SENTIMENT = "agent_sentiment"
    AGENT_ZACKS = "agent_zacks"
    AGENT_TIPRANKS = "agent_tipranks"
    AGENT_SEEKINGALPHA = "agent_seekingalpha"
    AGENT_INSIDER = "agent_insider"
    AGENT_MOTLEYFOOL = "agent_motleyfool"
    AGENT_STOCKSTORY = "agent_stockstory"
    AGENT_YAHOOFINANCE = "agent_yahoofinance"
    AGENT_MORNINGSTAR = "agent_morningstar"
    AGENT_GURUFOCUS = "agent_gurufocus"
    AGENT_TRADINGVIEW = "agent_tradingview"
    AGENT_STOCKROVER = "agent_stockrover"
    AGENT_SIMPLYWALLST = "agent_simplywallst"
    AGENT_ALPHASPREAD = "agent_alphaspread"
    AGENT_FACTSET = "agent_factset"
    AGENT_CAPITALIQ = "agent_capitaliq"
    AGENT_MARKETBEAT = "agent_marketbeat"
    AGENT_REFINITIV = "agent_refinitiv"
    AGENT_MACROTRENDS = "agent_macrotrends"
    AGENT_YCHARTS = "agent_ycharts"
    AGENT_KOYFIN = "agent_koyfin"
    AGENT_VALUELINE = "agent_valueline"
    AGENT_XTWITTER = "agent_xtwitter"
    AGENT_FACEBOOK = "agent_facebook"
    AGENT_INSTAGRAM = "agent_instagram"
    AGENT_CNBC = "agent_cnbc"
    AGENT_BLOOMBERG = "agent_bloomberg"
    AGENT_WSJ = "agent_wsj"
    AGENT_MARKETWATCH = "agent_marketwatch"
    AGENT_FOXBUSINESS = "agent_foxbusiness"
    AGENT_BARRONS = "agent_barrons"
    AGENT_INSIDERMONKEY = "agent_insidermonkey"
    AGENT_QUIVERQUANT = "agent_quiverquant"
    AGENT_DATAROMA = "agent_dataroma"
    AGENT_OPENINSIDER = "agent_openinsider"
    AGENT_WHALEWISDOM = "agent_whalewisdom"
    AGENT_ETFCOM = "agent_etfcom"
    AGENT_ETFDB = "agent_etfdb"
    AGENT_GLOBALXETF = "agent_globalxetf"
    AGENT_ARKINVEST = "agent_arkinvest"
    AGENT_MORNINGSTARETF = "agent_morningstaretf"
    AGENT_REDDIT = "agent_reddit"
    AGENT_STOCKTWITS = "agent_stocktwits"
    AGENT_OPTIONS_FLOW = "agent_options_flow"
    AGENT_INVESTOR_PRESENTATION = "agent_investor_presentation"
    AGENT_EARNINGS_CALL = "agent_earnings_call"

    # ─────────────────────────────────────────────────────────────────────────
    # ML Analysis
    # Master switch for the entire ML pipeline (LSTM, XGBoost, EnsembleScorer).
    # ─────────────────────────────────────────────────────────────────────────
    ML_ANALYSIS = "ml_analysis"

    # ─────────────────────────────────────────────────────────────────────────
    # Knowledge Graph
    # Enables the dual-layer Neo4j + NetworkX knowledge graph for sector/macro
    # context in the neuro-symbolic validator. Requires Neo4j running in Docker.
    # ─────────────────────────────────────────────────────────────────────────
    KNOWLEDGE_GRAPH = "knowledge_graph"

    # ─────────────────────────────────────────────────────────────────────────
    # Options Screener
    # Enables the Unusual Options Screener section in the Streamlit dashboard.
    # Supports natural language query parsing + yfinance options chain filtering.
    # ─────────────────────────────────────────────────────────────────────────
    OPTIONS_SCREENER = "options_screener"


# ─────────────────────────────────────────────────────────────────────────────
# Default Values
# ─────────────────────────────────────────────────────────────────────────────

# Default values for each feature flag
# These are used when:
#   1. The feature flag provider is unavailable
#   2. The flag hasn't been created in the provider yet
#   3. As a fallback for any errors
#
# Production Recommendation:
#   - Keep new features disabled (False) by default
#   - Enable core features (True) that are essential for the app
#   - Use the provider (Unleash/AppConfig) to enable features per environment
FEATURE_FLAG_DEFAULTS: Dict[FeatureFlag, bool] = {
    # Core feature - always enabled by default
    FeatureFlag.SINGLE_STOCK_ANALYSIS: True,

    # Batch features - disabled by default to control costs
    FeatureFlag.WATCHLIST_ANALYSIS: False,

    # Extended hours features - disabled by default
    # Enable per-environment based on user needs
    FeatureFlag.PREMARKET_ANALYSIS: False,
    FeatureFlag.AFTERMARKET_ANALYSIS: False,

    # Per-agent flags — all enabled by default to preserve existing behavior.
    # Toggle individual agents off in Unleash/AppConfig without code changes.
    FeatureFlag.AGENT_TECHNICAL: True,
    FeatureFlag.AGENT_NEWS: True,
    FeatureFlag.AGENT_SEC: True,
    FeatureFlag.AGENT_SENTIMENT: True,
    FeatureFlag.AGENT_ZACKS: True,
    FeatureFlag.AGENT_TIPRANKS: True,
    FeatureFlag.AGENT_SEEKINGALPHA: True,
    FeatureFlag.AGENT_INSIDER: True,
    FeatureFlag.AGENT_MOTLEYFOOL: True,
    FeatureFlag.AGENT_STOCKSTORY: True,
    FeatureFlag.AGENT_YAHOOFINANCE: True,
    FeatureFlag.AGENT_MORNINGSTAR: True,
    FeatureFlag.AGENT_GURUFOCUS: True,
    FeatureFlag.AGENT_TRADINGVIEW: True,
    FeatureFlag.AGENT_STOCKROVER: True,
    FeatureFlag.AGENT_SIMPLYWALLST: True,
    FeatureFlag.AGENT_ALPHASPREAD: True,
    FeatureFlag.AGENT_FACTSET: True,
    FeatureFlag.AGENT_CAPITALIQ: True,
    FeatureFlag.AGENT_MARKETBEAT: True,
    FeatureFlag.AGENT_REFINITIV: True,
    FeatureFlag.AGENT_MACROTRENDS: True,
    FeatureFlag.AGENT_YCHARTS: True,
    FeatureFlag.AGENT_KOYFIN: True,
    FeatureFlag.AGENT_VALUELINE: True,
    FeatureFlag.AGENT_XTWITTER: True,
    FeatureFlag.AGENT_FACEBOOK: True,
    FeatureFlag.AGENT_INSTAGRAM: True,
    FeatureFlag.AGENT_CNBC: True,
    FeatureFlag.AGENT_BLOOMBERG: True,
    FeatureFlag.AGENT_WSJ: True,
    FeatureFlag.AGENT_MARKETWATCH: True,
    FeatureFlag.AGENT_FOXBUSINESS: True,
    FeatureFlag.AGENT_BARRONS: True,
    FeatureFlag.AGENT_INSIDERMONKEY: True,
    FeatureFlag.AGENT_QUIVERQUANT: True,
    FeatureFlag.AGENT_DATAROMA: True,
    FeatureFlag.AGENT_OPENINSIDER: True,
    FeatureFlag.AGENT_WHALEWISDOM: True,
    FeatureFlag.AGENT_ETFCOM: True,
    FeatureFlag.AGENT_ETFDB: True,
    FeatureFlag.AGENT_GLOBALXETF: True,
    FeatureFlag.AGENT_ARKINVEST: True,
    FeatureFlag.AGENT_MORNINGSTARETF: True,
    FeatureFlag.AGENT_REDDIT: True,
    FeatureFlag.AGENT_STOCKTWITS: True,
    FeatureFlag.AGENT_OPTIONS_FLOW: True,
    FeatureFlag.AGENT_INVESTOR_PRESENTATION: True,
    FeatureFlag.AGENT_EARNINGS_CALL: True,

    # ML pipeline — enabled by default
    FeatureFlag.ML_ANALYSIS: True,

    # Knowledge graph — disabled by default (requires Neo4j running in Docker)
    FeatureFlag.KNOWLEDGE_GRAPH: False,

    # Options screener — enabled by default
    FeatureFlag.OPTIONS_SCREENER: True,
}


def get_default(flag: FeatureFlag) -> bool:
    """
    Get the default value for a feature flag.

    This function provides a safe way to retrieve default values,
    returning False for any unknown flags.

    Args:
        flag: The FeatureFlag enum member to look up.

    Returns:
        bool: The default value for the flag (True/False).
              Returns False if the flag is not in FEATURE_FLAG_DEFAULTS.

    Example:
        >>> get_default(FeatureFlag.SINGLE_STOCK_ANALYSIS)
        True
        >>> get_default(FeatureFlag.WATCHLIST_ANALYSIS)
        False
    """
    return FEATURE_FLAG_DEFAULTS.get(flag, False)
