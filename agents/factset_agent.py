"""FactSet agent that provides institutional-grade financial analytics via yfinance."""

import os
import sys
import uuid
from datetime import datetime, timezone

import yfinance as yf

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, FactSetMessage


class FactSetAgent(AgenticAIBase):
    """Analyzes institutional-grade financial data and analytics (FactSet style)."""

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

        self.register_tool("fetch_factset_data", self._fetch_factset_data,
                           "Fetch institutional analytics from yfinance")

        # Check for FactSet API key
        if not os.getenv("FACTSET_API_KEY"):
            print(f"  [FactSetAgent] No FACTSET_API_KEY found. Using yfinance proxy (free alternative to $12,000+/year FactSet subscription)", file=sys.stderr)

        if self.kafka_enabled:
            self.register_tool("publish_to_kafka", self._publish_to_kafka, "Publish to Kafka")
        if self.qdrant_enabled:
            self.register_tool("store_in_qdrant", self._store_in_qdrant, "Store in Qdrant")

    @staticmethod
    def _safe_float(val) -> float | None:
        if val is None:
            return None
        try:
            f = float(val)
            return None if f != f else f
        except (ValueError, TypeError):
            return None

    def _fetch_factset_data(self) -> dict:
        """Fetch institutional-grade financial analytics."""
        tk = yf.Ticker(self.ticker)
        data = {"earnings_quality": {}, "estimate_revisions": {}, "ownership_flow": {}, "valuation_metrics": {}}

        try:
            info = tk.info

            # Earnings quality metrics
            data["earnings_quality"] = {
                "trailing_eps": self._safe_float(info.get("trailingEps")),
                "forward_eps": self._safe_float(info.get("forwardEps")),
                "peg_ratio": self._safe_float(info.get("pegRatio")),
                "earnings_growth": self._safe_float(info.get("earningsGrowth")),
                "revenue_growth": self._safe_float(info.get("revenueGrowth")),
                "profit_margin": self._safe_float(info.get("profitMargins")),
                "operating_margin": self._safe_float(info.get("operatingMargins")),
            }

            # Estimate revisions (EPS trend as proxy)
            try:
                eps_trend = tk.eps_trend
                if eps_trend is not None and not eps_trend.empty:
                    row = eps_trend.iloc[0]
                    current = self._safe_float(row.get("current"))
                    ago_7d = self._safe_float(row.get("7daysAgo"))
                    ago_30d = self._safe_float(row.get("30daysAgo"))
                    ago_90d = self._safe_float(row.get("90daysAgo"))

                    revision_7d = ((current - ago_7d) / ago_7d) if current and ago_7d else None
                    revision_30d = ((current - ago_30d) / ago_30d) if current and ago_30d else None

                    data["estimate_revisions"] = {
                        "current_estimate": current,
                        "revision_7d": revision_7d,
                        "revision_30d": revision_30d,
                        "estimate_90d_ago": ago_90d,
                    }
            except Exception:
                pass

            # Ownership flow
            data["ownership_flow"] = {
                "institutional_holders_pct": self._safe_float(info.get("heldPercentInstitutions")),
                "insider_holders_pct": self._safe_float(info.get("heldPercentInsiders")),
                "short_ratio": self._safe_float(info.get("shortRatio")),
                "short_pct_float": self._safe_float(info.get("shortPercentOfFloat")),
                "float_shares": self._safe_float(info.get("floatShares")),
            }

            # Valuation metrics
            ev = self._safe_float(info.get("enterpriseValue"))
            mkt_cap = self._safe_float(info.get("marketCap"))
            data["valuation_metrics"] = {
                "market_cap": mkt_cap,
                "enterprise_value": ev,
                "ev_to_revenue": self._safe_float(info.get("enterpriseToRevenue")),
                "ev_to_ebitda": self._safe_float(info.get("enterpriseToEbitda")),
                "price_to_book": self._safe_float(info.get("priceToBook")),
                "price_to_sales": self._safe_float(info.get("priceToSalesTrailing12Months")),
                "trailing_pe": self._safe_float(info.get("trailingPE")),
                "forward_pe": self._safe_float(info.get("forwardPE")),
            }

        except Exception:
            pass

        return data

    def _publish_to_kafka(self, data: dict) -> int:
        if not self.kafka_producer:
            return 0
        msg = FactSetMessage(ticker=self.ticker, **data)
        self.kafka_producer.send(Config.KAFKA_TOPIC_FACTSET, key=self.ticker, value=msg.model_dump_json())
        return 1

    def _store_in_qdrant(self, data: dict) -> int:
        if not self.qdrant_store or not self.embedder:
            return 0
        eq = data.get("earnings_quality", {})
        summary = f"FactSet analysis for {self.ticker}: EPS Growth={eq.get('earnings_growth', 'N/A')}, Margin={eq.get('profit_margin', 'N/A')}."
        embeddings = self.embedder.embed([summary])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.ticker}:factset"))
        self.qdrant_store.upsert(Config.QDRANT_COLLECTION_FACTSET, [{"id": point_id, "vector": embeddings[0], "payload": {"ticker": self.ticker, **data}}])
        return 1

    def _compute_signal(self, data: dict) -> tuple[str, float]:
        scores = []

        # Earnings quality (weight 0.4)
        eq = data.get("earnings_quality", {})
        eg = eq.get("earnings_growth")
        pm = eq.get("profit_margin")
        if eg is not None or pm is not None:
            eq_score = 0.0
            if eg is not None:
                eq_score += 0.5 if eg > 0.15 else 0.25 if eg > 0.05 else -0.25 if eg < 0 else 0.0
            if pm is not None:
                eq_score += 0.5 if pm > 0.15 else 0.25 if pm > 0.08 else -0.25 if pm < 0 else 0.0
            scores.append(("earnings_quality", 0.4, max(-1, min(1, eq_score))))

        # Estimate revisions (weight 0.35)
        er = data.get("estimate_revisions", {})
        rev_30d = er.get("revision_30d")
        if rev_30d is not None:
            rev_score = 1.0 if rev_30d > 0.05 else 0.5 if rev_30d > 0 else -0.5 if rev_30d > -0.05 else -1.0
            scores.append(("revisions", 0.35, rev_score))

        # Short interest (weight 0.25)
        of = data.get("ownership_flow", {})
        short_pct = of.get("short_pct_float")
        if short_pct is not None:
            short_score = 0.5 if short_pct < 0.03 else 0.0 if short_pct < 0.08 else -0.5 if short_pct < 0.15 else -1.0
            scores.append(("short_interest", 0.25, short_score))

        if not scores:
            return "NEUTRAL", 0.0
        total_weight = sum(w for _, w, _ in scores)
        composite = sum(w * s / total_weight for _, w, s in scores)
        if composite > 0.3:
            return "BULLISH", min(0.95, 0.5 + composite * 0.4)
        elif composite < -0.3:
            return "BEARISH", min(0.95, 0.5 + abs(composite) * 0.4)
        return "NEUTRAL", 0.5

    def plan(self):
        self._state["plan"] = ["Fetch FactSet-style data", "Publish/Store if enabled"]

    def perceive(self):
        fs_data = self.use_tool("fetch_factset_data")
        self._state["data"]["factset"] = fs_data
        if not fs_data.get("earnings_quality") and not fs_data.get("valuation_metrics"):
            self.debug_log_no_data("FactSet", "Could not fetch institutional analytics data")
        else:
            self.debug_log("FactSet Data", fs_data)

    def reason(self):
        data = self._state["data"].get("factset", {})
        signal, confidence = self._compute_signal(data)
        self._state["reasoning"] = {"signal": signal, "confidence": confidence, **data}

    def act(self):
        data = self._state["data"].get("factset", {})
        reasoning = self._state["reasoning"]
        if self.kafka_enabled:
            self._publish_to_kafka(data)
        if self.qdrant_enabled:
            self._store_in_qdrant(data)

        eq = reasoning.get("earnings_quality", {})
        er = reasoning.get("estimate_revisions", {})
        eg = eq.get("earnings_growth")
        rev = er.get("revision_30d")
        eg_str = f"EG={eg:.0%}" if eg is not None else "EG=N/A"
        rev_str = f"Rev30d={rev:+.1%}" if rev is not None else "Rev30d=N/A"

        output = AgentOutput(agent_name="FactSetAgent", ticker=self.ticker, signal=reasoning["signal"],
                            confidence=reasoning["confidence"], summary=f"{eg_str}, {rev_str}", data=data)
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict:
        return self._state.get("actions", {})
