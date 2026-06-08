"""TipRanks agent that fetches analyst consensus data via yfinance."""

import os
import sys
import uuid
from datetime import datetime, timezone

import yfinance as yf

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, TipRanksMessage


class TipRanksAgent(AgenticAIBase):
    """Fetches analyst recommendations, price targets, and upgrades/downgrades from yfinance."""

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

        self.register_tool("fetch_tipranks_data", self._fetch_tipranks_data,
                           "Fetch analyst consensus data from yfinance")

        # Check for TipRanks API key
        if not os.getenv("TIPRANKS_API_KEY"):
            print(f"  [TipRanksAgent] No TIPRANKS_API_KEY found. Using yfinance proxy (free alternative to $30-50/month TipRanks subscription)", file=sys.stderr)

        if self.kafka_enabled:
            self.register_tool("publish_to_kafka", self._publish_to_kafka,
                               "Publish analyst consensus data to Kafka")
        if self.qdrant_enabled:
            self.register_tool("store_in_qdrant", self._store_in_qdrant,
                               "Store analyst consensus embeddings in Qdrant")

    # -- Tool implementations --------------------------------------------------

    def _fetch_tipranks_data(self) -> dict:
        """Fetch analyst consensus data from yfinance."""
        tk = yf.Ticker(self.ticker)
        data = {
            "consensus": {},
            "recommendation_mean": None,
            "recommendation_key": "",
            "price_targets": {},
            "recent_actions": [],
        }

        # Consensus counts from recommendations
        try:
            recs = tk.recommendations
            if recs is not None and not recs.empty:
                row = recs.iloc[-1]
                data["consensus"] = {
                    "strong_buy": int(row.get("strongBuy", 0)),
                    "buy": int(row.get("buy", 0)),
                    "hold": int(row.get("hold", 0)),
                    "sell": int(row.get("sell", 0)),
                    "strong_sell": int(row.get("strongSell", 0)),
                }
                data["consensus"]["total"] = sum(data["consensus"].values())
        except Exception:
            pass

        # Recommendation mean and key from info
        try:
            info = tk.info
            data["recommendation_mean"] = info.get("recommendationMean")
            data["recommendation_key"] = info.get("recommendationKey", "")
        except Exception:
            pass

        # Price targets
        try:
            targets = tk.analyst_price_targets
            if targets:
                data["price_targets"] = {
                    "high": targets.get("high"),
                    "low": targets.get("low"),
                    "mean": targets.get("mean"),
                    "median": targets.get("median"),
                }
        except Exception:
            pass

        # Recent upgrades/downgrades (last 10)
        try:
            ud = tk.upgrades_downgrades
            if ud is not None and not ud.empty:
                recent = ud.head(10)
                actions = []
                for idx, row in recent.iterrows():
                    actions.append({
                        "firm": row.get("Firm", ""),
                        "to_grade": row.get("ToGrade", ""),
                        "from_grade": row.get("FromGrade", ""),
                        "action": row.get("Action", ""),
                        "date": str(idx) if idx is not None else "",
                    })
                data["recent_actions"] = actions
        except Exception:
            pass

        return data

    def _publish_to_kafka(self, tipranks_data: dict) -> int:
        if not self.kafka_producer:
            return 0
        msg = TipRanksMessage(
            ticker=self.ticker,
            consensus=tipranks_data.get("consensus", {}),
            recommendation_mean=tipranks_data.get("recommendation_mean"),
            recommendation_key=tipranks_data.get("recommendation_key", ""),
            price_targets=tipranks_data.get("price_targets", {}),
            recent_actions=tipranks_data.get("recent_actions", []),
        )
        self.kafka_producer.send(Config.KAFKA_TOPIC_TIPRANKS, key=self.ticker,
                                 value=msg.model_dump_json())
        return 1

    def _store_in_qdrant(self, tipranks_data: dict) -> int:
        if not self.qdrant_store or not self.embedder:
            return 0
        consensus = tipranks_data.get("consensus", {})
        rec_mean = tipranks_data.get("recommendation_mean")
        rec_key = tipranks_data.get("recommendation_key", "")
        targets = tipranks_data.get("price_targets", {})
        summary = (
            f"Analyst consensus for {self.ticker}: "
            f"Recommendation {rec_mean} ({rec_key}). "
            f"Strong Buy={consensus.get('strong_buy', 0)}, "
            f"Buy={consensus.get('buy', 0)}, "
            f"Hold={consensus.get('hold', 0)}, "
            f"Sell={consensus.get('sell', 0)}, "
            f"Strong Sell={consensus.get('strong_sell', 0)}. "
            f"Target mean=${targets.get('mean', 'N/A')}."
        )
        embeddings = self.embedder.embed([summary])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.ticker}:tipranks"))
        points = [{
            "id": point_id,
            "vector": embeddings[0],
            "payload": {
                "ticker": self.ticker,
                "consensus": consensus,
                "recommendation_mean": rec_mean,
                "recommendation_key": rec_key,
                "price_targets": targets,
            },
        }]
        self.qdrant_store.upsert(Config.QDRANT_COLLECTION_TIPRANKS, points)
        return 1

    # -- Signal mapping --------------------------------------------------------

    def _compute_signal(self, tipranks_data: dict) -> tuple[str, float]:
        """Map recommendationMean to signal and confidence, adjusted by recent actions."""
        rec_mean = tipranks_data.get("recommendation_mean")
        if rec_mean is None:
            return "NEUTRAL", 0.0

        if rec_mean <= 1.5:
            signal, confidence = "BULLISH", 0.9
        elif rec_mean <= 2.5:
            signal, confidence = "BULLISH", 0.7
        elif rec_mean <= 3.5:
            signal, confidence = "NEUTRAL", 0.5
        elif rec_mean <= 4.5:
            signal, confidence = "BEARISH", 0.7
        else:
            signal, confidence = "BEARISH", 0.9

        # Adjust by recent upgrades vs downgrades
        actions = tipranks_data.get("recent_actions", [])
        upgrades = sum(1 for a in actions if a.get("action", "").lower() in ("up", "init"))
        downgrades = sum(1 for a in actions if a.get("action", "").lower() == "down")
        if upgrades > downgrades:
            confidence = min(1.0, confidence + 0.05)
        elif downgrades > upgrades:
            confidence = max(0.0, confidence - 0.05)

        return signal, confidence

    # -- Agentic lifecycle -----------------------------------------------------

    def plan(self):
        self._state["plan"] = [
            "Fetch analyst consensus data from yfinance",
            "Publish to Kafka (if enabled)",
            "Store embeddings in Qdrant (if enabled)",
        ]

    def perceive(self):
        tipranks_data = self.use_tool("fetch_tipranks_data")
        self._state["data"]["tipranks"] = tipranks_data
        if not tipranks_data.get("consensus") and tipranks_data.get("recommendation_mean") is None:
            self.debug_log_no_data("TipRanks", "Could not fetch analyst consensus data")
        else:
            self.debug_log("TipRanks Data", tipranks_data)

    def reason(self):
        tipranks_data = self._state["data"].get("tipranks", {})
        signal, confidence = self._compute_signal(tipranks_data)
        self._state["reasoning"] = {
            "signal": signal,
            "confidence": confidence,
            "consensus": tipranks_data.get("consensus", {}),
            "recommendation_mean": tipranks_data.get("recommendation_mean"),
            "recommendation_key": tipranks_data.get("recommendation_key", ""),
            "price_targets": tipranks_data.get("price_targets", {}),
            "recent_actions": tipranks_data.get("recent_actions", []),
        }

    def act(self):
        tipranks_data = self._state["data"].get("tipranks", {})
        reasoning = self._state["reasoning"]

        if self.kafka_enabled:
            self._publish_to_kafka(tipranks_data)
        if self.qdrant_enabled:
            self._store_in_qdrant(tipranks_data)

        rec_mean = reasoning.get("recommendation_mean")
        rec_key = reasoning.get("recommendation_key", "")
        rec_str = f"{rec_mean} ({rec_key})" if rec_mean else "N/A"
        targets = reasoning.get("price_targets", {})
        target_mean = targets.get("mean")
        target_str = f"${target_mean}" if target_mean else "N/A"
        consensus = reasoning.get("consensus", {})
        total = consensus.get("total", 0)

        output = AgentOutput(
            agent_name="TipRanksAgent",
            ticker=self.ticker,
            signal=reasoning["signal"],
            confidence=reasoning["confidence"],
            summary=f"Analyst consensus={rec_str}, Analysts={total}, Target={target_str}",
            data={
                "consensus": consensus,
                "recommendation_mean": reasoning.get("recommendation_mean"),
                "recommendation_key": reasoning.get("recommendation_key", ""),
                "price_targets": targets,
                "recent_actions": reasoning.get("recent_actions", []),
            },
        )
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict:
        return self._state.get("actions", {})
