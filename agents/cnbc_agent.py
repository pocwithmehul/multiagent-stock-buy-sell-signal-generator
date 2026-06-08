"""CNBC agent that analyzes market news and trading sentiment via yfinance proxy."""

import uuid
import yfinance as yf
from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, CNBCMessage


class CNBCAgent(AgenticAIBase):
    """Analyzes CNBC-style market news and trading sentiment using yfinance proxy."""

    def __init__(self, ticker: str, kafka_producer=None, kafka_enabled: bool = False,
                 qdrant_store=None, qdrant_enabled: bool = False, embedder=None):
        super().__init__()
        self.ticker = ticker.upper()
        self.kafka_producer = kafka_producer
        self.kafka_enabled = kafka_enabled
        self.qdrant_store = qdrant_store
        self.qdrant_enabled = qdrant_enabled
        self.embedder = embedder
        self.register_tool("fetch_cnbc_data", self._fetch_cnbc_data, "Fetch CNBC-style market data")

    @staticmethod
    def _safe_float(val):
        if val is None: return None
        try:
            f = float(val)
            return None if f != f else f
        except: return None

    def _fetch_cnbc_data(self) -> dict:
        """Fetch market news and trading sentiment data."""
        tk = yf.Ticker(self.ticker)
        data = {"market_pulse": {}, "trading_activity": {}, "news_sentiment": {}, "analyst_views": {}}

        try:
            info = tk.info
            news = tk.news or []
            hist = tk.history(period="5d")

            # Market pulse - real-time trading focus
            current = self._safe_float(info.get("currentPrice")) or self._safe_float(info.get("regularMarketPrice"))
            prev_close = self._safe_float(info.get("previousClose"))
            day_change = ((current - prev_close) / prev_close) if current and prev_close else None

            data["market_pulse"] = {
                "current_price": current,
                "previous_close": prev_close,
                "day_change_pct": day_change,
                "day_high": self._safe_float(info.get("dayHigh")),
                "day_low": self._safe_float(info.get("dayLow")),
                "bid": self._safe_float(info.get("bid")),
                "ask": self._safe_float(info.get("ask")),
                "spread_pct": ((info.get("ask", 0) - info.get("bid", 0)) / info.get("bid", 1)) if info.get("bid") else None,
            }

            # Trading activity - volume focus
            volume = self._safe_float(info.get("volume"))
            avg_volume = self._safe_float(info.get("averageVolume"))
            data["trading_activity"] = {
                "volume": volume,
                "avg_volume": avg_volume,
                "volume_ratio": (volume / avg_volume) if volume and avg_volume else None,
                "market_cap": self._safe_float(info.get("marketCap")),
                "shares_outstanding": self._safe_float(info.get("sharesOutstanding")),
            }

            # News sentiment from headlines
            bullish_words = ['surge', 'jump', 'rally', 'gain', 'soar', 'beat', 'upgrade', 'buy', 'record', 'breakthrough']
            bearish_words = ['fall', 'drop', 'plunge', 'crash', 'miss', 'downgrade', 'sell', 'cut', 'warning', 'concern']

            bullish_count = 0
            bearish_count = 0
            headlines = []

            for article in news[:15]:
                title = article.get('title', '').lower()
                headlines.append(article.get('title', '')[:80])
                bullish_count += sum(1 for w in bullish_words if w in title)
                bearish_count += sum(1 for w in bearish_words if w in title)

            total_signals = bullish_count + bearish_count
            data["news_sentiment"] = {
                "headline_count": len(news),
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "sentiment_ratio": (bullish_count - bearish_count) / total_signals if total_signals > 0 else 0,
                "recent_headlines": headlines[:5],
            }

            # Analyst views
            data["analyst_views"] = {
                "recommendation": info.get("recommendationKey", ""),
                "target_mean": self._safe_float(info.get("targetMeanPrice")),
                "target_high": self._safe_float(info.get("targetHighPrice")),
                "target_low": self._safe_float(info.get("targetLowPrice")),
                "num_analysts": info.get("numberOfAnalystOpinions"),
                "upside_potential": ((info.get("targetMeanPrice", 0) - current) / current) if current and info.get("targetMeanPrice") else None,
            }

        except: pass
        return data

    def _compute_signal(self, data: dict) -> tuple[str, float]:
        scores = []

        # Market pulse - day momentum (weight 0.3)
        mp = data.get("market_pulse", {})
        day_change = mp.get("day_change_pct")
        if day_change is not None:
            scores.append(("momentum", 0.3, 0.5 if day_change > 0.02 else 0.25 if day_change > 0 else -0.25 if day_change < -0.02 else 0.0))

        # News sentiment (weight 0.35)
        ns = data.get("news_sentiment", {})
        sent_ratio = ns.get("sentiment_ratio")
        if sent_ratio is not None:
            scores.append(("news", 0.35, sent_ratio))

        # Analyst upside (weight 0.35)
        av = data.get("analyst_views", {})
        upside = av.get("upside_potential")
        if upside is not None:
            scores.append(("analyst", 0.35, 0.5 if upside > 0.15 else 0.25 if upside > 0.05 else -0.25 if upside < 0 else 0.0))

        if not scores: return "NEUTRAL", 0.0
        total_weight = sum(w for _, w, _ in scores)
        composite = sum(w * s / total_weight for _, w, s in scores)
        if composite > 0.25: return "BULLISH", min(0.95, 0.5 + composite * 0.4)
        elif composite < -0.25: return "BEARISH", min(0.95, 0.5 + abs(composite) * 0.4)
        return "NEUTRAL", 0.5

    def plan(self): self._state["plan"] = ["Fetch CNBC-style market data"]
    def perceive(self):
        cnbc_data = self.use_tool("fetch_cnbc_data")
        self._state["data"]["cnbc"] = cnbc_data
        if not cnbc_data.get("market_pulse") and not cnbc_data.get("news_sentiment"):
            self.debug_log_no_data("CNBC", "Could not fetch market news/trading data")
        else:
            self.debug_log("CNBC Data", cnbc_data)
    def reason(self):
        data = self._state["data"].get("cnbc", {})
        signal, confidence = self._compute_signal(data)
        self._state["reasoning"] = {"signal": signal, "confidence": confidence, **data}

    def act(self):
        data = self._state["data"].get("cnbc", {})
        reasoning = self._state["reasoning"]
        mp = reasoning.get("market_pulse", {})
        ns = reasoning.get("news_sentiment", {})
        day_chg = mp.get("day_change_pct")
        day_str = f"Day={day_chg:+.1%}" if day_chg is not None else "Day=N/A"
        sent = ns.get("sentiment_ratio")
        sent_str = f"News={sent:+.2f}" if sent is not None else "News=N/A"
        output = AgentOutput(agent_name="CNBCAgent", ticker=self.ticker, signal=reasoning["signal"],
                            confidence=reasoning["confidence"], summary=f"{day_str}, {sent_str}", data=data)
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict: return self._state.get("actions", {})
