"""SeekingAlpha agent that fetches fundamental & estimates data via yfinance."""

import os
import sys
import uuid
from datetime import datetime, timezone

import yfinance as yf

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, SeekingAlphaMessage


class SeekingAlphaAgent(AgenticAIBase):
    """Fetches earnings estimates, growth estimates, earnings history, EPS trends, and valuation metrics from yfinance."""

    def __init__(self, ticker: str,
                 kafka_producer=None, kafka_enabled: bool = False,
                 qdrant_store=None, qdrant_enabled: bool = False,
                 embedder=None):
        super().__init__()
        self.ticker = ticker.upper()
        self.kafka_producer = kafka_producer
        self.kafka_enabled = kafka_enabled
        self.qdrant_store = qdrant_store
        self.qdrant_enabled = qdrant_enabled
        self.embedder = embedder

        self.register_tool("fetch_seekingalpha_data", self._fetch_seekingalpha_data,
                           "Fetch fundamental & estimates data from yfinance")

        # Check for Seeking Alpha API key
        if not os.getenv("SEEKINGALPHA_API_KEY"):
            print(f"  [SeekingAlphaAgent] No SEEKINGALPHA_API_KEY found. Using yfinance proxy (free alternative to $20-30/month Seeking Alpha Premium)", file=sys.stderr)

        if self.kafka_enabled:
            self.register_tool("publish_to_kafka", self._publish_to_kafka,
                               "Publish fundamental data to Kafka")
        if self.qdrant_enabled:
            self.register_tool("store_in_qdrant", self._store_in_qdrant,
                               "Store fundamental data embeddings in Qdrant")

    # -- Helpers ---------------------------------------------------------------

    @staticmethod
    def _safe_float(val) -> float | None:
        """Convert a value to float, returning None for NaN/None."""
        if val is None:
            return None
        try:
            f = float(val)
            return None if f != f else f  # NaN check
        except (ValueError, TypeError):
            return None

    # -- Tool implementations --------------------------------------------------

    def _fetch_seekingalpha_data(self) -> dict:
        """Fetch fundamental & estimates data from yfinance."""
        tk = yf.Ticker(self.ticker)
        data = {
            "earnings_estimates": {},
            "revenue_estimates": {},
            "growth_estimates": {},
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {},
        }

        # Earnings estimates
        try:
            ee = tk.earnings_estimate
            if ee is not None and not ee.empty:
                # Rows are periods (0q, +1q, 0y, +1y), columns are fields
                row = ee.iloc[0]  # Current quarter (0q)
                data["earnings_estimates"] = {
                    "period": str(ee.index[0]),
                    "avg": self._safe_float(row.get("avg")),
                    "low": self._safe_float(row.get("low")),
                    "high": self._safe_float(row.get("high")),
                    "year_ago_eps": self._safe_float(row.get("yearAgoEps")),
                    "number_of_analysts": int(row["numberOfAnalysts"]) if self._safe_float(row.get("numberOfAnalysts")) is not None else None,
                    "growth": self._safe_float(row.get("growth")),
                }
        except Exception:
            pass

        # Revenue estimates
        try:
            re_ = tk.revenue_estimate
            if re_ is not None and not re_.empty:
                # Use current year row (index 2 = "0y") if available, else first row
                row_idx = min(2, len(re_) - 1)
                row = re_.iloc[row_idx]
                data["revenue_estimates"] = {
                    "period": str(re_.index[row_idx]),
                    "avg": self._safe_float(row.get("avg")),
                    "low": self._safe_float(row.get("low")),
                    "high": self._safe_float(row.get("high")),
                    "number_of_analysts": int(row["numberOfAnalysts"]) if self._safe_float(row.get("numberOfAnalysts")) is not None else None,
                    "year_ago_revenue": self._safe_float(row.get("yearAgoRevenue")),
                    "growth": self._safe_float(row.get("growth")),
                }
        except Exception:
            pass

        # Growth estimates
        try:
            ge = tk.growth_estimates
            if ge is not None and not ge.empty:
                # Columns are ticker symbol and index name; rows are periods
                stock_col = ge.columns[0] if len(ge.columns) > 0 else None
                index_col = ge.columns[1] if len(ge.columns) > 1 else None
                growth_data = {}
                if stock_col is not None:
                    for period in ge.index:
                        entry = {"stock_trend": self._safe_float(ge.loc[period, stock_col])}
                        if index_col is not None:
                            entry["index_trend"] = self._safe_float(ge.loc[period, index_col])
                        growth_data[str(period)] = entry
                data["growth_estimates"] = growth_data
        except Exception:
            pass

        # Earnings history (last 4 quarters)
        try:
            eh = tk.earnings_history
            if eh is not None and not eh.empty:
                # Rows are quarter timestamps, columns are epsActual, epsEstimate, etc.
                history = []
                for idx, row in eh.iterrows():
                    history.append({
                        "quarter": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                        "eps_actual": self._safe_float(row.get("epsActual")),
                        "eps_estimate": self._safe_float(row.get("epsEstimate")),
                        "eps_difference": self._safe_float(row.get("epsDifference")),
                        "surprise_percent": self._safe_float(row.get("surprisePercent")),
                    })
                data["earnings_history"] = history
        except Exception:
            pass

        # EPS trend (current quarter)
        try:
            et = tk.eps_trend
            if et is not None and not et.empty:
                # Rows are periods (0q, +1q, ...), columns are current, 7daysAgo, etc.
                row = et.iloc[0]  # Current quarter (0q)
                data["eps_trend"] = {
                    "current": self._safe_float(row.get("current")),
                    "7days_ago": self._safe_float(row.get("7daysAgo")),
                    "30days_ago": self._safe_float(row.get("30daysAgo")),
                    "60days_ago": self._safe_float(row.get("60daysAgo")),
                    "90days_ago": self._safe_float(row.get("90daysAgo")),
                }
        except Exception:
            pass

        # Valuation metrics from info
        try:
            info = tk.info
            data["valuation"] = {
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "price_to_book": info.get("priceToBook"),
                "dividend_yield": info.get("dividendYield"),
                "profit_margins": info.get("profitMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
            }
        except Exception:
            pass

        return data

    def _publish_to_kafka(self, sa_data: dict) -> int:
        if not self.kafka_producer:
            return 0
        msg = SeekingAlphaMessage(
            ticker=self.ticker,
            earnings_estimates=sa_data.get("earnings_estimates", {}),
            revenue_estimates=sa_data.get("revenue_estimates", {}),
            growth_estimates=sa_data.get("growth_estimates", {}),
            earnings_history=sa_data.get("earnings_history", []),
            eps_trend=sa_data.get("eps_trend", {}),
            valuation=sa_data.get("valuation", {}),
        )
        self.kafka_producer.send(Config.KAFKA_TOPIC_SEEKINGALPHA, key=self.ticker,
                                 value=msg.model_dump_json())
        return 1

    def _store_in_qdrant(self, sa_data: dict) -> int:
        if not self.qdrant_store or not self.embedder:
            return 0
        valuation = sa_data.get("valuation", {})
        ee = sa_data.get("earnings_estimates", {})
        eps_trend = sa_data.get("eps_trend", {})
        summary = (
            f"Fundamental analysis for {self.ticker}: "
            f"Trailing P/E={valuation.get('trailing_pe', 'N/A')}, "
            f"Forward P/E={valuation.get('forward_pe', 'N/A')}, "
            f"EPS Estimate={ee.get('avg', 'N/A')}, "
            f"EPS Growth={ee.get('growth', 'N/A')}, "
            f"EPS Trend Current={eps_trend.get('current', 'N/A')}."
        )
        embeddings = self.embedder.embed([summary])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.ticker}:seekingalpha"))
        points = [{
            "id": point_id,
            "vector": embeddings[0],
            "payload": {
                "ticker": self.ticker,
                "valuation": valuation,
                "earnings_estimates": ee,
                "eps_trend": eps_trend,
            },
        }]
        self.qdrant_store.upsert(Config.QDRANT_COLLECTION_SEEKINGALPHA, points)
        return 1

    # -- Signal mapping --------------------------------------------------------

    def _compute_signal(self, sa_data: dict) -> tuple[str, float]:
        """Composite score from earnings surprises, EPS revisions, and growth."""
        scores = []

        # Factor 1: Earnings surprises (weight 0.4)
        history = sa_data.get("earnings_history", [])
        surprise_entries = [h for h in history if h.get("surprise_percent") is not None]
        if surprise_entries:
            beats = sum(1 for h in surprise_entries if h["surprise_percent"] > 0)
            total = len(surprise_entries)
            if total > 0:
                ratio = beats / total
                if ratio >= 1.0:
                    surprise_score = 1.0
                elif ratio >= 0.75:
                    surprise_score = 0.5
                elif ratio >= 0.5:
                    surprise_score = 0.0
                elif ratio >= 0.25:
                    surprise_score = -0.5
                else:
                    surprise_score = -1.0
                scores.append(("surprises", 0.4, surprise_score))

        # Factor 2: EPS revisions (weight 0.3)
        eps_trend = sa_data.get("eps_trend", {})
        current_eps = eps_trend.get("current")
        ago_30_eps = eps_trend.get("30days_ago")
        if current_eps is not None and ago_30_eps is not None:
            if current_eps > ago_30_eps:
                revision_score = 1.0
            elif current_eps < ago_30_eps:
                revision_score = -1.0
            else:
                revision_score = 0.0
            scores.append(("revisions", 0.3, revision_score))

        # Factor 3: Earnings growth (weight 0.3)
        valuation = sa_data.get("valuation", {})
        earnings_growth = valuation.get("earnings_growth")
        if earnings_growth is not None:
            if earnings_growth > 0.20:
                growth_score = 1.0
            elif earnings_growth > 0.10:
                growth_score = 0.5
            elif earnings_growth > 0.0:
                growth_score = 0.0
            else:
                growth_score = -1.0
            scores.append(("growth", 0.3, growth_score))

        if not scores:
            return "NEUTRAL", 0.0

        # Normalize weights to sum to 1.0 for available factors
        total_weight = sum(w for _, w, _ in scores)
        composite = sum(w * s / total_weight for _, w, s in scores)

        if composite > 0.3:
            confidence = min(0.95, 0.5 + composite * 0.4)
            return "BULLISH", confidence
        elif composite < -0.3:
            confidence = min(0.95, 0.5 + abs(composite) * 0.4)
            return "BEARISH", confidence
        else:
            return "NEUTRAL", 0.5

    # -- Agentic lifecycle -----------------------------------------------------

    def plan(self):
        self._state["plan"] = [
            "Fetch fundamental & estimates data from yfinance",
            "Publish to Kafka (if enabled)",
            "Store embeddings in Qdrant (if enabled)",
        ]

    def perceive(self):
        sa_data = self.use_tool("fetch_seekingalpha_data")
        self._state["data"]["seekingalpha"] = sa_data
        if not sa_data.get("earnings_estimates") and not sa_data.get("valuation"):
            self.debug_log_no_data("SeekingAlpha", "Could not fetch fundamental/estimates data")
        else:
            self.debug_log("SeekingAlpha Data", sa_data)

    def reason(self):
        sa_data = self._state["data"].get("seekingalpha", {})
        signal, confidence = self._compute_signal(sa_data)
        self._state["reasoning"] = {
            "signal": signal,
            "confidence": confidence,
            "earnings_estimates": sa_data.get("earnings_estimates", {}),
            "revenue_estimates": sa_data.get("revenue_estimates", {}),
            "growth_estimates": sa_data.get("growth_estimates", {}),
            "earnings_history": sa_data.get("earnings_history", []),
            "eps_trend": sa_data.get("eps_trend", {}),
            "valuation": sa_data.get("valuation", {}),
        }

    def act(self):
        sa_data = self._state["data"].get("seekingalpha", {})
        reasoning = self._state["reasoning"]

        if self.kafka_enabled:
            self._publish_to_kafka(sa_data)
        if self.qdrant_enabled:
            self._store_in_qdrant(sa_data)

        ee = reasoning.get("earnings_estimates", {})
        eps_trend = reasoning.get("eps_trend", {})
        valuation = reasoning.get("valuation", {})
        history = reasoning.get("earnings_history", [])

        # Build summary string
        eps_avg = ee.get("avg")
        eps_growth = ee.get("growth")
        eps_str = f"EPS est={eps_avg}" if eps_avg is not None else "EPS est=N/A"
        growth_str = f"growth={eps_growth:.1%}" if eps_growth is not None else "growth=N/A"
        beats = sum(1 for h in history if h.get("surprise_percent") is not None and h["surprise_percent"] > 0)
        total_q = len([h for h in history if h.get("surprise_percent") is not None])
        beats_str = f"beats={beats}/{total_q}" if total_q > 0 else "beats=N/A"
        trailing_pe = valuation.get("trailing_pe")
        pe_str = f"P/E={trailing_pe:.1f}" if trailing_pe is not None else "P/E=N/A"

        output = AgentOutput(
            agent_name="SeekingAlphaAgent",
            ticker=self.ticker,
            signal=reasoning["signal"],
            confidence=reasoning["confidence"],
            summary=f"{eps_str}, {growth_str}, {beats_str}, {pe_str}",
            data={
                "earnings_estimates": ee,
                "revenue_estimates": reasoning.get("revenue_estimates", {}),
                "growth_estimates": reasoning.get("growth_estimates", {}),
                "earnings_history": history,
                "eps_trend": eps_trend,
                "valuation": valuation,
            },
        )
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict:
        return self._state.get("actions", {})
