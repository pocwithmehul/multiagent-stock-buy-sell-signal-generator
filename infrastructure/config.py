"""Centralized configuration from application.yml and environment variables."""

import os
from pathlib import Path
from typing import Any

import yaml


# Environment detection
APP_ENV = os.getenv("APP_ENV", "local").lower()
IS_AWS = APP_ENV in ("qa", "stg", "staging", "prod", "production")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def _load_yaml_config() -> dict[str, Any]:
    """Load configuration from application.yml if it exists."""
    config_paths = [
        Path("application.yml"),
        Path("application.yaml"),
        Path(__file__).parent.parent / "application.yml",
        Path(__file__).parent.parent / "application.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
    return {}


def _get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """Get nested value from dict using dot-notation keys."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default


# Load YAML config once at module import
_yaml_config = _load_yaml_config()


class Config:
    """Configuration from application.yml with env var overrides."""

    # Debug mode - controls verbose data output from agents
    DEBUG: bool = os.getenv(
        "DEBUG",
        str(_get_nested(_yaml_config, "debug", default=False))
    ).lower() in ("true", "1", "yes")

    # Multi-agent mode - use 47 specialized agents instead of single agent
    MULTI_AGENT_ENABLED: bool = os.getenv(
        "MULTI_AGENT_ENABLED",
        str(_get_nested(_yaml_config, "multi_agent", "enabled", default=False))
    ).lower() in ("true", "1", "yes")

    # Kafka
    KAFKA_ENABLED: bool = os.getenv(
        "KAFKA_ENABLED",
        str(_get_nested(_yaml_config, "kafka", "enabled", default=False))
    ).lower() in ("true", "1", "yes")
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        _get_nested(_yaml_config, "kafka", "bootstrap_servers", default="localhost:9092")
    )
    KAFKA_TOPIC_PRICES: str = _get_nested(_yaml_config, "kafka", "topics", "prices", default="stock-prices")
    KAFKA_TOPIC_NEWS: str = _get_nested(_yaml_config, "kafka", "topics", "news", default="stock-news")
    KAFKA_TOPIC_FILINGS: str = _get_nested(_yaml_config, "kafka", "topics", "filings", default="sec-filings")
    KAFKA_TOPIC_EARNINGS_CALL: str = _get_nested(_yaml_config, "kafka", "topics", "earnings_call", default="earnings-call-live")

    # Whisper transcription
    WHISPER_MODEL_SIZE: str = os.getenv(
        "WHISPER_MODEL_SIZE",
        _get_nested(_yaml_config, "whisper", "model_size", default="base")
    )
    EARNINGS_CALL_CHUNK_SECONDS: int = int(os.getenv(
        "EARNINGS_CALL_CHUNK_SECONDS",
        _get_nested(_yaml_config, "whisper", "chunk_seconds", default=30)
    ))

    # Qdrant
    QDRANT_ENABLED: bool = os.getenv(
        "QDRANT_ENABLED",
        str(_get_nested(_yaml_config, "qdrant", "enabled", default=False))
    ).lower() in ("true", "1", "yes")
    QDRANT_HOST: str = os.getenv(
        "QDRANT_HOST",
        _get_nested(_yaml_config, "qdrant", "host", default="localhost")
    )
    QDRANT_PORT: int = int(os.getenv(
        "QDRANT_PORT",
        _get_nested(_yaml_config, "qdrant", "port", default=6333)
    ))
    QDRANT_DATABASE: str = os.getenv(
        "QDRANT_DATABASE",
        _get_nested(_yaml_config, "qdrant", "database", default="stock-signal")
    )
    QDRANT_COLLECTION_NEWS: str = _get_nested(_yaml_config, "qdrant", "collections", "news", default="stock_news")
    QDRANT_COLLECTION_FILINGS: str = _get_nested(_yaml_config, "qdrant", "collections", "filings", default="sec_filings")
    QDRANT_COLLECTION_PRICES: str = _get_nested(_yaml_config, "qdrant", "collections", "prices", default="stock_prices")

    # Neo4j Knowledge Graph
    NEO4J_ENABLED: bool = os.getenv(
        "NEO4J_ENABLED",
        str(_get_nested(_yaml_config, "neo4j", "enabled", default=False))
    ).lower() in ("true", "1", "yes")
    NEO4J_URI: str = os.getenv(
        "NEO4J_URI",
        _get_nested(_yaml_config, "neo4j", "uri", default="bolt://localhost:7687")
    )
    NEO4J_USER: str = os.getenv(
        "NEO4J_USER",
        _get_nested(_yaml_config, "neo4j", "user", default="neo4j")
    )
    NEO4J_PASSWORD: str = os.getenv(
        "NEO4J_PASSWORD",
        _get_nested(_yaml_config, "neo4j", "password", default="neo4j_password")
    )
    NEO4J_DATABASE: str = os.getenv(
        "NEO4J_DATABASE",
        _get_nested(_yaml_config, "neo4j", "database", default="neo4j")
    )

    # PostgreSQL (historical price cache)
    POSTGRES_ENABLED: bool = os.getenv(
        "POSTGRES_ENABLED",
        str(_get_nested(_yaml_config, "postgres", "enabled", default=False))
    ).lower() in ("true", "1", "yes")
    POSTGRES_HOST: str = os.getenv(
        "POSTGRES_HOST",
        _get_nested(_yaml_config, "postgres", "host", default="localhost")
    )
    POSTGRES_PORT: int = int(os.getenv(
        "POSTGRES_PORT",
        _get_nested(_yaml_config, "postgres", "port", default=5432)
    ))
    POSTGRES_DATABASE: str = os.getenv(
        "POSTGRES_DATABASE",
        _get_nested(_yaml_config, "postgres", "database", default="stock_signal")
    )
    POSTGRES_USER: str = os.getenv(
        "POSTGRES_USER",
        _get_nested(_yaml_config, "postgres", "user", default="postgres")
    )
    POSTGRES_PASSWORD: str = os.getenv(
        "POSTGRES_PASSWORD",
        _get_nested(_yaml_config, "postgres", "password", default="")
    )
    POSTGRES_SSLMODE: str = os.getenv(
        "POSTGRES_SSLMODE",
        _get_nested(_yaml_config, "postgres", "sslmode", default="prefer")
    )
    POSTGRES_CONNECT_TIMEOUT: int = int(os.getenv(
        "POSTGRES_CONNECT_TIMEOUT",
        _get_nested(_yaml_config, "postgres", "connect_timeout", default=5)
    ))
    POSTGRES_PRICES_TABLE: str = os.getenv(
        "POSTGRES_PRICES_TABLE",
        _get_nested(_yaml_config, "postgres", "prices_table", default="stock_prices_daily")
    )
    POSTGRES_SCHEDULES_TABLE: str = os.getenv(
        "POSTGRES_SCHEDULES_TABLE",
        _get_nested(_yaml_config, "postgres", "schedules_table", default="stock_schedule_configs")
    )
    POSTGRES_WATCHLIST_TABLE: str = os.getenv(
        "POSTGRES_WATCHLIST_TABLE",
        _get_nested(_yaml_config, "postgres", "watchlist_table", default="stock_watchlist")
    )
    POSTGRES_BACKFILL_YEARS: int = int(os.getenv(
        "POSTGRES_BACKFILL_YEARS",
        _get_nested(_yaml_config, "postgres", "backfill_years", default=5)
    ))

    # Embeddings
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        _get_nested(_yaml_config, "embeddings", "model", default="all-MiniLM-L6-v2")
    )
    EMBEDDING_DIM: int = _get_nested(_yaml_config, "embeddings", "dimension", default=384)

    # SEC EDGAR
    SEC_USER_AGENT: str = os.getenv(
        "SEC_USER_AGENT",
        _get_nested(_yaml_config, "sec", "user_agent", default="StockSignalAgent/1.0 (contact@example.com)")
    )
    SEC_BASE_URL: str = _get_nested(_yaml_config, "sec", "base_url", default="https://efts.sec.gov/LATEST")
    SEC_SUBMISSIONS_URL: str = _get_nested(_yaml_config, "sec", "submissions_url", default="https://data.sec.gov/submissions")
    SEC_TICKERS_URL: str = _get_nested(_yaml_config, "sec", "tickers_url", default="https://www.sec.gov/files/company_tickers.json")

    # Zacks
    ZACKS_USER_AGENT: str = os.getenv(
        "ZACKS_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    ZACKS_BASE_URL: str = "https://www.zacks.com/stock/quote"
    KAFKA_TOPIC_ZACKS: str = "zacks-data"
    QDRANT_COLLECTION_ZACKS: str = "zacks_data"

    # TipRanks (analyst consensus via yfinance)
    KAFKA_TOPIC_TIPRANKS: str = "tipranks-data"
    QDRANT_COLLECTION_TIPRANKS: str = "tipranks_data"

    # SeekingAlpha (fundamentals & estimates via yfinance)
    KAFKA_TOPIC_SEEKINGALPHA: str = "seekingalpha-data"
    QDRANT_COLLECTION_SEEKINGALPHA: str = "seekingalpha_data"

    # Insider & Institutional (Benzinga/Investopedia style via yfinance)
    KAFKA_TOPIC_INSIDER: str = "insider-institutional-data"
    QDRANT_COLLECTION_INSIDER: str = "insider_institutional_data"

    # MotleyFool (quality & growth metrics via yfinance)
    KAFKA_TOPIC_MOTLEYFOOL: str = "motleyfool-data"
    QDRANT_COLLECTION_MOTLEYFOOL: str = "motleyfool_data"

    # StockStory (business fundamentals, risk, market position via yfinance)
    KAFKA_TOPIC_STOCKSTORY: str = "stockstory-data"
    QDRANT_COLLECTION_STOCKSTORY: str = "stockstory_data"

    # Yahoo Finance (options, trading activity, dividends via yfinance)
    KAFKA_TOPIC_YAHOOFINANCE: str = "yahoofinance-data"
    QDRANT_COLLECTION_YAHOOFINANCE: str = "yahoofinance_data"

    # Morningstar (moat, fair value, financial health via yfinance)
    KAFKA_TOPIC_MORNINGSTAR: str = "morningstar-data"
    QDRANT_COLLECTION_MORNINGSTAR: str = "morningstar_data"

    # GuruFocus (value investing metrics via yfinance)
    KAFKA_TOPIC_GURUFOCUS: str = "gurufocus-data"
    QDRANT_COLLECTION_GURUFOCUS: str = "gurufocus_data"

    # TradingView (technical oscillators and MAs via yfinance)
    KAFKA_TOPIC_TRADINGVIEW: str = "tradingview-data"
    QDRANT_COLLECTION_TRADINGVIEW: str = "tradingview_data"

    # Stock Rover (quality, value, growth, sentiment scores via yfinance)
    KAFKA_TOPIC_STOCKROVER: str = "stockrover-data"
    QDRANT_COLLECTION_STOCKROVER: str = "stockrover_data"

    # Simply Wall St (snowflake analysis via yfinance)
    KAFKA_TOPIC_SIMPLYWALLST: str = "simplywallst-data"
    QDRANT_COLLECTION_SIMPLYWALLST: str = "simplywallst_data"

    # Alpha Spread (intrinsic value, DCF analysis via yfinance)
    KAFKA_TOPIC_ALPHASPREAD: str = "alphaspread-data"
    QDRANT_COLLECTION_ALPHASPREAD: str = "alphaspread_data"

    # FactSet (earnings quality, estimate revisions via yfinance)
    KAFKA_TOPIC_FACTSET: str = "factset-data"
    QDRANT_COLLECTION_FACTSET: str = "factset_data"

    # S&P Capital IQ (credit metrics, profitability via yfinance)
    KAFKA_TOPIC_CAPITALIQ: str = "capitaliq-data"
    QDRANT_COLLECTION_CAPITALIQ: str = "capitaliq_data"

    # MarketBeat (analyst ratings, earnings beat rate via yfinance)
    KAFKA_TOPIC_MARKETBEAT: str = "marketbeat-data"
    QDRANT_COLLECTION_MARKETBEAT: str = "marketbeat_data"

    # Refinitiv (consensus estimates, market data via yfinance)
    KAFKA_TOPIC_REFINITIV: str = "refinitiv-data"
    QDRANT_COLLECTION_REFINITIV: str = "refinitiv_data"

    # Macrotrends (historical price and financial trends via yfinance)
    KAFKA_TOPIC_MACROTRENDS: str = "macrotrends-data"
    QDRANT_COLLECTION_MACROTRENDS: str = "macrotrends_data"

    # YCharts (valuation, profitability, momentum charts via yfinance)
    KAFKA_TOPIC_YCHARTS: str = "ycharts-data"
    QDRANT_COLLECTION_YCHARTS: str = "ycharts_data"

    # Koyfin (screening fundamentals, technicals, estimates via yfinance)
    KAFKA_TOPIC_KOYFIN: str = "koyfin-data"
    QDRANT_COLLECTION_KOYFIN: str = "koyfin_data"

    # Value Line (timeliness, safety, projections via yfinance)
    KAFKA_TOPIC_VALUELINE: str = "valueline-data"
    QDRANT_COLLECTION_VALUELINE: str = "valueline_data"

    # X/Twitter (social sentiment via yfinance news proxy)
    KAFKA_TOPIC_XTWITTER: str = "xtwitter-data"
    QDRANT_COLLECTION_XTWITTER: str = "xtwitter_data"

    # Facebook (social engagement metrics via yfinance proxy)
    KAFKA_TOPIC_FACEBOOK: str = "facebook-data"
    QDRANT_COLLECTION_FACEBOOK: str = "facebook_data"

    # Instagram (brand/visual engagement via yfinance proxy)
    KAFKA_TOPIC_INSTAGRAM: str = "instagram-data"
    QDRANT_COLLECTION_INSTAGRAM: str = "instagram_data"

    # CNBC (market news and trading sentiment via yfinance proxy)
    KAFKA_TOPIC_CNBC: str = "cnbc-data"
    QDRANT_COLLECTION_CNBC: str = "cnbc_data"

    # Bloomberg (institutional-grade financial data via yfinance proxy)
    KAFKA_TOPIC_BLOOMBERG: str = "bloomberg-data"
    QDRANT_COLLECTION_BLOOMBERG: str = "bloomberg_data"

    # Wall Street Journal (business news and market data via yfinance proxy)
    KAFKA_TOPIC_WSJ: str = "wsj-data"
    QDRANT_COLLECTION_WSJ: str = "wsj_data"

    # MarketWatch (personal finance and market data via yfinance proxy)
    KAFKA_TOPIC_MARKETWATCH: str = "marketwatch-data"
    QDRANT_COLLECTION_MARKETWATCH: str = "marketwatch_data"

    # Fox Business (business news and market data via yfinance proxy)
    KAFKA_TOPIC_FOXBUSINESS: str = "foxbusiness-data"
    QDRANT_COLLECTION_FOXBUSINESS: str = "foxbusiness_data"

    # Barron's (premium investment analysis via yfinance proxy)
    KAFKA_TOPIC_BARRONS: str = "barrons-data"
    QDRANT_COLLECTION_BARRONS: str = "barrons_data"

    # Insider Monkey (hedge fund and insider tracking via yfinance proxy)
    KAFKA_TOPIC_INSIDERMONKEY: str = "insidermonkey-data"
    QDRANT_COLLECTION_INSIDERMONKEY: str = "insidermonkey_data"

    # Quiver Quantitative (alternative data via yfinance proxy)
    KAFKA_TOPIC_QUIVERQUANT: str = "quiverquant-data"
    QDRANT_COLLECTION_QUIVERQUANT: str = "quiverquant_data"

    # Dataroma (superinvestor portfolio tracking via yfinance proxy)
    KAFKA_TOPIC_DATAROMA: str = "dataroma-data"
    QDRANT_COLLECTION_DATAROMA: str = "dataroma_data"

    # OpenInsider (SEC Form 4 insider transactions via yfinance proxy)
    KAFKA_TOPIC_OPENINSIDER: str = "openinsider-data"
    QDRANT_COLLECTION_OPENINSIDER: str = "openinsider_data"

    # WhaleWisdom (13F institutional holdings via yfinance proxy)
    KAFKA_TOPIC_WHALEWISDOM: str = "whalewisdom-data"
    QDRANT_COLLECTION_WHALEWISDOM: str = "whalewisdom_data"

    # ETF.com (ETF research and analysis via yfinance proxy)
    KAFKA_TOPIC_ETFCOM: str = "etfcom-data"
    QDRANT_COLLECTION_ETFCOM: str = "etfcom_data"

    # ETFdb (ETF database and screening via yfinance proxy)
    KAFKA_TOPIC_ETFDB: str = "etfdb-data"
    QDRANT_COLLECTION_ETFDB: str = "etfdb_data"

    # Global X ETFs (thematic ETF research via yfinance proxy)
    KAFKA_TOPIC_GLOBALXETF: str = "globalxetf-data"
    QDRANT_COLLECTION_GLOBALXETF: str = "globalxetf_data"

    # ARK Invest (disruptive innovation research via yfinance proxy)
    KAFKA_TOPIC_ARKINVEST: str = "arkinvest-data"
    QDRANT_COLLECTION_ARKINVEST: str = "arkinvest_data"

    # Morningstar ETF (ETF ratings and analysis via yfinance proxy)
    KAFKA_TOPIC_MORNINGSTARETF: str = "morningstaretf-data"
    QDRANT_COLLECTION_MORNINGSTARETF: str = "morningstaretf_data"

    # LLM defaults
    DEFAULT_MODEL: str = os.getenv(
        "LLM_MODEL",
        _get_nested(_yaml_config, "llm", "model", default="gpt-4o-mini")
    )
    DEFAULT_API_BASE: str | None = os.getenv(
        "LLM_API_BASE",
        _get_nested(_yaml_config, "llm", "api_base", default=None)
    )

    # API Server
    API_HOST: str = _get_nested(_yaml_config, "api", "host", default="0.0.0.0")
    API_PORT: int = _get_nested(_yaml_config, "api", "port", default=8000)

    # Observability
    LANGFUSE_ENABLED: bool = _get_nested(_yaml_config, "observability", "langfuse", "enabled", default=False)
    LANGFUSE_PUBLIC_KEY: str | None = os.getenv(
        "LANGFUSE_PUBLIC_KEY",
        _get_nested(_yaml_config, "observability", "langfuse", "public_key", default=None)
    )
    LANGFUSE_SECRET_KEY: str | None = os.getenv(
        "LANGFUSE_SECRET_KEY",
        _get_nested(_yaml_config, "observability", "langfuse", "secret_key", default=None)
    )
    LANGFUSE_HOST: str = _get_nested(
        _yaml_config, "observability", "langfuse", "host", default="https://cloud.langfuse.com"
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # AWS Configuration (QA, STG, PROD environments)
    # ═══════════════════════════════════════════════════════════════════════════

    # AWS Bedrock LLM
    BEDROCK_MODEL: str = os.getenv(
        "BEDROCK_MODEL",
        _get_nested(_yaml_config, "aws", "bedrock", "model", default="anthropic.claude-3-sonnet-20240229-v1:0")
    )
    BEDROCK_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # Amazon MSK (Managed Streaming for Apache Kafka)
    MSK_BOOTSTRAP_SERVERS: str = os.getenv(
        "MSK_BOOTSTRAP_SERVERS",
        _get_nested(_yaml_config, "aws", "msk", "bootstrap_servers", default="")
    )
    MSK_USE_IAM_AUTH: bool = os.getenv(
        "MSK_USE_IAM_AUTH",
        str(_get_nested(_yaml_config, "aws", "msk", "use_iam_auth", default=True))
    ).lower() in ("true", "1", "yes")

    # Amazon OpenSearch
    OPENSEARCH_ENDPOINT: str = os.getenv(
        "OPENSEARCH_ENDPOINT",
        _get_nested(_yaml_config, "aws", "opensearch", "endpoint", default="")
    )
    OPENSEARCH_USE_IAM_AUTH: bool = os.getenv(
        "OPENSEARCH_USE_IAM_AUTH",
        str(_get_nested(_yaml_config, "aws", "opensearch", "use_iam_auth", default=True))
    ).lower() in ("true", "1", "yes")

    # AWS Secrets Manager
    USE_SECRETS_MANAGER: bool = os.getenv(
        "USE_SECRETS_MANAGER",
        str(_get_nested(_yaml_config, "aws", "secrets_manager", "enabled", default=False))
    ).lower() in ("true", "1", "yes") or IS_AWS

    # EKS Cluster
    EKS_CLUSTER_NAME: str = os.getenv(
        "EKS_CLUSTER_NAME",
        _get_nested(_yaml_config, "aws", "eks", "cluster_name", default="")
    )

    # AWS AppConfig (Feature Flags)
    APPCONFIG_APPLICATION_ID: str = os.getenv(
        "APPCONFIG_APPLICATION_ID",
        _get_nested(_yaml_config, "aws", "appconfig", "application_id", default="")
    )
    APPCONFIG_ENVIRONMENT_ID: str = os.getenv(
        "APPCONFIG_ENVIRONMENT_ID",
        _get_nested(_yaml_config, "aws", "appconfig", "environment_id", default="")
    )
    APPCONFIG_PROFILE_ID: str = os.getenv(
        "APPCONFIG_PROFILE_ID",
        _get_nested(_yaml_config, "aws", "appconfig", "profile_id", default="")
    )
    APPCONFIG_POLL_INTERVAL: int = int(os.getenv(
        "APPCONFIG_POLL_INTERVAL",
        _get_nested(_yaml_config, "feature_flags", "appconfig", "poll_interval_seconds", default=60)
    ))

    # ═══════════════════════════════════════════════════════════════════════════
    # Feature Flags Configuration (Unleash for local, AppConfig for AWS)
    # ═══════════════════════════════════════════════════════════════════════════

    UNLEASH_URL: str = os.getenv(
        "UNLEASH_URL",
        _get_nested(_yaml_config, "feature_flags", "unleash", "url", default="http://localhost:4242/api")
    )
    UNLEASH_APP_NAME: str = os.getenv(
        "UNLEASH_APP_NAME",
        _get_nested(_yaml_config, "feature_flags", "unleash", "app_name", default="stock-signal-api")
    )
    UNLEASH_API_TOKEN: str = os.getenv(
        "UNLEASH_API_TOKEN",
        "default:development.unleash-insecure-api-token"
    )
    UNLEASH_REFRESH_INTERVAL: int = int(os.getenv(
        "UNLEASH_REFRESH_INTERVAL",
        _get_nested(_yaml_config, "feature_flags", "unleash", "refresh_interval_seconds", default=15)
    ))

    # Feature Flag Defaults
    FF_SINGLE_STOCK_ANALYSIS: bool = _get_nested(
        _yaml_config, "feature_flags", "defaults", "single_stock_analysis", default=True
    )
    FF_WATCHLIST_ANALYSIS: bool = _get_nested(
        _yaml_config, "feature_flags", "defaults", "watchlist_analysis", default=False
    )
    FF_PREMARKET_ANALYSIS: bool = _get_nested(
        _yaml_config, "feature_flags", "defaults", "premarket_analysis", default=False
    )
    FF_AFTERMARKET_ANALYSIS: bool = _get_nested(
        _yaml_config, "feature_flags", "defaults", "aftermarket_analysis", default=False
    )

    @classmethod
    def get_llm_model(cls) -> str:
        """Get the appropriate LLM model based on environment."""
        if IS_AWS:
            return f"bedrock/{cls.BEDROCK_MODEL}"
        return cls.DEFAULT_MODEL

    @classmethod
    def get_kafka_servers(cls) -> str:
        """Get Kafka bootstrap servers based on environment."""
        if IS_AWS and cls.MSK_BOOTSTRAP_SERVERS:
            return cls.MSK_BOOTSTRAP_SERVERS
        return cls.KAFKA_BOOTSTRAP_SERVERS

    @classmethod
    def get_vector_db_type(cls) -> str:
        """Get vector database type based on environment."""
        if IS_AWS:
            return "opensearch"
        return "qdrant"
