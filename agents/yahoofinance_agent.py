"""Yahoo Finance agent that analyzes options, trading activity, and dividend metrics via yfinance."""

import uuid
from datetime import datetime, timezone

import yfinance as yf

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, YahooFinanceMessage


class YahooFinanceAgent(AgenticAIBase):
    """Analyzes options sentiment, trading activity, and dividend metrics from yfinance."""

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

        self.register_tool("fetch_yahoofinance_data", self._fetch_yahoofinance_data,
                           "Fetch options/trading/dividend data from yfinance")
        if self.kafka_enabled:
            self.register_tool("publish_to_kafka", self._publish_to_kafka,
                               "Publish Yahoo Finance data to Kafka")
        if self.qdrant_enabled:
            self.register_tool("store_in_qdrant", self._store_in_qdrant,
                               "Store Yahoo Finance data embeddings in Qdrant")

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

    @staticmethod
    def _safe_int(val) -> int | None:
        """Convert a value to int, returning None for NaN/None."""
        if val is None:
            return None
        try:
            f = float(val)
            if f != f:  # NaN check
                return None
            return int(f)
        except (ValueError, TypeError):
            return None

    # -- Tool implementations --------------------------------------------------

    def _fetch_yahoofinance_data(self) -> dict:
        """Fetch options, trading activity, and dividend data from yfinance."""
        tk = yf.Ticker(self.ticker)
        data = {
            "options_sentiment": {},
            "trading_activity": {},
            "dividend_metrics": {},
            "price_performance": {},
        }

        try:
            info = tk.info

            # Options sentiment (put/call ratio, implied volatility)
            try:
                exp_dates = tk.options
                if exp_dates:
                    # Get nearest expiration
                    opt = tk.option_chain(exp_dates[0])
                    calls = opt.calls
                    puts = opt.puts

                    # Calculate put/call ratio by open interest
                    total_call_oi = calls['openInterest'].sum() if 'openInterest' in calls.columns else 0
                    total_put_oi = puts['openInterest'].sum() if 'openInterest' in puts.columns else 0
                    put_call_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else None

                    # Calculate put/call ratio by volume
                    total_call_vol = calls['volume'].sum() if 'volume' in calls.columns else 0
                    total_put_vol = puts['volume'].sum() if 'volume' in puts.columns else 0
                    put_call_vol_ratio = total_put_vol / total_call_vol if total_call_vol > 0 else None

                    # Average implied volatility (ATM options)
                    current_price = self._safe_float(info.get("currentPrice")) or self._safe_float(info.get("regularMarketPrice"))
                    if current_price:
                        # Find ATM calls and puts (within 5% of current price)
                        atm_calls = calls[(calls['strike'] >= current_price * 0.95) & (calls['strike'] <= current_price * 1.05)]
                        atm_puts = puts[(puts['strike'] >= current_price * 0.95) & (puts['strike'] <= current_price * 1.05)]

                        call_iv = atm_calls['impliedVolatility'].mean() if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns else None
                        put_iv = atm_puts['impliedVolatility'].mean() if not atm_puts.empty and 'impliedVolatility' in atm_puts.columns else None
                        avg_iv = None
                        if call_iv is not None and put_iv is not None:
                            avg_iv = (call_iv + put_iv) / 2
                        elif call_iv is not None:
                            avg_iv = call_iv
                        elif put_iv is not None:
                            avg_iv = put_iv
                    else:
                        avg_iv = None

                    data["options_sentiment"] = {
                        "put_call_oi_ratio": self._safe_float(put_call_ratio),
                        "put_call_volume_ratio": self._safe_float(put_call_vol_ratio),
                        "total_call_open_interest": self._safe_int(total_call_oi),
                        "total_put_open_interest": self._safe_int(total_put_oi),
                        "total_call_volume": self._safe_int(total_call_vol),
                        "total_put_volume": self._safe_int(total_put_vol),
                        "avg_implied_volatility": self._safe_float(avg_iv),
                        "nearest_expiration": exp_dates[0] if exp_dates else None,
                    }
            except Exception:
                pass

            # Trading activity
            current_volume = self._safe_int(info.get("volume")) or self._safe_int(info.get("regularMarketVolume"))
            avg_volume = self._safe_int(info.get("averageVolume"))
            avg_volume_10d = self._safe_int(info.get("averageVolume10days"))

            volume_ratio = None
            if current_volume and avg_volume:
                volume_ratio = current_volume / avg_volume

            bid = self._safe_float(info.get("bid"))
            ask = self._safe_float(info.get("ask"))
            spread = None
            spread_pct = None
            if bid and ask and bid > 0:
                spread = ask - bid
                mid = (ask + bid) / 2
                spread_pct = spread / mid if mid > 0 else None

            data["trading_activity"] = {
                "current_volume": current_volume,
                "average_volume": avg_volume,
                "average_volume_10d": avg_volume_10d,
                "volume_ratio": self._safe_float(volume_ratio),
                "bid": bid,
                "ask": ask,
                "bid_size": self._safe_int(info.get("bidSize")),
                "ask_size": self._safe_int(info.get("askSize")),
                "spread": self._safe_float(spread),
                "spread_pct": self._safe_float(spread_pct),
            }

            # Dividend metrics
            data["dividend_metrics"] = {
                "dividend_rate": self._safe_float(info.get("dividendRate")),
                "dividend_yield": self._safe_float(info.get("dividendYield")),
                "trailing_annual_dividend_rate": self._safe_float(info.get("trailingAnnualDividendRate")),
                "trailing_annual_dividend_yield": self._safe_float(info.get("trailingAnnualDividendYield")),
                "payout_ratio": self._safe_float(info.get("payoutRatio")),
                "five_year_avg_dividend_yield": self._safe_float(info.get("fiveYearAvgDividendYield")),
                "last_dividend_value": self._safe_float(info.get("lastDividendValue")),
            }

            # Price performance (52-week)
            data["price_performance"] = {
                "current_price": self._safe_float(info.get("currentPrice")) or self._safe_float(info.get("regularMarketPrice")),
                "previous_close": self._safe_float(info.get("previousClose")),
                "open": self._safe_float(info.get("open")),
                "day_low": self._safe_float(info.get("dayLow")),
                "day_high": self._safe_float(info.get("dayHigh")),
                "fifty_two_week_low": self._safe_float(info.get("fiftyTwoWeekLow")),
                "fifty_two_week_high": self._safe_float(info.get("fiftyTwoWeekHigh")),
                "fifty_two_week_low_change_pct": self._safe_float(info.get("fiftyTwoWeekLowChangePercent")),
                "fifty_two_week_high_change_pct": self._safe_float(info.get("fiftyTwoWeekHighChangePercent")),
            }

        except Exception:
            pass

        return data

    def _publish_to_kafka(self, yf_data: dict) -> int:
        if not self.kafka_producer:
            return 0
        msg = YahooFinanceMessage(
            ticker=self.ticker,
            options_sentiment=yf_data.get("options_sentiment", {}),
            trading_activity=yf_data.get("trading_activity", {}),
            dividend_metrics=yf_data.get("dividend_metrics", {}),
            price_performance=yf_data.get("price_performance", {}),
        )
        self.kafka_producer.send(Config.KAFKA_TOPIC_YAHOOFINANCE, key=self.ticker,
                                 value=msg.model_dump_json())
        return 1

    def _store_in_qdrant(self, yf_data: dict) -> int:
        if not self.qdrant_store or not self.embedder:
            return 0
        opts = yf_data.get("options_sentiment", {})
        trading = yf_data.get("trading_activity", {})
        div = yf_data.get("dividend_metrics", {})

        pc_ratio = opts.get('put_call_oi_ratio')
        pc_str = f"{pc_ratio:.2f}" if pc_ratio is not None else "N/A"
        iv = opts.get('avg_implied_volatility')
        iv_str = f"{iv:.1%}" if iv is not None else "N/A"
        vol_ratio = trading.get('volume_ratio')
        vol_str = f"{vol_ratio:.2f}x" if vol_ratio is not None else "N/A"
        div_yield = div.get('dividend_yield')
        div_str = f"{div_yield:.2%}" if div_yield is not None else "N/A"

        summary = (
            f"Yahoo Finance data for {self.ticker}: "
            f"Put/Call={pc_str}, IV={iv_str}, "
            f"Volume Ratio={vol_str}, Div Yield={div_str}."
        )
        embeddings = self.embedder.embed([summary])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.ticker}:yahoofinance"))
        points = [{
            "id": point_id,
            "vector": embeddings[0],
            "payload": {
                "ticker": self.ticker,
                "options_sentiment": opts,
                "trading_activity": trading,
                "dividend_metrics": div,
            },
        }]
        self.qdrant_store.upsert(Config.QDRANT_COLLECTION_YAHOOFINANCE, points)
        return 1

    # -- Signal mapping --------------------------------------------------------

    def _compute_signal(self, yf_data: dict) -> tuple[str, float]:
        """Composite score from options sentiment, volume, and dividend stability."""
        scores = []

        # Factor 1: Options Sentiment - Put/Call Ratio (weight 0.4)
        # High put/call ratio = bearish sentiment, low = bullish
        opts = yf_data.get("options_sentiment", {})
        pc_ratio = opts.get("put_call_oi_ratio")
        if pc_ratio is not None:
            if pc_ratio < 0.5:  # Very bullish options flow
                opts_score = 1.0
            elif pc_ratio < 0.7:  # Moderately bullish
                opts_score = 0.5
            elif pc_ratio < 1.0:  # Neutral to slightly bullish
                opts_score = 0.0
            elif pc_ratio < 1.3:  # Moderately bearish
                opts_score = -0.5
            else:  # Very bearish options flow
                opts_score = -1.0
            scores.append(("options_sentiment", 0.4, opts_score))

        # Factor 2: Volume Analysis (weight 0.3)
        # High volume relative to average can indicate momentum
        trading = yf_data.get("trading_activity", {})
        vol_ratio = trading.get("volume_ratio")
        if vol_ratio is not None:
            # Volume alone doesn't indicate direction, but we look at price context
            perf = yf_data.get("price_performance", {})
            current = perf.get("current_price")
            prev_close = perf.get("previous_close")

            if current and prev_close:
                daily_return = (current - prev_close) / prev_close
                # High volume + positive return = bullish, high volume + negative = bearish
                if vol_ratio > 1.5:  # Above average volume
                    if daily_return > 0.01:  # Up more than 1%
                        vol_score = 1.0
                    elif daily_return > 0:
                        vol_score = 0.5
                    elif daily_return > -0.01:
                        vol_score = -0.25
                    else:
                        vol_score = -1.0
                elif vol_ratio > 0.8:  # Normal volume
                    vol_score = 0.0
                else:  # Low volume
                    vol_score = -0.25  # Low volume can indicate lack of conviction
                scores.append(("volume_momentum", 0.3, vol_score))

        # Factor 3: Implied Volatility (weight 0.15)
        # High IV can indicate uncertainty/fear
        iv = opts.get("avg_implied_volatility")
        if iv is not None:
            if iv < 0.20:  # Low IV, calm market
                iv_score = 0.5
            elif iv < 0.30:  # Normal IV
                iv_score = 0.0
            elif iv < 0.50:  # Elevated IV
                iv_score = -0.25
            else:  # High IV, fear/uncertainty
                iv_score = -0.5
            scores.append(("implied_volatility", 0.15, iv_score))

        # Factor 4: Dividend Stability (weight 0.15)
        div = yf_data.get("dividend_metrics", {})
        payout_ratio = div.get("payout_ratio")
        # Use trailing annual yield as it's more reliable
        div_yield = div.get("trailing_annual_dividend_yield") or div.get("dividend_yield")
        if payout_ratio is not None or div_yield is not None:
            div_score = 0.0

            if payout_ratio is not None:
                if 0.2 <= payout_ratio <= 0.6:  # Healthy payout ratio
                    div_score += 0.5
                elif payout_ratio < 0.2:  # Low payout, room to grow
                    div_score += 0.25
                elif payout_ratio <= 0.8:  # High but sustainable
                    div_score += 0.0
                else:  # Unsustainable payout
                    div_score -= 0.5

            if div_yield is not None and div_yield > 0:
                if div_yield > 0.02:  # >2% yield
                    div_score += 0.25

            div_score = max(-1.0, min(1.0, div_score))
            scores.append(("dividend_stability", 0.15, div_score))

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
            "Fetch options/trading/dividend data from yfinance",
            "Publish to Kafka (if enabled)",
            "Store embeddings in Qdrant (if enabled)",
        ]

    def perceive(self):
        yf_data = self.use_tool("fetch_yahoofinance_data")
        self._state["data"]["yahoofinance"] = yf_data
        if not yf_data.get("options_sentiment") and not yf_data.get("trading_activity"):
            self.debug_log_no_data("YahooFinance", "Could not fetch options/trading data")
        else:
            self.debug_log("YahooFinance Data", yf_data)

    def reason(self):
        yf_data = self._state["data"].get("yahoofinance", {})
        signal, confidence = self._compute_signal(yf_data)
        self._state["reasoning"] = {
            "signal": signal,
            "confidence": confidence,
            "options_sentiment": yf_data.get("options_sentiment", {}),
            "trading_activity": yf_data.get("trading_activity", {}),
            "dividend_metrics": yf_data.get("dividend_metrics", {}),
            "price_performance": yf_data.get("price_performance", {}),
        }

    def act(self):
        yf_data = self._state["data"].get("yahoofinance", {})
        reasoning = self._state["reasoning"]

        if self.kafka_enabled:
            self._publish_to_kafka(yf_data)
        if self.qdrant_enabled:
            self._store_in_qdrant(yf_data)

        opts = reasoning.get("options_sentiment", {})
        trading = reasoning.get("trading_activity", {})
        div = reasoning.get("dividend_metrics", {})

        # Build summary string
        pc_ratio = opts.get("put_call_oi_ratio")
        pc_str = f"P/C={pc_ratio:.2f}" if pc_ratio is not None else "P/C=N/A"

        iv = opts.get("avg_implied_volatility")
        iv_str = f"IV={iv:.0%}" if iv is not None else "IV=N/A"

        vol_ratio = trading.get("volume_ratio")
        vol_str = f"Vol={vol_ratio:.1f}x" if vol_ratio is not None else "Vol=N/A"

        # Use trailing annual yield as it's more reliable
        div_yield = div.get("trailing_annual_dividend_yield") or div.get("dividend_yield")
        div_str = f"Yield={div_yield:.2%}" if div_yield is not None else "Yield=N/A"

        output = AgentOutput(
            agent_name="YahooFinanceAgent",
            ticker=self.ticker,
            signal=reasoning["signal"],
            confidence=reasoning["confidence"],
            summary=f"{pc_str}, {iv_str}, {vol_str}, {div_str}",
            data={
                "options_sentiment": opts,
                "trading_activity": trading,
                "dividend_metrics": div,
                "price_performance": reasoning.get("price_performance", {}),
            },
        )
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict:
        return self._state.get("actions", {})
