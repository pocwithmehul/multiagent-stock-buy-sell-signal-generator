"""
Orchestrator Agent Module - Multi-Agent Coordination System.

This module implements the orchestrator pattern for coordinating specialized
sub-agents and synthesizing their signals into a final BUY/SELL/HOLD recommendation.
The number of active agents is determined at runtime by Unleash feature flags.

Architecture Overview:
    - Runs all feature-flag-enabled data-gathering agents sequentially
    - Collects signals, confidence scores, and detailed data from each
    - Uses majority voting to determine consensus signal
    - Calls LLM to synthesize reasoning from all data sources
    - Reconciles LLM output with majority vote for final signal

Agent Categories:
    - Technical: TechnicalAnalysisAgent (RSI, MACD, SMA, EMA, Bollinger)
    - Fundamental: SeekingAlpha, Zacks, Morningstar, GuruFocus, etc.
    - News/SEC: NewsAgent, SECFilingAgent
    - Analyst: TipRanks, MarketBeat, Refinitiv
    - Sentiment: SentimentAgent, Reddit, StockTwits
    - Social: XTwitter, Facebook, Instagram
    - Institutional: InsiderMonkey, QuiverQuant, Dataroma, WhaleWisdom, OpenInsider
    - ETF: ETF.com, ETFdb, Global X, ARK Invest, Morningstar ETF
    - Media: CNBC, Bloomberg, WSJ, MarketWatch, Fox Business, Barron's
    - Options: OptionsFlowAgent, Yahoo Finance options analysis

Library Dependencies:
    - json: JSON parsing for LLM responses (https://docs.python.org/3/library/json.html)
    - sys: System functions for stderr output (https://docs.python.org/3/library/sys.html)
    - datetime: Date/time handling (https://docs.python.org/3/library/datetime.html)
    - litellm: Unified LLM API client (https://docs.litellm.ai/)
"""

# json: JSON encoder/decoder for parsing LLM responses
# Reference: https://docs.python.org/3/library/json.html
import json

# sys: System-specific parameters, provides stderr for status messages
# Reference: https://docs.python.org/3/library/sys.html
import sys

# datetime: Core date/time classes
# datetime: Combined date and time class
# timezone: Timezone information (UTC)
# Reference: https://docs.python.org/3/library/datetime.html
from datetime import datetime, timezone

# litellm: Unified interface for multiple LLM providers
# Supports OpenAI, Anthropic, Ollama, Azure, etc.
# Reference: https://docs.litellm.ai/
import litellm

# AgenticAIBase: Abstract base class defining agent lifecycle
# Provides: plan(), perceive(), reason(), act() pattern
from agentic_ai_base import AgenticAIBase
from ml.symbolic_validator import SymbolicValidator
from infrastructure.knowledge_graph import StockKnowledgeGraph
from agents.technical_analysis_agent import TechnicalAnalysisAgent
from agents.news_agent import NewsAgent
from agents.sec_filing_agent import SECFilingAgent
from agents.sentiment_agent import SentimentAgent
from agents.zacks_agent import ZacksAnalysisAgent
from agents.tipranks_agent import TipRanksAgent
from agents.seekingalpha_agent import SeekingAlphaAgent
from agents.insider_institutional_agent import InsiderInstitutionalAgent
from agents.motleyfool_agent import MotleyFoolAgent
from agents.stockstory_agent import StockStoryAgent
from agents.yahoofinance_agent import YahooFinanceAgent
from agents.morningstar_agent import MorningstarAgent
from agents.gurufocus_agent import GuruFocusAgent
from agents.tradingview_agent import TradingViewAgent
from agents.stockrover_agent import StockRoverAgent
from agents.simplywallst_agent import SimplyWallStAgent
from agents.alphaspread_agent import AlphaSpreadAgent
from agents.factset_agent import FactSetAgent
from agents.capitaliq_agent import CapitalIQAgent
from agents.marketbeat_agent import MarketBeatAgent
from agents.refinitiv_agent import RefinitivAgent
from agents.macrotrends_agent import MacrotrendsAgent
from agents.ycharts_agent import YChartsAgent
from agents.koyfin_agent import KoyfinAgent
from agents.valueline_agent import ValueLineAgent
from agents.xtwitter_agent import XTwitterAgent
from agents.facebook_agent import FacebookAgent
from agents.instagram_agent import InstagramAgent
from agents.cnbc_agent import CNBCAgent
from agents.bloomberg_agent import BloombergAgent
from agents.wsj_agent import WSJAgent
from agents.marketwatch_agent import MarketWatchAgent
from agents.foxbusiness_agent import FoxBusinessAgent
from agents.barrons_agent import BarronsAgent
from agents.insidermonkey_agent import InsiderMonkeyAgent
from agents.quiverquant_agent import QuiverQuantAgent
from agents.dataroma_agent import DataromaAgent
from agents.openinsider_agent import OpenInsiderAgent
from agents.whalewisdom_agent import WhaleWisdomAgent
from agents.etfcom_agent import ETFComAgent
from agents.etfdb_agent import ETFDBAgent
from agents.globalxetf_agent import GlobalXETFAgent
from agents.arkinvest_agent import ARKInvestAgent
from agents.morningstaretf_agent import MorningstarETFAgent
from agents.reddit_agent import RedditAgent
from agents.stocktwits_agent import StockTwitsAgent
from agents.options_flow_agent import OptionsFlowAgent
from agents.investor_presentation_agent import InvestorPresentationAgent
from agents.earnings_call_agent import EarningsCallAgent
from infrastructure.feature_flags import is_feature_enabled, FeatureFlag


class OrchestratorAgent(AgenticAIBase):
    """
    Orchestrator that coordinates feature-flag-enabled sub-agents and synthesizes a final signal.

    This is the central coordination agent that:
    1. Executes all specialized agents in sequence
    2. Collects and aggregates their outputs
    3. Uses LLM to synthesize a comprehensive analysis
    4. Applies majority voting for signal reconciliation

    Attributes:
        ticker (str): Stock ticker symbol (uppercase)
        past_days (int): Number of days of historical data to analyze
        model (str): LLM model identifier for litellm
        api_base (str): Optional API base URL for local LLMs
        kafka_enabled (bool): Whether to enable Kafka publishing
        kafka_producer: Kafka producer instance
        qdrant_enabled (bool): Whether to enable Qdrant vector storage
        qdrant_store: Qdrant store instance
        embedder: Sentence transformer for embeddings
        verbose (bool): Include detailed agent summaries in output
        progress_callback: Callback function for progress updates
        agent_outputs (dict): Collected outputs from all agents
    """

    def __init__(self, ticker: str, past_days: int = 365,
                 model: str = "gpt-4o-mini", api_base: str = None,
                 kafka_enabled: bool = False, kafka_producer=None,
                 qdrant_enabled: bool = False, qdrant_store=None,
                 embedder=None, verbose: bool = False,
                 progress_callback=None,
                 earnings_audio_file: str = None):
        """
        Initialize the orchestrator agent.

        Args:
            ticker (str): Stock ticker symbol to analyze
            past_days (int): Days of historical data (default: 365)
            model (str): LLM model for synthesis (default: gpt-4o-mini)
            api_base (str): API base URL for local LLMs (e.g., Ollama)
            kafka_enabled (bool): Enable Kafka publishing
            kafka_producer: Kafka producer instance
            qdrant_enabled (bool): Enable Qdrant vector storage
            qdrant_store: Qdrant store instance
            embedder: Sentence transformer for embeddings
            verbose (bool): Include detailed summaries in output
            progress_callback: Callback(agent_name, current, total) for progress
        """
        # Call parent class constructor
        # super().__init__(): Initialize AgenticAIBase with empty state
        super().__init__()

        # Store configuration parameters
        # str.upper(): Normalize ticker to uppercase for consistency
        self.ticker = ticker.upper()

        # int type: Number of days to analyze
        self.past_days = past_days

        # str type: LLM model identifier for litellm
        # Examples: "gpt-4o-mini", "ollama/llama3", "claude-3-sonnet"
        self.model = model

        # str type: Optional API base for local LLM servers
        # Example: "http://localhost:11434" for Ollama
        self.api_base = api_base

        # Kafka configuration for streaming price data
        self.kafka_enabled = kafka_enabled
        self.kafka_producer = kafka_producer

        # Qdrant configuration for vector storage/RAG
        self.qdrant_enabled = qdrant_enabled
        self.qdrant_store = qdrant_store

        # Sentence transformer for generating embeddings
        self.embedder = embedder
        if self.qdrant_enabled and (self.qdrant_store is None or self.embedder is None):
            self.qdrant_enabled = False
            print("  [Orchestrator] Qdrant disabled: store/embedder not available.", file=sys.stderr)

        # bool type: Include detailed summaries in output
        self.verbose = verbose

        # Optional local audio file path for EarningsCallAgent
        self.earnings_audio_file = earnings_audio_file

        # Neuro-symbolic validator: applies hard rules on top of neural ensemble
        self.symbolic_validator = SymbolicValidator()

        # Knowledge graph: sector / macro context for KG-aware symbolic rules
        # Only instantiated when the KNOWLEDGE_GRAPH feature flag is enabled
        self.knowledge_graph = (
            StockKnowledgeGraph()
            if is_feature_enabled(FeatureFlag.KNOWLEDGE_GRAPH)
            else None
        )

        # Callback function: Signature is (agent_name: str, current: int, total: int)
        # Used by dashboard to show progress bar
        self.progress_callback = progress_callback

        # dict type: Stores outputs from all executed agents
        # Key: agent identifier (e.g., "technical", "news", "sec")
        # Value: Agent output dict with signal, confidence, data
        self.agent_outputs = {}

    @staticmethod
    def _normalize_signal(signal: str) -> str:
        """
        Normalize heterogeneous agent signal labels to standard format.

        Different agents may return signals in various formats:
        - Technical agents: BULLISH, BEARISH, NEUTRAL
        - Fundamental agents: BUY, SELL, HOLD
        - Sentiment agents: Various formats

        This method normalizes all to: BUY, SELL, or HOLD

        Args:
            signal (str): Raw signal string from agent

        Returns:
            str: Normalized signal (BUY, SELL, or HOLD)
        """
        # Handle None and normalize to uppercase
        # str.upper(): Convert to uppercase
        # str.strip(): Remove whitespace
        # or operator: Handle None case - returns "" if signal is None
        sig = (signal or "").upper().strip()

        # Map BULLISH variants to BUY
        # 'in' operator: Check membership in tuple
        if sig in ("BUY", "BULLISH"):
            return "BUY"

        # Map BEARISH variants to SELL
        if sig in ("SELL", "BEARISH"):
            return "SELL"

        # Default to HOLD for NEUTRAL, unknown, or empty signals
        return "HOLD"

    def _compute_majority_vote(self, outputs: dict) -> dict:
        """
        Compute majority signal from all agent outputs using vote counting.

        Implements democratic voting where each agent gets one vote.
        Also tracks average confidence for each signal type.

        Args:
            outputs (dict): Dictionary of agent_key -> agent_output

        Returns:
            dict: Voting results containing:
                - majority_signal: The winning signal (BUY/SELL/HOLD)
                - majority_vote_ratio: Fraction of agents voting for majority
                - majority_avg_confidence: Average confidence of majority voters
                - vote_counts: Dict with count for each signal type
                - total_votes: Total number of valid votes
        """
        # Initialize vote counters for each signal type
        # dict literal: Create mapping of signal to count
        vote_counts = {"BUY": 0, "HOLD": 0, "SELL": 0}

        # Track confidence sums for computing averages
        # float type: Accumulate confidence values
        conf_sums = {"BUY": 0.0, "HOLD": 0.0, "SELL": 0.0}

        # Counter for total valid votes
        total_votes = 0

        # Iterate through all agent outputs
        # dict.values(): Get all values (agent outputs)
        for out in outputs.values():
            # Skip None or empty outputs
            if not out:
                continue

            # Normalize the signal to BUY/SELL/HOLD
            signal = self._normalize_signal(out.get("signal"))

            # Extract confidence, default to 0.0 if missing
            # float(): Convert to float type
            confidence = float(out.get("confidence") or 0.0)

            # Increment vote count for this signal
            vote_counts[signal] += 1

            # Add confidence to running sum
            conf_sums[signal] += confidence

            # Increment total votes
            total_votes += 1

        # Handle case with no valid votes
        if total_votes == 0:
            return {
                "majority_signal": "HOLD",
                "majority_vote_ratio": 0.0,
                "majority_avg_confidence": 0.0,
                "vote_counts": vote_counts,
                "total_votes": 0,
            }

        # Find signal with most votes
        # max() with key function: Find key with highest value
        # dict.get: Returns value for key (used as comparison function)
        majority_signal = max(vote_counts, key=vote_counts.get)

        # Get count for winning signal
        majority_votes = vote_counts[majority_signal]

        # Calculate ratio of majority votes to total
        majority_ratio = majority_votes / total_votes

        # Calculate average confidence of majority voters
        # Conditional expression: Avoid division by zero
        majority_avg_conf = conf_sums[majority_signal] / majority_votes if majority_votes > 0 else 0.0

        return {
            "majority_signal": majority_signal,
            "majority_vote_ratio": majority_ratio,
            "majority_avg_confidence": majority_avg_conf,
            "vote_counts": vote_counts,
            "total_votes": total_votes,
        }

    def _reconcile_with_majority(self, reasoning: dict, majority: dict) -> tuple[str, float, str]:
        """
        Reconcile LLM final signal with majority vote from agents.

        This implements a hybrid decision-making approach that combines
        the LLM's synthesis capabilities with democratic agent voting.

        Decision Rules:
        1. If LLM and majority agree -> Use aligned signal (highest confidence)
        2. If majority has >= 50% consensus and disagrees with LLM -> Override with majority
        3. Otherwise -> Trust the LLM's synthesis

        Args:
            reasoning (dict): LLM reasoning output with 'signal' and 'confidence'
            majority (dict): Majority vote results from _compute_majority_vote()

        Returns:
            tuple[str, float, str]: (final_signal, final_confidence, decision_source)
                - decision_source is one of: "llm_aligned_with_majority",
                  "majority_override", "llm_override"
        """
        # Extract and normalize LLM signal
        llm_signal = self._normalize_signal(reasoning.get("signal"))

        # Extract LLM confidence, default to 0.0
        # float(): Ensure float type
        llm_conf = float(reasoning.get("confidence") or 0.0)

        # Extract majority voting results
        majority_signal = majority["majority_signal"]
        majority_ratio = majority["majority_vote_ratio"]
        majority_conf = float(majority["majority_avg_confidence"] or 0.0)

        # Case 1: LLM and majority agree
        # Use the aligned signal with the higher confidence
        if llm_signal == majority_signal:
            # max(): Take higher confidence between LLM and majority average
            return llm_signal, max(llm_conf, majority_conf), "llm_aligned_with_majority"

        # Case 2: Majority has strong consensus (>= 50%) but disagrees with LLM
        # Democratic override - trust the collective agent wisdom
        if majority_ratio >= 0.50:
            return majority_signal, max(majority_conf, majority_ratio), "majority_override"

        # Case 3: No strong majority consensus
        # Trust the LLM's synthesis of all data
        return llm_signal, llm_conf, "llm_override"

    def _debug_log_reconciliation(self, reasoning: dict, majority: dict,
                                  final_signal: str, final_confidence: float,
                                  decision_source: str):
        """
        Log detailed debug information about signal reconciliation decision.

        Outputs comprehensive context to stderr if DEBUG mode is enabled.
        Useful for understanding why a particular signal was chosen.

        Args:
            reasoning (dict): LLM reasoning output
            majority (dict): Majority vote results
            final_signal (str): The reconciled final signal
            final_confidence (float): The reconciled confidence
            decision_source (str): Which source won (llm or majority)
        """
        # Extract LLM values for comparison logging
        llm_signal = self._normalize_signal(reasoning.get("signal"))
        llm_conf = float(reasoning.get("confidence") or 0.0)

        # Build comprehensive rationale dictionary
        # dict literal: Create debug output structure
        rationale = {
            "decision_source": decision_source,
            "final_signal": final_signal,
            "final_confidence": round(final_confidence, 4),
            "llm_signal": llm_signal,
            "llm_confidence": round(llm_conf, 4),
            "majority_signal": majority.get("majority_signal"),
            "majority_vote_ratio": round(float(majority.get("majority_vote_ratio") or 0.0), 4),
            "majority_avg_confidence": round(float(majority.get("majority_avg_confidence") or 0.0), 4),
            "majority_vote_counts": majority.get("vote_counts", {}),
            # Human-readable explanation of the decision rules
            "rule": (
                "If LLM and majority agree -> keep aligned signal; "
                "if disagreement and majority vote ratio >= 0.50 -> majority override; "
                "otherwise keep LLM."
            ),
        }

        # Log via inherited debug_log() method (outputs to stderr if DEBUG=true)
        # debug_log(): From AgenticAIBase
        self.debug_log("Signal Reconciliation Decision", rationale, agent_name="OrchestratorAgent")

    def _resolve_current_price(self, outputs: dict) -> float | None:
        """
        Resolve current price from agent outputs, falling back to yfinance.

        Tries in order:
          1. Technical agent output (most reliable)
          2. Other agent outputs that commonly include current_price
          3. Direct yfinance call as last resort

        This prevents current_price from being null when the technical
        agent is disabled via feature flag.
        """
        # 1. Technical agent — preferred source
        tech = outputs.get("technical", {})
        if tech:
            price = tech.get("data", {}).get("current_price")
            if price:
                return float(price)

        # 2. Other agents that surface current_price in their data
        fallback_paths = [
            ("yahoofinance", "options_data"),
            ("morningstar", "valuation"),
            ("marketbeat", "price_target"),
            ("tradingview", "price_data"),
            ("marketwatch", "quote_data"),
            ("simplywallst", "valuation"),
            ("alphaspread", "valuation"),
        ]
        for agent_key, sub_key in fallback_paths:
            agent_out = outputs.get(agent_key, {})
            if agent_out:
                price = agent_out.get("data", {}).get(sub_key, {}).get("current_price")
                if price:
                    return float(price)

        # 3. Direct yfinance call as last resort
        try:
            import yfinance as yf
            info = yf.Ticker(self.ticker).info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price:
                return float(price)
        except Exception:
            pass

        return None

    # ══════════════════════════════════════════════════════════════════
    # Sub-Agent Runner Methods
    # ══════════════════════════════════════════════════════════════════
    #
    # Each _run_*_agent() method follows the same pattern:
    #   1. Print status message to stderr
    #   2. Instantiate the specialized agent with config parameters
    #   3. Call agent.execute() to run its lifecycle
    #   4. Return agent.get_output() or None on failure
    #
    # All methods are wrapped in try/except to allow graceful degradation
    # if individual agents fail. The orchestrator continues with remaining
    # agents rather than failing completely.
    #
    # ══════════════════════════════════════════════════════════════════

    def _run_technical_agent(self) -> dict | None:
        """
        Run the TechnicalAnalysisAgent for price-based indicators.

        Computes: RSI, MACD, SMA, EMA, Bollinger Bands
        Data source: Yahoo Finance (via yfinance library)

        Returns:
            dict | None: Agent output with signal/confidence or None on failure
        """
        try:
            print(f"  [Orchestrator] Running TechnicalAnalysisAgent...", file=sys.stderr)
            agent = TechnicalAnalysisAgent(
                ticker=self.ticker,
                past_days=self.past_days,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] TechnicalAnalysisAgent failed: {e}", file=sys.stderr)
            return None

    def _run_news_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running NewsAgent...", file=sys.stderr)
            agent = NewsAgent(
                ticker=self.ticker,
                past_days=self.past_days,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] NewsAgent failed: {e}", file=sys.stderr)
            return None

    def _run_sec_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running SECFilingAgent...", file=sys.stderr)
            agent = SECFilingAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] SECFilingAgent failed: {e}", file=sys.stderr)
            return None

    def _run_zacks_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running ZacksAnalysisAgent...", file=sys.stderr)
            agent = ZacksAnalysisAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] ZacksAnalysisAgent failed: {e}", file=sys.stderr)
            return None

    def _run_tipranks_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running TipRanksAgent...", file=sys.stderr)
            agent = TipRanksAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] TipRanksAgent failed: {e}", file=sys.stderr)
            return None

    def _run_seekingalpha_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running SeekingAlphaAgent...", file=sys.stderr)
            agent = SeekingAlphaAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] SeekingAlphaAgent failed: {e}", file=sys.stderr)
            return None

    def _run_insider_institutional_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running InsiderInstitutionalAgent...", file=sys.stderr)
            agent = InsiderInstitutionalAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] InsiderInstitutionalAgent failed: {e}", file=sys.stderr)
            return None

    def _run_motleyfool_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MotleyFoolAgent...", file=sys.stderr)
            agent = MotleyFoolAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MotleyFoolAgent failed: {e}", file=sys.stderr)
            return None

    def _run_stockstory_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running StockStoryAgent...", file=sys.stderr)
            agent = StockStoryAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] StockStoryAgent failed: {e}", file=sys.stderr)
            return None

    def _run_yahoofinance_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running YahooFinanceAgent...", file=sys.stderr)
            agent = YahooFinanceAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] YahooFinanceAgent failed: {e}", file=sys.stderr)
            return None

    def _run_morningstar_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MorningstarAgent...", file=sys.stderr)
            agent = MorningstarAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MorningstarAgent failed: {e}", file=sys.stderr)
            return None

    def _run_gurufocus_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running GuruFocusAgent...", file=sys.stderr)
            agent = GuruFocusAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] GuruFocusAgent failed: {e}", file=sys.stderr)
            return None

    def _run_tradingview_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running TradingViewAgent...", file=sys.stderr)
            agent = TradingViewAgent(
                ticker=self.ticker,
                past_days=self.past_days,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] TradingViewAgent failed: {e}", file=sys.stderr)
            return None

    def _run_stockrover_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running StockRoverAgent...", file=sys.stderr)
            agent = StockRoverAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] StockRoverAgent failed: {e}", file=sys.stderr)
            return None

    def _run_simplywallst_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running SimplyWallStAgent...", file=sys.stderr)
            agent = SimplyWallStAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] SimplyWallStAgent failed: {e}", file=sys.stderr)
            return None

    def _run_alphaspread_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running AlphaSpreadAgent...", file=sys.stderr)
            agent = AlphaSpreadAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] AlphaSpreadAgent failed: {e}", file=sys.stderr)
            return None

    def _run_factset_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running FactSetAgent...", file=sys.stderr)
            agent = FactSetAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] FactSetAgent failed: {e}", file=sys.stderr)
            return None

    def _run_capitaliq_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running CapitalIQAgent...", file=sys.stderr)
            agent = CapitalIQAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] CapitalIQAgent failed: {e}", file=sys.stderr)
            return None

    def _run_marketbeat_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MarketBeatAgent...", file=sys.stderr)
            agent = MarketBeatAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MarketBeatAgent failed: {e}", file=sys.stderr)
            return None

    def _run_refinitiv_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running RefinitivAgent...", file=sys.stderr)
            agent = RefinitivAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] RefinitivAgent failed: {e}", file=sys.stderr)
            return None

    def _run_macrotrends_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MacrotrendsAgent...", file=sys.stderr)
            agent = MacrotrendsAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MacrotrendsAgent failed: {e}", file=sys.stderr)
            return None

    def _run_ycharts_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running YChartsAgent...", file=sys.stderr)
            agent = YChartsAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] YChartsAgent failed: {e}", file=sys.stderr)
            return None

    def _run_koyfin_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running KoyfinAgent...", file=sys.stderr)
            agent = KoyfinAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] KoyfinAgent failed: {e}", file=sys.stderr)
            return None

    def _run_valueline_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running ValueLineAgent...", file=sys.stderr)
            agent = ValueLineAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] ValueLineAgent failed: {e}", file=sys.stderr)
            return None

    def _run_xtwitter_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running XTwitterAgent...", file=sys.stderr)
            agent = XTwitterAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] XTwitterAgent failed: {e}", file=sys.stderr)
            return None

    def _run_facebook_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running FacebookAgent...", file=sys.stderr)
            agent = FacebookAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] FacebookAgent failed: {e}", file=sys.stderr)
            return None

    def _run_instagram_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running InstagramAgent...", file=sys.stderr)
            agent = InstagramAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] InstagramAgent failed: {e}", file=sys.stderr)
            return None

    def _run_cnbc_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running CNBCAgent...", file=sys.stderr)
            agent = CNBCAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] CNBCAgent failed: {e}", file=sys.stderr)
            return None

    def _run_bloomberg_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running BloombergAgent...", file=sys.stderr)
            agent = BloombergAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] BloombergAgent failed: {e}", file=sys.stderr)
            return None

    def _run_wsj_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running WSJAgent...", file=sys.stderr)
            agent = WSJAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] WSJAgent failed: {e}", file=sys.stderr)
            return None

    def _run_marketwatch_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MarketWatchAgent...", file=sys.stderr)
            agent = MarketWatchAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MarketWatchAgent failed: {e}", file=sys.stderr)
            return None

    def _run_foxbusiness_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running FoxBusinessAgent...", file=sys.stderr)
            agent = FoxBusinessAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] FoxBusinessAgent failed: {e}", file=sys.stderr)
            return None

    def _run_barrons_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running BarronsAgent...", file=sys.stderr)
            agent = BarronsAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] BarronsAgent failed: {e}", file=sys.stderr)
            return None

    def _run_insidermonkey_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running InsiderMonkeyAgent...", file=sys.stderr)
            agent = InsiderMonkeyAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] InsiderMonkeyAgent failed: {e}", file=sys.stderr)
            return None

    def _run_quiverquant_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running QuiverQuantAgent...", file=sys.stderr)
            agent = QuiverQuantAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] QuiverQuantAgent failed: {e}", file=sys.stderr)
            return None

    def _run_dataroma_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running DataromaAgent...", file=sys.stderr)
            agent = DataromaAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] DataromaAgent failed: {e}", file=sys.stderr)
            return None

    def _run_openinsider_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running OpenInsiderAgent...", file=sys.stderr)
            agent = OpenInsiderAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] OpenInsiderAgent failed: {e}", file=sys.stderr)
            return None

    def _run_whalewisdom_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running WhaleWisdomAgent...", file=sys.stderr)
            agent = WhaleWisdomAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] WhaleWisdomAgent failed: {e}", file=sys.stderr)
            return None

    def _run_etfcom_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running ETFComAgent...", file=sys.stderr)
            agent = ETFComAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] ETFComAgent failed: {e}", file=sys.stderr)
            return None

    def _run_etfdb_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running ETFDBAgent...", file=sys.stderr)
            agent = ETFDBAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] ETFDBAgent failed: {e}", file=sys.stderr)
            return None

    def _run_globalxetf_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running GlobalXETFAgent...", file=sys.stderr)
            agent = GlobalXETFAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] GlobalXETFAgent failed: {e}", file=sys.stderr)
            return None

    def _run_arkinvest_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running ARKInvestAgent...", file=sys.stderr)
            agent = ARKInvestAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] ARKInvestAgent failed: {e}", file=sys.stderr)
            return None

    def _run_morningstaretf_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running MorningstarETFAgent...", file=sys.stderr)
            agent = MorningstarETFAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] MorningstarETFAgent failed: {e}", file=sys.stderr)
            return None

    def _run_reddit_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running RedditAgent...", file=sys.stderr)
            agent = RedditAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] RedditAgent failed: {e}", file=sys.stderr)
            return None

    def _run_stocktwits_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running StockTwitsAgent...", file=sys.stderr)
            agent = StockTwitsAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] StockTwitsAgent failed: {e}", file=sys.stderr)
            return None

    def _run_options_flow_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running OptionsFlowAgent...", file=sys.stderr)
            agent = OptionsFlowAgent(
                ticker=self.ticker,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] OptionsFlowAgent failed: {e}", file=sys.stderr)
            return None

    def _run_investor_presentation_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running InvestorPresentationAgent...", file=sys.stderr)
            agent = InvestorPresentationAgent(
                ticker=self.ticker,
                model=self.model,
                api_base=self.api_base,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] InvestorPresentationAgent failed: {e}", file=sys.stderr)
            return None

    def _run_earnings_call_agent(self) -> dict | None:
        try:
            print(f"  [Orchestrator] Running EarningsCallAgent...", file=sys.stderr)
            agent = EarningsCallAgent(
                ticker=self.ticker,
                model=self.model,
                api_base=self.api_base,
                kafka_producer=self.kafka_producer,
                kafka_enabled=self.kafka_enabled,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
                audio_file_path=self.earnings_audio_file,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] EarningsCallAgent failed: {e}", file=sys.stderr)
            return None

    def _run_sentiment_agent(self, news_texts: list[str],
                              filing_texts: list[str]) -> dict | None:
        try:
            print(f"  [Orchestrator] Running SentimentAgent...", file=sys.stderr)
            agent = SentimentAgent(
                ticker=self.ticker,
                news_texts=news_texts,
                filing_texts=filing_texts,
                model=self.model,
                api_base=self.api_base,
                qdrant_store=self.qdrant_store,
                qdrant_enabled=self.qdrant_enabled,
                embedder=self.embedder,
            )
            agent.execute()
            return agent.get_output()
        except Exception as e:
            print(f"  [Orchestrator] SentimentAgent failed: {e}", file=sys.stderr)
            return None

    # ══════════════════════════════════════════════════════════════════
    # Agentic Lifecycle Methods
    # ══════════════════════════════════════════════════════════════════
    #
    # The orchestrator follows the standard agentic lifecycle:
    #   PLAN -> PERCEIVE -> REASON -> ACT
    #
    # PLAN: Define the execution steps
    # PERCEIVE: Run all feature-flag-enabled sub-agents and collect their outputs
    # REASON: Build LLM prompt and synthesize multi-source data
    # ACT: Reconcile with majority vote and produce final output
    #
    # ══════════════════════════════════════════════════════════════════

    def plan(self):
        """
        Define the execution plan for multi-agent analysis.

        Lists all feature-flag-enabled agents to be executed plus final synthesis step.
        This plan is stored in self._state["plan"] for lifecycle tracking.
        """
        # Store ordered list of execution steps
        # list literal: Create list of step descriptions
        self._state["plan"] = [
            "Run TechnicalAnalysisAgent",
            "Run NewsAgent",
            "Run SECFilingAgent",
            "Run ZacksAnalysisAgent",
            "Run TipRanksAgent",
            "Run SeekingAlphaAgent",
            "Run InsiderInstitutionalAgent",
            "Run MotleyFoolAgent",
            "Run StockStoryAgent",
            "Run YahooFinanceAgent",
            "Run MorningstarAgent",
            "Run GuruFocusAgent",
            "Run TradingViewAgent",
            "Run StockRoverAgent",
            "Run SimplyWallStAgent",
            "Run AlphaSpreadAgent",
            "Run FactSetAgent",
            "Run CapitalIQAgent",
            "Run MarketBeatAgent",
            "Run RefinitivAgent",
            "Run MacrotrendsAgent",
            "Run YChartsAgent",
            "Run KoyfinAgent",
            "Run ValueLineAgent",
            "Run XTwitterAgent",
            "Run FacebookAgent",
            "Run InstagramAgent",
            "Run CNBCAgent",
            "Run BloombergAgent",
            "Run WSJAgent",
            "Run MarketWatchAgent",
            "Run FoxBusinessAgent",
            "Run BarronsAgent",
            "Run InsiderMonkeyAgent",
            "Run QuiverQuantAgent",
            "Run DataromaAgent",
            "Run OpenInsiderAgent",
            "Run WhaleWisdomAgent",
            "Run ETFComAgent",
            "Run ETFDBAgent",
            "Run GlobalXETFAgent",
            "Run ARKInvestAgent",
            "Run MorningstarETFAgent",
            "Run SentimentAgent with collected texts",
            "Synthesize final signal via LLM",
        ]

    def _report_progress(self, agent_name: str, current: int, total: int):
        """
        Report progress to callback if available.

        Used by dashboard to update progress bar during agent execution.

        Args:
            agent_name (str): Display name of current agent
            current (int): Current agent number (1-indexed)
            total (int): Total number of agents to run
        """
        # Check if callback was provided during initialization
        if self.progress_callback:
            # Invoke callback with progress info
            # Callback signature: (agent_name: str, current: int, total: int)
            self.progress_callback(agent_name, current, total)

    def perceive(self):
        """
        Execute all sub-agents and collect their outputs.

        This is the data gathering phase of the orchestrator lifecycle:
        1. Runs all 46+ specialized agents sequentially
        2. Collects outputs in self.agent_outputs dict
        3. Extracts texts from news/SEC for sentiment analysis
        4. Runs sentiment agent on collected texts
        5. Stores all outputs in self._state["data"]

        Each agent runs independently - failures are logged but don't
        stop execution of remaining agents (graceful degradation).
        """
        # ── Define Agent Registry ──────────────────────────────────────
        # List of tuples: (display_name, key, runner_method)
        # display_name: Human-readable name for progress updates
        # key: Dictionary key for storing output
        # runner_method: Method to execute the agent
        # list of tuples: Registry of all agents to run
        agents = [
            ("Technical Analysis", "technical", self._run_technical_agent),
            ("News", "news", self._run_news_agent),
            ("SEC Filings", "sec", self._run_sec_agent),
            ("Zacks", "zacks", self._run_zacks_agent),
            ("TipRanks", "tipranks", self._run_tipranks_agent),
            ("Seeking Alpha", "seekingalpha", self._run_seekingalpha_agent),
            ("Insider Trading", "insider", self._run_insider_institutional_agent),
            ("Motley Fool", "motleyfool", self._run_motleyfool_agent),
            ("Stock Story", "stockstory", self._run_stockstory_agent),
            ("Yahoo Finance", "yahoofinance", self._run_yahoofinance_agent),
            ("Morningstar", "morningstar", self._run_morningstar_agent),
            ("GuruFocus", "gurufocus", self._run_gurufocus_agent),
            ("TradingView", "tradingview", self._run_tradingview_agent),
            ("Stock Rover", "stockrover", self._run_stockrover_agent),
            ("Simply Wall St", "simplywallst", self._run_simplywallst_agent),
            ("Alpha Spread", "alphaspread", self._run_alphaspread_agent),
            ("FactSet", "factset", self._run_factset_agent),
            ("Capital IQ", "capitaliq", self._run_capitaliq_agent),
            ("MarketBeat", "marketbeat", self._run_marketbeat_agent),
            ("Refinitiv", "refinitiv", self._run_refinitiv_agent),
            ("Macrotrends", "macrotrends", self._run_macrotrends_agent),
            ("YCharts", "ycharts", self._run_ycharts_agent),
            ("Koyfin", "koyfin", self._run_koyfin_agent),
            ("Value Line", "valueline", self._run_valueline_agent),
            ("X/Twitter", "xtwitter", self._run_xtwitter_agent),
            ("Facebook", "facebook", self._run_facebook_agent),
            ("Instagram", "instagram", self._run_instagram_agent),
            ("CNBC", "cnbc", self._run_cnbc_agent),
            ("Bloomberg", "bloomberg", self._run_bloomberg_agent),
            ("Wall Street Journal", "wsj", self._run_wsj_agent),
            ("MarketWatch", "marketwatch", self._run_marketwatch_agent),
            ("Fox Business", "foxbusiness", self._run_foxbusiness_agent),
            ("Barron's", "barrons", self._run_barrons_agent),
            ("Insider Monkey", "insidermonkey", self._run_insidermonkey_agent),
            ("Quiver Quant", "quiverquant", self._run_quiverquant_agent),
            ("Dataroma", "dataroma", self._run_dataroma_agent),
            ("OpenInsider", "openinsider", self._run_openinsider_agent),
            ("WhaleWisdom", "whalewisdom", self._run_whalewisdom_agent),
            ("ETF.com", "etfcom", self._run_etfcom_agent),
            ("ETFDB", "etfdb", self._run_etfdb_agent),
            ("Global X ETF", "globalxetf", self._run_globalxetf_agent),
            ("ARK Invest", "arkinvest", self._run_arkinvest_agent),
            ("Morningstar ETF", "morningstaretf", self._run_morningstaretf_agent),
            ("Reddit", "reddit", self._run_reddit_agent),
            ("StockTwits", "stocktwits", self._run_stocktwits_agent),
            ("Options Flow", "options_flow", self._run_options_flow_agent),
            ("Investor Presentations", "investor_presentation", self._run_investor_presentation_agent),
            ("Earnings Call", "earnings_call", self._run_earnings_call_agent),
        ]

        # Filter agents list based on feature flags before computing total.
        # This ensures the progress bar reflects only the agents that will run.
        active_agents = [
            (display_name, key, runner)
            for display_name, key, runner in agents
            if is_feature_enabled(FeatureFlag(f"agent_{key}"), default=True)
        ]

        skipped = len(agents) - len(active_agents)
        if skipped:
            print(f"[feature-flag] Skipping {skipped} agent(s) (disabled via feature flags)", file=sys.stderr)

        sentiment_enabled = is_feature_enabled(FeatureFlag.AGENT_SENTIMENT, default=True)

        # +1 accounts for sentiment agent if it is enabled
        total_agents = len(active_agents) + (1 if sentiment_enabled else 0)

        # ── Execute All Data-Gathering Agents ──────────────────────────
        # Track news and SEC outputs separately for sentiment analysis
        news_output = None
        sec_output = None

        # Iterate through only the enabled agents
        for i, (display_name, key, runner) in enumerate(active_agents):
            # Report progress to callback (for dashboard progress bar)
            # i + 1: Convert 0-indexed to 1-indexed for display
            self._report_progress(display_name, i + 1, total_agents)

            # Execute agent via its runner method
            # Each runner returns dict on success, None on failure
            output = runner()

            # Store output if agent succeeded
            if output:
                # Store in agent_outputs dict with key
                self.agent_outputs[key] = output

                # Special handling: Track news and SEC for sentiment
                # These outputs provide text for sentiment analysis
                if key == "news":
                    news_output = output
                elif key == "sec":
                    sec_output = output

        # ── Prepare Texts for Sentiment Analysis ───────────────────────
        # Extract news headlines for sentiment scoring
        # list type: Collection of headline strings
        news_texts = []
        if news_output:
            # Navigate nested dict structure to get articles
            # dict.get(): Safe access with default empty dict/list
            articles = news_output.get("data", {}).get("articles", [])
            # List comprehension: Extract titles from articles
            news_texts = [a.get("title", "") for a in articles if a.get("title")]

        # Extract SEC filing excerpts for sentiment scoring
        filing_texts = []
        if sec_output:
            filings = sec_output.get("data", {}).get("filings", [])
            # List comprehension: Extract excerpts from filings
            filing_texts = [f.get("excerpt", "") for f in filings if f.get("excerpt")]

        # ── Run Sentiment Agent on Collected Texts ─────────────────────
        # Report final agent in progress
        self._report_progress("Sentiment Analysis", total_agents, total_agents)

        if sentiment_enabled:
            # Execute sentiment agent with collected news and filing texts
            sentiment_output = self._run_sentiment_agent(news_texts, filing_texts)

            # Store sentiment output if successful
            if sentiment_output:
                self.agent_outputs["sentiment"] = sentiment_output
        else:
            print("[feature-flag] Skipping Sentiment Analysis (agent_sentiment disabled)", file=sys.stderr)

        # ── Store All Outputs in State ─────────────────────────────────
        # Store collected outputs in state for reason() phase
        self._state["data"]["agent_outputs"] = self.agent_outputs

    def reason(self):
        """
        Synthesize multi-agent data using LLM.

        This is the analysis phase of the orchestrator lifecycle:
        1. Builds comprehensive prompt from all agent outputs
        2. Formats data into human-readable markdown sections
        3. Calls LLM (via litellm) to synthesize final recommendation
        4. Parses JSON response into reasoning dict

        The LLM is asked to consider all active data sources and produce:
        - Signal (BUY/SELL/HOLD)
        - Confidence (0.0-1.0)
        - Target price
        - Upside/downside percentages
        - Stop loss
        - Sentiment score
        - Reasoning summary
        """
        # Retrieve collected agent outputs
        # dict.get(): Safe access with default empty dict
        outputs = self._state["data"].get("agent_outputs", {})

        # ── Build LLM Prompt Sections ──────────────────────────────────
        # Each section formats one agent's output as markdown
        # list type: Collect formatted sections
        sections = []

        # Technical analysis
        tech = outputs.get("technical", {})
        if tech:
            tech_data = tech.get("data", {})
            indicators = tech_data.get("indicators", {})
            sections.append(f"""## Technical Analysis
- Signal: {tech.get('signal', 'N/A')}
- Confidence: {tech.get('confidence', 0)}
- Current Price: ${tech_data.get('current_price', 'N/A')}
- RSI: {indicators.get('rsi', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')} (signal: {indicators.get('macd_signal', 'N/A')}, hist: {indicators.get('macd_histogram', 'N/A')})
- SMA-20: {indicators.get('sma_20', 'N/A')}, SMA-50: {indicators.get('sma_50', 'N/A')}
- Bollinger: upper={indicators.get('bollinger_upper', 'N/A')}, mid={indicators.get('bollinger_middle', 'N/A')}, lower={indicators.get('bollinger_lower', 'N/A')}
- Votes: {tech_data.get('votes', {})}""")

        # News
        news = outputs.get("news", {})
        if news:
            headlines = news.get("data", {}).get("headlines", [])
            headline_str = "\n".join(f"- {h}" for h in headlines[:10]) if headlines else "- No news available"
            sections.append(f"""## Recent News
{headline_str}""")

        # SEC filings
        sec = outputs.get("sec", {})
        if sec:
            filings = sec.get("data", {}).get("filings", [])
            filing_str = "\n".join(
                f"- {f['form_type']} ({f['filing_date']}): {f.get('excerpt', '')[:200]}"
                for f in filings
            ) if filings else "- No filings available"
            sections.append(f"""## SEC Filings
{filing_str}""")

        # Zacks analysis
        zacks = outputs.get("zacks", {})
        if zacks:
            zacks_data = zacks.get("data", {})
            style_scores = zacks_data.get("style_scores", {})
            style_str = ", ".join(f"{k}={v}" for k, v in style_scores.items()) if style_scores else "N/A"
            target = zacks_data.get("target_price")
            target_str = f"${target}" if target is not None else "N/A"
            sections.append(f"""## Zacks Analysis
- Signal: {zacks.get('signal', 'N/A')}
- Confidence: {zacks.get('confidence', 0)}
- Zacks Rank: {zacks_data.get('zacks_rank', 'N/A')} ({zacks_data.get('rank_label', '')})
- Style Scores: {style_str}
- Industry Rank: {zacks_data.get('industry_rank', 'N/A')}
- Analyst Target Price: {target_str}""")

        # Analyst Consensus (TipRanks)
        tipranks = outputs.get("tipranks", {})
        if tipranks:
            tr_data = tipranks.get("data", {})
            consensus = tr_data.get("consensus", {})
            consensus_str = (
                f"Strong Buy={consensus.get('strong_buy', 0)}, "
                f"Buy={consensus.get('buy', 0)}, "
                f"Hold={consensus.get('hold', 0)}, "
                f"Sell={consensus.get('sell', 0)}, "
                f"Strong Sell={consensus.get('strong_sell', 0)}"
            ) if consensus else "N/A"
            rec_mean = tr_data.get("recommendation_mean")
            rec_key = tr_data.get("recommendation_key", "")
            rec_str = f"{rec_mean} ({rec_key})" if rec_mean else "N/A"
            tr_targets = tr_data.get("price_targets", {})
            tr_target_str = (
                f"High=${tr_targets.get('high', 'N/A')}, "
                f"Low=${tr_targets.get('low', 'N/A')}, "
                f"Mean=${tr_targets.get('mean', 'N/A')}, "
                f"Median=${tr_targets.get('median', 'N/A')}"
            ) if tr_targets else "N/A"
            recent = tr_data.get("recent_actions", [])
            recent_str = "\n".join(
                f"- {a.get('firm', '')}: {a.get('action', '')} → {a.get('to_grade', '')} ({a.get('date', '')})"
                for a in recent[:5]
            ) if recent else "- No recent actions"
            sections.append(f"""## Analyst Consensus (TipRanks)
- Signal: {tipranks.get('signal', 'N/A')}
- Confidence: {tipranks.get('confidence', 0)}
- Recommendation Mean: {rec_str}
- Consensus: {consensus_str}
- Price Targets: {tr_target_str}
- Recent Actions:
{recent_str}""")

        # Fundamental Analysis (SeekingAlpha)
        seekingalpha = outputs.get("seekingalpha", {})
        if seekingalpha:
            sa_data = seekingalpha.get("data", {})
            sa_ee = sa_data.get("earnings_estimates", {})
            sa_history = sa_data.get("earnings_history", [])
            sa_eps_trend = sa_data.get("eps_trend", {})
            sa_valuation = sa_data.get("valuation", {})

            ee_avg = sa_ee.get("avg")
            ee_growth = sa_ee.get("growth")
            ee_str = f"Avg EPS={ee_avg}" if ee_avg is not None else "Avg EPS=N/A"
            ee_growth_str = f"{ee_growth:.1%}" if ee_growth is not None else "N/A"

            history_str = "\n".join(
                f"  - {h.get('quarter', 'N/A')}: actual={h.get('eps_actual', 'N/A')}, "
                f"est={h.get('eps_estimate', 'N/A')}, surprise={h.get('surprise_percent', 'N/A')}%"
                for h in sa_history
            ) if sa_history else "  - No earnings history"

            eps_current = sa_eps_trend.get("current")
            eps_30d = sa_eps_trend.get("30days_ago")
            if eps_current is not None and eps_30d is not None:
                if eps_current > eps_30d:
                    revision_dir = "Upward"
                elif eps_current < eps_30d:
                    revision_dir = "Downward"
                else:
                    revision_dir = "Flat"
                revision_str = f"{revision_dir} (current={eps_current}, 30d ago={eps_30d})"
            else:
                revision_str = "N/A"

            trailing_pe = sa_valuation.get("trailing_pe")
            forward_pe = sa_valuation.get("forward_pe")
            ptb = sa_valuation.get("price_to_book")
            div_yield = sa_valuation.get("dividend_yield")
            trailing_pe_str = f"{trailing_pe:.1f}" if trailing_pe is not None else "N/A"
            forward_pe_str = f"{forward_pe:.1f}" if forward_pe is not None else "N/A"
            ptb_str = f"{ptb:.1f}" if ptb is not None else "N/A"
            div_str = f"{div_yield:.2%}" if div_yield is not None else "N/A"

            eg = sa_valuation.get("earnings_growth")
            rg = sa_valuation.get("revenue_growth")
            pm = sa_valuation.get("profit_margins")
            roe = sa_valuation.get("return_on_equity")
            eg_str = f"{eg:.1%}" if eg is not None else "N/A"
            rg_str = f"{rg:.1%}" if rg is not None else "N/A"
            pm_str = f"{pm:.1%}" if pm is not None else "N/A"
            roe_str = f"{roe:.1%}" if roe is not None else "N/A"

            sections.append(f"""## Fundamental Analysis (SeekingAlpha)
- Signal: {seekingalpha.get('signal', 'N/A')}
- Confidence: {seekingalpha.get('confidence', 0)}
- Earnings Estimates: {ee_str}, Growth={ee_growth_str}
- Earnings History:
{history_str}
- EPS Revision Trend: {revision_str}
- Valuation: Trailing P/E={trailing_pe_str}, Forward P/E={forward_pe_str}, P/B={ptb_str}, Div Yield={div_str}
- Growth: Earnings={eg_str}, Revenue={rg_str}, Margins={pm_str}, ROE={roe_str}""")

        # Insider & Institutional Activity
        insider = outputs.get("insider", {})
        if insider:
            ins_data = insider.get("data", {})
            ins_ip = ins_data.get("insider_purchases", {})
            ins_mh = ins_data.get("major_holders", {})
            ins_ih = ins_data.get("institutional_holders", [])
            ins_tx = ins_data.get("insider_transactions", [])
            ins_cal = ins_data.get("calendar", {})
            ins_divs = ins_data.get("dividends", [])

            # Insider activity summary
            net_shares = ins_ip.get("net_shares")
            net_str = f"{net_shares:+,}" if net_shares is not None else "N/A"
            purchases = ins_ip.get("purchases")
            sales = ins_ip.get("sales")
            purchases_str = str(purchases) if purchases is not None else "N/A"
            sales_str = str(sales) if sales is not None else "N/A"

            # Recent transactions (last 5)
            tx_str = "\n".join(
                f"  - {t.get('insider', 'N/A')}: {t.get('transaction', 'N/A')} {t.get('shares', 'N/A')} shares ({t.get('date', 'N/A')})"
                for t in ins_tx[:5]
            ) if ins_tx else "  - No recent transactions"

            # Top institutional holders (top 3)
            def fmt_ih(h):
                holder = h.get('holder', 'N/A')
                pct_out = h.get('pct_out')
                pct_change = h.get('pct_change')
                pct_out_str = f"{pct_out:.2%}" if pct_out is not None else "N/A"
                pct_change_str = f"{pct_change:+.2%}" if pct_change is not None else "N/A"
                return f"  - {holder}: {pct_out_str} (change: {pct_change_str})"
            ih_str = "\n".join(fmt_ih(h) for h in ins_ih[:3]) if ins_ih else "  - No institutional holder data"

            # Upcoming events
            earnings_date = ins_cal.get("earnings_date", "N/A")
            ex_div_date = ins_cal.get("ex_dividend_date", "N/A")

            # Recent dividends (last 2)
            divs_str = ", ".join(
                f"${d.get('amount', 0):.2f} ({d.get('date', 'N/A')})"
                for d in ins_divs[-2:]
            ) if ins_divs else "N/A"

            insiders_pct = ins_mh.get("insiders_pct")
            inst_pct = ins_mh.get("institutions_pct")
            insiders_pct_str = f"{insiders_pct:.2%}" if insiders_pct is not None else "N/A"
            inst_pct_str = f"{inst_pct:.2%}" if inst_pct is not None else "N/A"

            sections.append(f"""## Insider & Institutional Activity
- Signal: {insider.get('signal', 'N/A')}
- Confidence: {insider.get('confidence', 0)}
- Ownership: Insiders={insiders_pct_str}, Institutions={inst_pct_str}
- Insider Activity (6mo): Purchases={purchases_str}, Sales={sales_str}, Net={net_str}
- Recent Insider Transactions:
{tx_str}
- Top Institutional Holders:
{ih_str}
- Upcoming Events: Earnings={earnings_date}, Ex-Dividend={ex_div_date}
- Recent Dividends: {divs_str}""")

        # MotleyFool Quality & Growth Analysis
        motleyfool = outputs.get("motleyfool", {})
        if motleyfool:
            mf_data = motleyfool.get("data", {})
            mf_qm = mf_data.get("quality_metrics", {})
            mf_gm = mf_data.get("growth_metrics", {})
            mf_fh = mf_data.get("financial_health", {})
            mf_val = mf_data.get("valuation", {})
            mf_cf = mf_data.get("cash_flow", {})
            mf_rec = mf_data.get("recommendation", {})

            # Quality metrics
            roe = mf_qm.get("return_on_equity")
            roa = mf_qm.get("return_on_assets")
            gross_margin = mf_qm.get("gross_margin")
            profit_margin = mf_qm.get("profit_margin")
            roe_str = f"{roe:.1%}" if roe is not None else "N/A"
            roa_str = f"{roa:.1%}" if roa is not None else "N/A"
            gm_str = f"{gross_margin:.1%}" if gross_margin is not None else "N/A"
            pm_str = f"{profit_margin:.1%}" if profit_margin is not None else "N/A"

            # Growth metrics
            rev_growth = mf_gm.get("revenue_growth")
            earn_growth = mf_gm.get("earnings_growth")
            rev_growth_str = f"{rev_growth:.1%}" if rev_growth is not None else "N/A"
            earn_growth_str = f"{earn_growth:.1%}" if earn_growth is not None else "N/A"

            # Financial health
            dte = mf_fh.get("debt_to_equity")
            curr_ratio = mf_fh.get("current_ratio")
            total_cash = mf_fh.get("total_cash")
            total_debt = mf_fh.get("total_debt")
            dte_str = f"{dte:.1f}" if dte is not None else "N/A"
            curr_ratio_str = f"{curr_ratio:.2f}" if curr_ratio is not None else "N/A"
            cash_str = f"${total_cash/1e9:.1f}B" if total_cash is not None else "N/A"
            debt_str = f"${total_debt/1e9:.1f}B" if total_debt is not None else "N/A"

            # Valuation
            pe = mf_val.get("trailing_pe")
            fwd_pe = mf_val.get("forward_pe")
            peg = mf_val.get("peg_ratio")
            ptb = mf_val.get("price_to_book")
            pe_str = f"{pe:.1f}" if pe is not None else "N/A"
            fwd_pe_str = f"{fwd_pe:.1f}" if fwd_pe is not None else "N/A"
            peg_str = f"{peg:.2f}" if peg is not None else "N/A"
            ptb_str = f"{ptb:.1f}" if ptb is not None else "N/A"

            # Cash flow
            fcf = mf_cf.get("free_cashflow")
            fcf_str = f"${fcf/1e9:.1f}B" if fcf is not None else "N/A"

            sections.append(f"""## Quality & Growth Analysis (MotleyFool)
- Signal: {motleyfool.get('signal', 'N/A')}
- Confidence: {motleyfool.get('confidence', 0)}
- Quality: ROE={roe_str}, ROA={roa_str}, Gross Margin={gm_str}, Profit Margin={pm_str}
- Growth: Revenue={rev_growth_str}, Earnings={earn_growth_str}
- Financial Health: Debt/Equity={dte_str}, Current Ratio={curr_ratio_str}, Cash={cash_str}, Debt={debt_str}
- Valuation: P/E={pe_str}, Forward P/E={fwd_pe_str}, PEG={peg_str}, P/B={ptb_str}
- Free Cash Flow: {fcf_str}""")

        # StockStory Business Analysis
        stockstory = outputs.get("stockstory", {})
        if stockstory:
            ss_data = stockstory.get("data", {})
            ss_biz = ss_data.get("business_info", {})
            ss_risk = ss_data.get("risk_metrics", {})
            ss_mkt = ss_data.get("market_position", {})
            ss_momentum = ss_data.get("price_momentum", {})
            ss_short = ss_data.get("short_interest", {})

            # Business info
            sector = ss_biz.get("sector", "N/A")
            industry = ss_biz.get("industry", "N/A")
            employees = ss_biz.get("full_time_employees")
            employees_str = f"{employees:,}" if employees is not None else "N/A"

            # Risk metrics
            overall_risk = ss_risk.get("overall_risk")
            beta = ss_risk.get("beta")
            audit_risk = ss_risk.get("audit_risk")
            board_risk = ss_risk.get("board_risk")
            overall_risk_str = f"{overall_risk}/10" if overall_risk is not None else "N/A"
            beta_str = f"{beta:.2f}" if beta is not None else "N/A"
            audit_str = f"{audit_risk}/10" if audit_risk is not None else "N/A"
            board_str = f"{board_risk}/10" if board_risk is not None else "N/A"

            # Market position
            mkt_cap = ss_mkt.get("market_cap")
            mkt_cap_str = f"${mkt_cap/1e9:.0f}B" if mkt_cap is not None else "N/A"
            inst_held = ss_mkt.get("held_by_institutions")
            inst_held_str = f"{inst_held:.1%}" if inst_held is not None else "N/A"

            # Price momentum
            pct_from_200d = ss_momentum.get("pct_from_200d_avg")
            pct_from_52w_high = ss_momentum.get("pct_from_52w_high")
            pct_200d_str = f"{pct_from_200d:+.1%}" if pct_from_200d is not None else "N/A"
            pct_52w_str = f"{pct_from_52w_high:+.1%}" if pct_from_52w_high is not None else "N/A"

            # Short interest
            short_pct = ss_short.get("short_percent_of_float")
            short_ratio = ss_short.get("short_ratio")
            short_pct_str = f"{short_pct:.2%}" if short_pct is not None else "N/A"
            short_ratio_str = f"{short_ratio:.1f} days" if short_ratio is not None else "N/A"

            sections.append(f"""## Business Story Analysis (StockStory)
- Signal: {stockstory.get('signal', 'N/A')}
- Confidence: {stockstory.get('confidence', 0)}
- Business: Sector={sector}, Industry={industry}, Employees={employees_str}
- Governance Risk: Overall={overall_risk_str}, Audit={audit_str}, Board={board_str}
- Market Position: Cap={mkt_cap_str}, Institutional={inst_held_str}, Beta={beta_str}
- Momentum: vs 200d Avg={pct_200d_str}, vs 52w High={pct_52w_str}
- Short Interest: {short_pct_str} of float, {short_ratio_str} to cover""")

        # Yahoo Finance Options & Trading Analysis
        yahoofinance = outputs.get("yahoofinance", {})
        if yahoofinance:
            yf_data = yahoofinance.get("data", {})
            yf_opts = yf_data.get("options_sentiment", {})
            yf_trading = yf_data.get("trading_activity", {})
            yf_div = yf_data.get("dividend_metrics", {})

            # Options sentiment
            pc_ratio = yf_opts.get("put_call_oi_ratio")
            pc_vol_ratio = yf_opts.get("put_call_volume_ratio")
            iv = yf_opts.get("avg_implied_volatility")
            call_oi = yf_opts.get("total_call_open_interest")
            put_oi = yf_opts.get("total_put_open_interest")
            pc_str = f"{pc_ratio:.2f}" if pc_ratio is not None else "N/A"
            pc_vol_str = f"{pc_vol_ratio:.2f}" if pc_vol_ratio is not None else "N/A"
            iv_str = f"{iv:.0%}" if iv is not None else "N/A"
            call_oi_str = f"{call_oi:,}" if call_oi is not None else "N/A"
            put_oi_str = f"{put_oi:,}" if put_oi is not None else "N/A"

            # Trading activity
            vol_ratio = yf_trading.get("volume_ratio")
            spread_pct = yf_trading.get("spread_pct")
            vol_ratio_str = f"{vol_ratio:.2f}x avg" if vol_ratio is not None else "N/A"
            spread_str = f"{spread_pct:.3%}" if spread_pct is not None else "N/A"

            # Dividend metrics (use trailing annual yield as it's more reliable)
            div_yield = yf_div.get("trailing_annual_dividend_yield") or yf_div.get("dividend_yield")
            payout = yf_div.get("payout_ratio")
            div_yield_str = f"{div_yield:.2%}" if div_yield is not None else "N/A"
            payout_str = f"{payout:.1%}" if payout is not None else "N/A"

            sections.append(f"""## Options & Trading Analysis (Yahoo Finance)
- Signal: {yahoofinance.get('signal', 'N/A')}
- Confidence: {yahoofinance.get('confidence', 0)}
- Put/Call Ratio: OI={pc_str}, Volume={pc_vol_str}
- Open Interest: Calls={call_oi_str}, Puts={put_oi_str}
- Implied Volatility: {iv_str}
- Volume: {vol_ratio_str}, Bid-Ask Spread: {spread_str}
- Dividend: Yield={div_yield_str}, Payout Ratio={payout_str}""")

        # Morningstar Moat & Fair Value Analysis
        morningstar = outputs.get("morningstar", {})
        if morningstar:
            ms_data = morningstar.get("data", {})
            ms_moat = ms_data.get("moat_indicators", {})
            ms_fv = ms_data.get("fair_value", {})
            ms_roe = ms_moat.get("return_on_equity")
            ms_pm = ms_moat.get("profit_margin")
            ms_ptfv = ms_fv.get("price_to_fair_value")
            ms_unc = ms_fv.get("uncertainty_rating", "N/A")
            ms_roe_str = f"{ms_roe:.0%}" if ms_roe is not None else "N/A"
            ms_pm_str = f"{ms_pm:.0%}" if ms_pm is not None else "N/A"
            ms_ptfv_str = f"{ms_ptfv:.2f}" if ms_ptfv is not None else "N/A"
            sections.append(f"""## Moat & Fair Value (Morningstar)
- Signal: {morningstar.get('signal', 'N/A')}, Confidence: {morningstar.get('confidence', 0)}
- Moat Indicators: ROE={ms_roe_str}, Profit Margin={ms_pm_str}
- Price/Fair Value: {ms_ptfv_str}, Uncertainty: {ms_unc}""")

        # GuruFocus Value Investing Analysis
        gurufocus = outputs.get("gurufocus", {})
        if gurufocus:
            gf_data = gurufocus.get("data", {})
            gf_val = gf_data.get("value_metrics", {})
            gf_fin = gf_data.get("financial_strength", {})
            gf_pe = gf_val.get("pe_ratio")
            gf_peg = gf_val.get("peg_ratio")
            gf_dte = gf_fin.get("debt_to_equity")
            gf_pe_str = f"{gf_pe:.1f}" if gf_pe is not None else "N/A"
            gf_peg_str = f"{gf_peg:.2f}" if gf_peg is not None else "N/A"
            gf_dte_str = f"{gf_dte:.0f}" if gf_dte is not None else "N/A"
            sections.append(f"""## Value Investing (GuruFocus)
- Signal: {gurufocus.get('signal', 'N/A')}, Confidence: {gurufocus.get('confidence', 0)}
- Value: P/E={gf_pe_str}, PEG={gf_peg_str}
- Financial Strength: D/E={gf_dte_str}""")

        # TradingView Technical Analysis
        tradingview = outputs.get("tradingview", {})
        if tradingview:
            tv_data = tradingview.get("data", {})
            tv_osc = tv_data.get("oscillators", {})
            tv_summ = tv_data.get("summary", {})
            tv_rsi = tv_osc.get("rsi")
            tv_buy = tv_summ.get("total_buy", 0)
            tv_sell = tv_summ.get("total_sell", 0)
            tv_rsi_str = f"{tv_rsi:.0f}" if tv_rsi is not None else "N/A"
            sections.append(f"""## Technical Oscillators (TradingView)
- Signal: {tradingview.get('signal', 'N/A')}, Confidence: {tradingview.get('confidence', 0)}
- RSI: {tv_rsi_str}, Buy Signals: {tv_buy}, Sell Signals: {tv_sell}""")

        # Stock Rover Comprehensive Rating
        stockrover = outputs.get("stockrover", {})
        if stockrover:
            sr_data = stockrover.get("data", {})
            sr_overall = sr_data.get("overall_rating", {}).get("overall_score")
            sr_quality = sr_data.get("quality_score", {}).get("overall_quality")
            sr_value = sr_data.get("value_score", {}).get("overall_value")
            sr_growth = sr_data.get("growth_score", {}).get("overall_growth")
            sr_overall_str = f"{sr_overall:.0f}/100" if sr_overall is not None else "N/A"
            sr_q_str = f"{sr_quality:.0f}" if sr_quality is not None else "N/A"
            sr_v_str = f"{sr_value:.0f}" if sr_value is not None else "N/A"
            sr_g_str = f"{sr_growth:.0f}" if sr_growth is not None else "N/A"
            sections.append(f"""## Comprehensive Rating (Stock Rover)
- Signal: {stockrover.get('signal', 'N/A')}, Confidence: {stockrover.get('confidence', 0)}
- Overall: {sr_overall_str}, Quality: {sr_q_str}, Value: {sr_v_str}, Growth: {sr_g_str}""")

        # Simply Wall St Snowflake Analysis
        simplywallst = outputs.get("simplywallst", {})
        if simplywallst:
            sws_data = simplywallst.get("data", {})
            sws_scores = sws_data.get("snowflake_scores", {})
            sws_total = sws_scores.get("total", 0)
            sws_v = sws_scores.get("value", 0)
            sws_f = sws_scores.get("future", 0)
            sws_p = sws_scores.get("past", 0)
            sws_h = sws_scores.get("health", 0)
            sections.append(f"""## Snowflake Analysis (Simply Wall St)
- Signal: {simplywallst.get('signal', 'N/A')}, Confidence: {simplywallst.get('confidence', 0)}
- Total: {sws_total}/30 (Value={sws_v}, Future={sws_f}, Past={sws_p}, Health={sws_h})""")

        # Alpha Spread Intrinsic Value Analysis
        alphaspread = outputs.get("alphaspread", {})
        if alphaspread:
            as_data = alphaspread.get("data", {})
            as_vs = as_data.get("valuation_summary", {})
            as_iv = as_data.get("intrinsic_value", {})
            as_mos = as_data.get("margin_of_safety", {})
            as_rating = as_vs.get("rating", "N/A")
            as_dcf = as_iv.get("dcf_base")
            as_margin = as_mos.get("average_margin")
            as_dcf_str = f"${as_dcf:.2f}" if as_dcf is not None else "N/A"
            as_margin_str = f"{as_margin:+.0%}" if as_margin is not None else "N/A"
            sections.append(f"""## Intrinsic Value (Alpha Spread)
- Signal: {alphaspread.get('signal', 'N/A')}, Confidence: {alphaspread.get('confidence', 0)}
- Rating: {as_rating}, DCF Value: {as_dcf_str}, Margin of Safety: {as_margin_str}""")

        # FactSet Earnings Quality
        factset = outputs.get("factset", {})
        if factset:
            fs_data = factset.get("data", {})
            fs_eq = fs_data.get("earnings_quality", {})
            fs_accruals = fs_eq.get("accruals_ratio")
            fs_accruals_str = f"{fs_accruals:.2%}" if fs_accruals is not None else "N/A"
            sections.append(f"""## Earnings Quality (FactSet)
- Signal: {factset.get('signal', 'N/A')}, Confidence: {factset.get('confidence', 0)}
- Accruals Ratio: {fs_accruals_str}""")

        # Capital IQ Credit Analysis
        capitaliq = outputs.get("capitaliq", {})
        if capitaliq:
            ciq_data = capitaliq.get("data", {})
            ciq_credit = ciq_data.get("credit_metrics", {})
            ciq_dte = ciq_credit.get("debt_to_equity")
            ciq_icr = ciq_credit.get("interest_coverage")
            ciq_dte_str = f"{ciq_dte:.1f}" if ciq_dte is not None else "N/A"
            ciq_icr_str = f"{ciq_icr:.1f}x" if ciq_icr is not None else "N/A"
            sections.append(f"""## Credit Analysis (Capital IQ)
- Signal: {capitaliq.get('signal', 'N/A')}, Confidence: {capitaliq.get('confidence', 0)}
- D/E: {ciq_dte_str}, Interest Coverage: {ciq_icr_str}""")

        # MarketBeat Analyst Ratings
        marketbeat = outputs.get("marketbeat", {})
        if marketbeat:
            mb_data = marketbeat.get("data", {})
            mb_ar = mb_data.get("analyst_ratings", {})
            mb_et = mb_data.get("earnings_track", {})
            mb_rec = mb_ar.get("recommendation", "N/A")
            mb_beat_rate = mb_et.get("beat_rate")
            mb_beat_str = f"{mb_beat_rate:.0%}" if mb_beat_rate is not None else "N/A"
            sections.append(f"""## Analyst Ratings (MarketBeat)
- Signal: {marketbeat.get('signal', 'N/A')}, Confidence: {marketbeat.get('confidence', 0)}
- Recommendation: {mb_rec}, Earnings Beat Rate: {mb_beat_str}""")

        # Refinitiv Consensus Estimates
        refinitiv = outputs.get("refinitiv", {})
        if refinitiv:
            ref_data = refinitiv.get("data", {})
            ref_ce = ref_data.get("consensus_estimates", {})
            ref_rec = ref_ce.get("recommendation", "N/A")
            ref_target = ref_ce.get("target_price")
            ref_target_str = f"${ref_target:.2f}" if ref_target is not None else "N/A"
            sections.append(f"""## Consensus Estimates (Refinitiv)
- Signal: {refinitiv.get('signal', 'N/A')}, Confidence: {refinitiv.get('confidence', 0)}
- Recommendation: {ref_rec}, Target: {ref_target_str}""")

        # Macrotrends Historical Analysis
        macrotrends = outputs.get("macrotrends", {})
        if macrotrends:
            mt_data = macrotrends.get("data", {})
            mt_ph = mt_data.get("price_history", {})
            mt_1y_ret = mt_ph.get("1y_return")
            mt_vol = mt_ph.get("volatility")
            mt_ret_str = f"{mt_1y_ret:+.0%}" if mt_1y_ret is not None else "N/A"
            mt_vol_str = f"{mt_vol:.0%}" if mt_vol is not None else "N/A"
            sections.append(f"""## Historical Trends (Macrotrends)
- Signal: {macrotrends.get('signal', 'N/A')}, Confidence: {macrotrends.get('confidence', 0)}
- 1Y Return: {mt_ret_str}, Volatility: {mt_vol_str}""")

        # YCharts Valuation Charts
        ycharts = outputs.get("ycharts", {})
        if ycharts:
            yc_data = ycharts.get("data", {})
            yc_vc = yc_data.get("valuation_chart", {})
            yc_mc = yc_data.get("momentum_chart", {})
            yc_pe = yc_vc.get("pe_ratio")
            yc_pct_200d = yc_mc.get("pct_from_200d")
            yc_pe_str = f"{yc_pe:.1f}" if yc_pe is not None else "N/A"
            yc_pct_str = f"{yc_pct_200d:+.0%}" if yc_pct_200d is not None else "N/A"
            sections.append(f"""## Valuation Charts (YCharts)
- Signal: {ycharts.get('signal', 'N/A')}, Confidence: {ycharts.get('confidence', 0)}
- P/E: {yc_pe_str}, vs 200d: {yc_pct_str}""")

        # Koyfin Screening Analysis
        koyfin = outputs.get("koyfin", {})
        if koyfin:
            kf_data = koyfin.get("data", {})
            kf_fund = kf_data.get("fundamentals", {})
            kf_est = kf_data.get("estimates", {})
            kf_roe = kf_fund.get("roe")
            kf_rec = kf_est.get("recommendation", "N/A")
            kf_roe_str = f"{kf_roe:.0%}" if kf_roe is not None else "N/A"
            sections.append(f"""## Screening Analysis (Koyfin)
- Signal: {koyfin.get('signal', 'N/A')}, Confidence: {koyfin.get('confidence', 0)}
- ROE: {kf_roe_str}, Recommendation: {kf_rec}""")

        # Value Line Investment Survey
        valueline = outputs.get("valueline", {})
        if valueline:
            vl_data = valueline.get("data", {})
            vl_tl = vl_data.get("timeliness", {})
            vl_proj = vl_data.get("projections", {})
            vl_mom = vl_tl.get("price_momentum_12m")
            vl_appr = vl_proj.get("appreciation_potential")
            vl_mom_str = f"{vl_mom:+.0%}" if vl_mom is not None else "N/A"
            vl_appr_str = f"{vl_appr:+.0%}" if vl_appr is not None else "N/A"
            sections.append(f"""## Investment Survey (Value Line)
- Signal: {valueline.get('signal', 'N/A')}, Confidence: {valueline.get('confidence', 0)}
- 12M Momentum: {vl_mom_str}, Appreciation Potential: {vl_appr_str}""")

        # X/Twitter Social Sentiment
        xtwitter = outputs.get("xtwitter", {})
        if xtwitter:
            xt_data = xtwitter.get("data", {})
            xt_sm = xt_data.get("sentiment_metrics", {})
            xt_score = xt_sm.get("sentiment_score")
            xt_pos = xt_sm.get("positive_ratio")
            xt_score_str = f"{xt_score:+.2f}" if xt_score is not None else "N/A"
            xt_pos_str = f"{xt_pos:.0%}" if xt_pos is not None else "N/A"
            sections.append(f"""## Social Sentiment (X/Twitter)
- Signal: {xtwitter.get('signal', 'N/A')}, Confidence: {xtwitter.get('confidence', 0)}
- Sentiment Score: {xt_score_str}, Positive Ratio: {xt_pos_str}""")

        # Facebook Community Engagement
        facebook = outputs.get("facebook", {})
        if facebook:
            fb_data = facebook.get("data", {})
            fb_cs = fb_data.get("community_sentiment", {})
            fb_rec = fb_cs.get("recommendation", "N/A")
            fb_upside = fb_cs.get("analyst_upside")
            fb_upside_str = f"{fb_upside:+.0%}" if fb_upside is not None else "N/A"
            sections.append(f"""## Community Engagement (Facebook)
- Signal: {facebook.get('signal', 'N/A')}, Confidence: {facebook.get('confidence', 0)}
- Recommendation: {fb_rec}, Analyst Upside: {fb_upside_str}""")

        # Instagram Brand Analysis
        instagram = outputs.get("instagram", {})
        if instagram:
            ig_data = instagram.get("data", {})
            ig_vm = ig_data.get("visual_metrics", {})
            ig_tm = ig_data.get("trend_metrics", {})
            ig_3m = ig_vm.get("3m_return")
            ig_above_200 = ig_tm.get("above_200d")
            ig_3m_str = f"{ig_3m:+.0%}" if ig_3m is not None else "N/A"
            ig_trend_str = "Above" if ig_above_200 else "Below" if ig_above_200 is False else "N/A"
            sections.append(f"""## Brand Analysis (Instagram)
- Signal: {instagram.get('signal', 'N/A')}, Confidence: {instagram.get('confidence', 0)}
- 3M Return: {ig_3m_str}, vs 200d: {ig_trend_str}""")

        # CNBC Market News
        cnbc = outputs.get("cnbc", {})
        if cnbc:
            cnbc_data = cnbc.get("data", {})
            cnbc_mp = cnbc_data.get("market_pulse", {})
            cnbc_ns = cnbc_data.get("news_sentiment", {})
            cnbc_day = cnbc_mp.get("day_change_pct")
            cnbc_sent = cnbc_ns.get("sentiment_ratio")
            cnbc_day_str = f"{cnbc_day:+.1%}" if cnbc_day is not None else "N/A"
            cnbc_sent_str = f"{cnbc_sent:+.2f}" if cnbc_sent is not None else "N/A"
            sections.append(f"""## Market News (CNBC)
- Signal: {cnbc.get('signal', 'N/A')}, Confidence: {cnbc.get('confidence', 0)}
- Day Change: {cnbc_day_str}, News Sentiment: {cnbc_sent_str}""")

        # Bloomberg Institutional Analysis
        bloomberg = outputs.get("bloomberg", {})
        if bloomberg:
            bb_data = bloomberg.get("data", {})
            bb_ea = bb_data.get("equity_analysis", {})
            bb_earn = bb_data.get("earnings_analysis", {})
            bb_peg = bb_ea.get("peg_ratio")
            bb_roe = bb_earn.get("roe")
            bb_peg_str = f"{bb_peg:.2f}" if bb_peg is not None else "N/A"
            bb_roe_str = f"{bb_roe:.0%}" if bb_roe is not None else "N/A"
            sections.append(f"""## Institutional Analysis (Bloomberg)
- Signal: {bloomberg.get('signal', 'N/A')}, Confidence: {bloomberg.get('confidence', 0)}
- PEG: {bb_peg_str}, ROE: {bb_roe_str}""")

        # WSJ Business Analysis
        wsj = outputs.get("wsj", {})
        if wsj:
            wsj_data = wsj.get("data", {})
            wsj_fp = wsj_data.get("financial_performance", {})
            wsj_mv = wsj_data.get("market_valuation", {})
            wsj_rev = wsj_fp.get("revenue_growth")
            wsj_pe = wsj_mv.get("pe_ratio")
            wsj_rev_str = f"{wsj_rev:+.0%}" if wsj_rev is not None else "N/A"
            wsj_pe_str = f"{wsj_pe:.1f}" if wsj_pe is not None else "N/A"
            sections.append(f"""## Business Analysis (WSJ)
- Signal: {wsj.get('signal', 'N/A')}, Confidence: {wsj.get('confidence', 0)}
- Revenue Growth: {wsj_rev_str}, P/E: {wsj_pe_str}""")

        # MarketWatch Performance
        mwatch = outputs.get("marketwatch", {})
        if mwatch:
            mw_data = mwatch.get("data", {})
            mw_pm = mw_data.get("performance_metrics", {})
            mw_ae = mw_data.get("analyst_estimates", {})
            mw_3m = mw_pm.get("return_3m")
            mw_rec = mw_ae.get("recommendation", "N/A")
            mw_3m_str = f"{mw_3m:+.0%}" if mw_3m is not None else "N/A"
            sections.append(f"""## Market Performance (MarketWatch)
- Signal: {mwatch.get('signal', 'N/A')}, Confidence: {mwatch.get('confidence', 0)}
- 3M Return: {mw_3m_str}, Recommendation: {mw_rec}""")

        # Fox Business Market Analysis
        foxbiz = outputs.get("foxbusiness", {})
        if foxbiz:
            fb_data = foxbiz.get("data", {})
            fb_mm = fb_data.get("market_movers", {})
            fb_ts = fb_data.get("trading_signals", {})
            fb_high = fb_mm.get("from_52w_high")
            fb_rec = fb_ts.get("recommendation", "N/A")
            fb_high_str = f"{fb_high:+.0%}" if fb_high is not None else "N/A"
            sections.append(f"""## Market Analysis (Fox Business)
- Signal: {foxbiz.get('signal', 'N/A')}, Confidence: {foxbiz.get('confidence', 0)}
- vs 52W High: {fb_high_str}, Recommendation: {fb_rec}""")

        # Barron's Premium Analysis
        barrons = outputs.get("barrons", {})
        if barrons:
            br_data = barrons.get("data", {})
            br_spa = br_data.get("stock_pick_analysis", {})
            br_ga = br_data.get("growth_analysis", {})
            br_upside = br_spa.get("upside_to_target")
            br_roe = br_ga.get("roe")
            br_upside_str = f"{br_upside:+.0%}" if br_upside is not None else "N/A"
            br_roe_str = f"{br_roe:.0%}" if br_roe is not None else "N/A"
            sections.append(f"""## Premium Analysis (Barron's)
- Signal: {barrons.get('signal', 'N/A')}, Confidence: {barrons.get('confidence', 0)}
- Target Upside: {br_upside_str}, ROE: {br_roe_str}""")

        # Insider Monkey Hedge Fund Tracking
        insidermonkey = outputs.get("insidermonkey", {})
        if insidermonkey:
            im_data = insidermonkey.get("data", {})
            im_hfs = im_data.get("hedge_fund_sentiment", {})
            im_ia = im_data.get("insider_activity", {})
            im_hf_count = im_hfs.get("hedge_fund_count", 0)
            im_sentiment = im_ia.get("net_insider_sentiment", "N/A")
            sections.append(f"""## Hedge Fund Tracking (Insider Monkey)
- Signal: {insidermonkey.get('signal', 'N/A')}, Confidence: {insidermonkey.get('confidence', 0)}
- Hedge Funds: {im_hf_count}, Insider Sentiment: {im_sentiment}""")

        # Quiver Quantitative Alternative Data
        quiverquant = outputs.get("quiverquant", {})
        if quiverquant:
            qq_data = quiverquant.get("data", {})
            qq_ia = qq_data.get("institutional_activity", {})
            qq_si = qq_data.get("short_interest", {})
            qq_inst_sent = qq_ia.get("net_institutional_sentiment", "N/A")
            qq_squeeze = qq_si.get("short_squeeze_potential", "N/A")
            sections.append(f"""## Alternative Data (Quiver Quant)
- Signal: {quiverquant.get('signal', 'N/A')}, Confidence: {quiverquant.get('confidence', 0)}
- Institutional: {qq_inst_sent}, Squeeze Potential: {qq_squeeze}""")

        # Dataroma Superinvestor Tracking
        dataroma = outputs.get("dataroma", {})
        if dataroma:
            dr_data = dataroma.get("data", {})
            dr_sh = dr_data.get("superinvestor_holdings", {})
            dr_pc = dr_data.get("position_changes", {})
            dr_supers = dr_sh.get("superinvestor_count", 0)
            dr_flow = dr_pc.get("net_sentiment", "N/A")
            sections.append(f"""## Superinvestor Tracking (Dataroma)
- Signal: {dataroma.get('signal', 'N/A')}, Confidence: {dataroma.get('confidence', 0)}
- Superinvestors: {dr_supers}, Flow: {dr_flow}""")

        # OpenInsider Form 4 Filings
        openinsider = outputs.get("openinsider", {})
        if openinsider:
            oi_data = openinsider.get("data", {})
            oi_ts = oi_data.get("transaction_summary", {})
            oi_cb = oi_data.get("cluster_buys", {})
            oi_net = oi_ts.get("net_shares", 0)
            oi_net_str = f"{oi_net:+,}" if oi_net else "0"
            oi_cluster = oi_cb.get("cluster_signal", "N/A")
            sections.append(f"""## Form 4 Filings (OpenInsider)
- Signal: {openinsider.get('signal', 'N/A')}, Confidence: {openinsider.get('confidence', 0)}
- Net Shares: {oi_net_str}, Cluster: {oi_cluster}""")

        # WhaleWisdom 13F Holdings
        whalewisdom = outputs.get("whalewisdom", {})
        if whalewisdom:
            ww_data = whalewisdom.get("data", {})
            ww_pc = ww_data.get("position_changes", {})
            ww_wa = ww_data.get("whale_activity", {})
            ww_flow = ww_pc.get("net_flow", "N/A")
            ww_whale_sent = ww_wa.get("whale_sentiment", "N/A")
            sections.append(f"""## 13F Holdings (WhaleWisdom)
- Signal: {whalewisdom.get('signal', 'N/A')}, Confidence: {whalewisdom.get('confidence', 0)}
- Flow: {ww_flow}, Whale Sentiment: {ww_whale_sent}""")

        # ETF.com Research
        etfcom = outputs.get("etfcom", {})
        if etfcom:
            ec_data = etfcom.get("data", {})
            ec_pm = ec_data.get("performance_metrics", {})
            ec_fo = ec_data.get("fund_overview", {})
            ec_1y = ec_pm.get("return_1y")
            ec_1y_str = f"{ec_1y:+.0%}" if ec_1y is not None else "N/A"
            ec_cat = ec_fo.get("category", "N/A")[:15]
            sections.append(f"""## ETF Research (ETF.com)
- Signal: {etfcom.get('signal', 'N/A')}, Confidence: {etfcom.get('confidence', 0)}
- 1Y Return: {ec_1y_str}, Category: {ec_cat}""")

        # ETFdb Screening
        etfdb = outputs.get("etfdb", {})
        if etfdb:
            ed_data = etfdb.get("data", {})
            ed_eg = ed_data.get("etf_grades", {})
            ed_da = ed_data.get("dividend_analysis", {})
            ed_grade = ed_eg.get("overall_grade", "N/A")
            ed_yield = ed_da.get("dividend_yield")
            ed_yield_str = f"{ed_yield:.2%}" if ed_yield is not None else "N/A"
            sections.append(f"""## ETF Screening (ETFdb)
- Signal: {etfdb.get('signal', 'N/A')}, Confidence: {etfdb.get('confidence', 0)}
- Grade: {ed_grade}, Yield: {ed_yield_str}""")

        # Global X Thematic Research
        globalxetf = outputs.get("globalxetf", {})
        if globalxetf:
            gx_data = globalxetf.get("data", {})
            gx_te = gx_data.get("thematic_exposure", {})
            gx_gm = gx_data.get("growth_metrics", {})
            gx_themes = gx_te.get("identified_themes", [])
            gx_theme_str = gx_themes[0][:12] if gx_themes else "N/A"
            gx_rev = gx_gm.get("revenue_growth")
            gx_rev_str = f"{gx_rev:+.0%}" if gx_rev is not None else "N/A"
            sections.append(f"""## Thematic Research (Global X)
- Signal: {globalxetf.get('signal', 'N/A')}, Confidence: {globalxetf.get('confidence', 0)}
- Theme: {gx_theme_str}, Revenue Growth: {gx_rev_str}""")

        # ARK Invest Disruptive Innovation
        arkinvest = outputs.get("arkinvest", {})
        if arkinvest:
            ark_data = arkinvest.get("data", {})
            ark_im = ark_data.get("innovation_metrics", {})
            ark_gt = ark_data.get("growth_trajectory", {})
            ark_areas = ark_im.get("innovation_areas", [])
            ark_area_str = ark_areas[0][:10] if ark_areas else "Traditional"
            ark_mom = ark_gt.get("momentum", "N/A")
            sections.append(f"""## Disruptive Innovation (ARK Invest)
- Signal: {arkinvest.get('signal', 'N/A')}, Confidence: {arkinvest.get('confidence', 0)}
- Innovation Area: {ark_area_str}, Momentum: {ark_mom}""")

        # Morningstar ETF Ratings
        morningstaretf = outputs.get("morningstaretf", {})
        if morningstaretf:
            mse_data = morningstaretf.get("data", {})
            mse_sr = mse_data.get("star_rating_proxy", {})
            mse_ar = mse_data.get("analyst_rating", {})
            mse_stars = mse_sr.get("star_rating", "N/A")
            mse_rating = mse_ar.get("morningstar_rating", "N/A")
            sections.append(f"""## ETF Ratings (Morningstar)
- Signal: {morningstaretf.get('signal', 'N/A')}, Confidence: {morningstaretf.get('confidence', 0)}
- Stars: {mse_stars}, Rating: {mse_rating}""")

        # Sentiment
        sentiment = outputs.get("sentiment", {})
        if sentiment:
            agg = sentiment.get("data", {}).get("aggregate", {})
            sections.append(f"""## Sentiment Analysis
- Signal: {sentiment.get('signal', 'N/A')}
- Aggregate Score: {agg.get('aggregate_score', 'N/A')}
- News Average: {agg.get('news_avg', 'N/A')}
- Filing Average: {agg.get('filing_avg', 'N/A')}""")

        current_price = self._resolve_current_price(outputs)

        num_sources = len(sections)
        active_agent_names = list(outputs.keys())
        agents_summary = ", ".join(active_agent_names) if active_agent_names else "limited sources"

        prompt = f"""You are a senior stock analyst. Analyze the following multi-source data for {self.ticker} and provide a final trading signal.

{"".join(sections) if sections else "Limited data available. Provide a conservative HOLD recommendation."}

Based on ALL the above data ({num_sources} active data source(s): {agents_summary}), provide your final analysis as JSON with these exact fields:
{{
  "signal": "BUY" or "SELL" or "HOLD",
  "confidence": 0.0 to 1.0,
  "target_price": estimated target price as number,
  "potential_upside_pct": percentage upside as number,
  "potential_downside_pct": percentage downside as negative number,
  "stop_loss": suggested stop loss price as number,
  "sentiment_score": -1.0 to 1.0,
  "reasoning": "2-3 sentence explanation synthesizing all {num_sources} active data source(s) ({agents_summary})"
}}"""

        # Call LLM
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional stock analyst. Respond ONLY with valid JSON, no markdown fencing."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base

        try:
            response = litellm.completion(**kwargs)
            raw = response.choices[0].message.content.strip()

            # Strip markdown fencing if present
            cleaned = raw
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
            cleaned = cleaned.strip()

            self._state["reasoning"] = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"  [Orchestrator] JSON decode error: {e}", file=sys.stderr)
            print(f"  [Orchestrator] Raw LLM response: {raw[:500] if 'raw' in dir() else 'N/A'}...", file=sys.stderr)
            self._state["reasoning"] = {
                "signal": "HOLD",
                "confidence": 0.0,
                "target_price": current_price or 0,
                "potential_upside_pct": 0,
                "potential_downside_pct": 0,
                "stop_loss": 0,
                "sentiment_score": 0,
                "reasoning": f"Could not parse LLM response as JSON. Defaulting to HOLD.",
            }
        except Exception as e:
            print(f"  [Orchestrator] LLM synthesis error: {type(e).__name__}: {e}", file=sys.stderr)
            self._state["reasoning"] = {
                "signal": "HOLD",
                "confidence": 0.0,
                "target_price": current_price or 0,
                "potential_upside_pct": 0,
                "potential_downside_pct": 0,
                "stop_loss": 0,
                "sentiment_score": 0,
                "reasoning": f"Could not synthesize multi-agent data: {type(e).__name__}. Defaulting to HOLD.",
            }

    def act(self):
        reasoning = self._state["reasoning"]
        outputs = self._state["data"].get("agent_outputs", {})
        tech = outputs.get("technical", {})
        majority = self._compute_majority_vote(outputs)

        current_price = self._resolve_current_price(outputs)

        # Build comprehensive sources list based on agents used
        source_mapping = {
            "technical": {"name": "Yahoo Finance (Technical)", "url": f"https://finance.yahoo.com/quote/{self.ticker}"},
            "news": {"name": "Yahoo Finance News", "url": f"https://finance.yahoo.com/quote/{self.ticker}/news"},
            "sec": {"name": "SEC EDGAR", "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={self.ticker}"},
            "sentiment": {"name": "Sentiment Analysis", "url": ""},
            "zacks": {"name": "Zacks Investment Research", "url": f"https://www.zacks.com/stock/quote/{self.ticker}"},
            "tipranks": {"name": "TipRanks", "url": f"https://www.tipranks.com/stocks/{self.ticker}"},
            "seekingalpha": {"name": "Seeking Alpha", "url": f"https://seekingalpha.com/symbol/{self.ticker}"},
            "insider": {"name": "Insider Trading Data", "url": f"https://finance.yahoo.com/quote/{self.ticker}/insider-transactions"},
            "motleyfool": {"name": "Motley Fool", "url": f"https://www.fool.com/quote/{self.ticker}"},
            "stockstory": {"name": "Stock Story", "url": "https://www.stockstory.org"},
            "yahoofinance": {"name": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{self.ticker}"},
            "morningstar": {"name": "Morningstar", "url": f"https://www.morningstar.com/stocks/{self.ticker}"},
            "gurufocus": {"name": "GuruFocus", "url": f"https://www.gurufocus.com/stock/{self.ticker}"},
            "tradingview": {"name": "TradingView", "url": f"https://www.tradingview.com/symbols/{self.ticker}"},
            "stockrover": {"name": "Stock Rover", "url": "https://www.stockrover.com"},
            "simplywallst": {"name": "Simply Wall St", "url": f"https://simplywall.st/stocks/{self.ticker}"},
            "alphaspread": {"name": "Alpha Spread", "url": "https://www.alphaspread.com"},
            "factset": {"name": "FactSet", "url": "https://www.factset.com"},
            "capitaliq": {"name": "S&P Capital IQ", "url": "https://www.capitaliq.com"},
            "marketbeat": {"name": "MarketBeat", "url": f"https://www.marketbeat.com/stocks/{self.ticker}"},
            "refinitiv": {"name": "Refinitiv", "url": "https://www.refinitiv.com"},
            "macrotrends": {"name": "Macrotrends", "url": f"https://www.macrotrends.net/stocks/charts/{self.ticker}"},
            "ycharts": {"name": "YCharts", "url": f"https://ycharts.com/companies/{self.ticker}"},
            "koyfin": {"name": "Koyfin", "url": f"https://www.koyfin.com/stock/{self.ticker}"},
            "valueline": {"name": "Value Line", "url": "https://www.valueline.com"},
            "xtwitter": {"name": "X (Twitter)", "url": f"https://twitter.com/search?q=%24{self.ticker}"},
            "facebook": {"name": "Facebook", "url": "https://www.facebook.com"},
            "instagram": {"name": "Instagram", "url": "https://www.instagram.com"},
            "cnbc": {"name": "CNBC", "url": f"https://www.cnbc.com/quotes/{self.ticker}"},
            "bloomberg": {"name": "Bloomberg", "url": f"https://www.bloomberg.com/quote/{self.ticker}:US"},
            "wsj": {"name": "Wall Street Journal", "url": f"https://www.wsj.com/market-data/quotes/{self.ticker}"},
            "marketwatch": {"name": "MarketWatch", "url": f"https://www.marketwatch.com/investing/stock/{self.ticker}"},
            "foxbusiness": {"name": "Fox Business", "url": f"https://www.foxbusiness.com/quote?stockTicker={self.ticker}"},
            "barrons": {"name": "Barron's", "url": f"https://www.barrons.com/market-data/stocks/{self.ticker}"},
            "insidermonkey": {"name": "Insider Monkey", "url": f"https://www.insidermonkey.com/insider-trading/company/{self.ticker}"},
            "quiverquant": {"name": "Quiver Quantitative", "url": f"https://www.quiverquant.com/stocks/{self.ticker}"},
            "dataroma": {"name": "Dataroma", "url": "https://www.dataroma.com"},
            "openinsider": {"name": "OpenInsider", "url": f"https://www.openinsider.com/search?q={self.ticker}"},
            "whalewisdom": {"name": "WhaleWisdom", "url": f"https://whalewisdom.com/stock/{self.ticker}"},
            "etfcom": {"name": "ETF.com", "url": "https://www.etf.com"},
            "etfdb": {"name": "ETF Database", "url": "https://etfdb.com"},
            "globalxetf": {"name": "Global X ETFs", "url": "https://www.globalxetfs.com"},
            "arkinvest": {"name": "ARK Invest", "url": "https://ark-invest.com"},
            "morningstaretf": {"name": "Morningstar ETF", "url": "https://www.morningstar.com/etfs"},
        }

        sources = []
        for agent_name in outputs.keys():
            if agent_name in source_mapping:
                sources.append(source_mapping[agent_name])

        final_signal, final_confidence, decision_source = self._reconcile_with_majority(reasoning, majority)
        self._debug_log_reconciliation(reasoning, majority, final_signal, final_confidence, decision_source)

        # ── Knowledge graph context ────────────────────────────────────
        kg_context = self.knowledge_graph.get_context(self.ticker) if self.knowledge_graph else {}

        # ── Neuro-symbolic validation ──────────────────────────────────
        tech_data = outputs.get("technical", {}).get("data", {})
        validation = self.symbolic_validator.validate(
            final_signal, final_confidence, tech_data, kg_context=kg_context
        )
        final_signal = validation.signal
        final_confidence = validation.confidence
        if validation.overridden or validation.rules_triggered:
            print(
                f"  [SymbolicValidator] rules={validation.rules_triggered} "
                f"overridden={validation.overridden} → {final_signal} @ {final_confidence}",
                file=sys.stderr,
            )

        result = {
            "ticker": self.ticker,
            "current_price": current_price,
            "signal": final_signal,
            "confidence": final_confidence,
            "target_price": reasoning.get("target_price"),
            "potential_upside_pct": reasoning.get("potential_upside_pct"),
            "potential_downside_pct": reasoning.get("potential_downside_pct"),
            "stop_loss": reasoning.get("stop_loss"),
            "sentiment_score": reasoning.get("sentiment_score", 0),
            "reasoning": reasoning.get("reasoning", ""),
            "data_period_days": self.past_days,
            "mode": "multi-agent",
            "agents_used": list(outputs.keys()),
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "llm_signal": self._normalize_signal(reasoning.get("signal")),
            "llm_confidence": float(reasoning.get("confidence") or 0.0),
            "majority_signal": majority["majority_signal"],
            "majority_vote_ratio": majority["majority_vote_ratio"],
            "majority_vote_counts": majority["vote_counts"],
            "decision_source": decision_source,
            "symbolic_validation": {
                "rules_triggered": validation.rules_triggered,
                "overridden": validation.overridden,
                "adjustments": validation.adjustments,
                "kg_sector": kg_context.get("sector"),
                "kg_industry": kg_context.get("industry"),
                "kg_macro_sensitivities": kg_context.get("macro_sensitivities"),
            },
        }

        # Always include agent_details for ensemble scoring (verbose only affects display)
        result["agent_details"] = {
            name: {
                "signal": out.get("signal"),
                "confidence": out.get("confidence"),
                "summary": out.get("summary") if self.verbose else None,
            }
            for name, out in outputs.items()
        }

        self._state["actions"] = result

    def get_signal(self) -> dict:
        return self._state.get("actions", {})
