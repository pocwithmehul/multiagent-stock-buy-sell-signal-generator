import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf
import litellm

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from infrastructure.postgres_store import PostgresPriceStore


class StockSignalAgent(AgenticAIBase):
    """Agent that analyzes a stock and produces a buy/sell/hold signal."""

    def __init__(self, stock_ticker: str, past_days: int, model: str = "gpt-4o-mini", api_base: str = None):
        super().__init__()
        self.ticker = stock_ticker.upper()
        self.past_days = past_days
        self.model = model
        self.api_base = api_base
        self.postgres_store = None

        if Config.POSTGRES_ENABLED:
            try:
                self.postgres_store = PostgresPriceStore()
                self.postgres_store.ensure_schema()
            except Exception:
                self.postgres_store = None

        self.register_tool("fetch_current_price", self._fetch_current_price, "Get current price and basic info")
        self.register_tool("fetch_price_history", self._fetch_price_history, "Get historical OHLCV data")
        self.register_tool("fetch_analyst_recommendations", self._fetch_analyst_recommendations, "Get analyst ratings")
        self.register_tool("fetch_news", self._fetch_news, "Get recent news articles")
        self.register_tool("analyze_with_llm", self._analyze_with_llm, "Send data to LLM for analysis")

    def _empty_current_price_info(self, error: str | None = None) -> dict:
        result = {
            "current_price": None,
            "previous_close": None,
            "market_cap": None,
            "pe_ratio": None,
            "forward_pe": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "dividend_yield": None,
            "sector": None,
            "industry": None,
            "name": self.ticker,
        }
        if error:
            result["error"] = error
        return result

    def _empty_recommendations(self, error: str | None = None) -> dict:
        result = {
            "recommendations": [],
            "consensus": "N/A",
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
        }
        if error:
            result["error"] = error
        return result

    # ── Tool implementations ──────────────────────────────────────────

    def _fetch_current_price(self) -> dict:
        try:
            stock = yf.Ticker(self.ticker)
            info = stock.info or {}
        except Exception as e:
            return self._empty_current_price_info(error=f"Failed to fetch current price data: {e}")

        # Try to get the most recent price from intraday data
        current_price = None
        try:
            # Fetch 1-minute interval data for today
            intraday = stock.history(period="1d", interval="1m")
            if not intraday.empty:
                current_price = round(float(intraday["Close"].iloc[-1]), 2)
        except Exception:
            pass

        # Fall back to info if intraday not available
        if current_price is None:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        return {
            "current_price": current_price,
            "previous_close": info.get("previousClose"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "name": info.get("shortName"),
        }

    def _fetch_price_history(self) -> dict:
        end = datetime.now()
        start = end - timedelta(days=self.past_days)
        hist = pd.DataFrame()

        if self.postgres_store:
            try:
                hist = self.postgres_store.load_prices(self.ticker, start, end)
            except Exception:
                hist = pd.DataFrame()

        if hist.empty:
            try:
                stock = yf.Ticker(self.ticker)
                backfill_days = max(self.past_days, Config.POSTGRES_BACKFILL_YEARS * 365)
                backfill_start = end - timedelta(days=backfill_days)
                hist = stock.history(start=backfill_start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
            except Exception as e:
                return {"error": f"Failed to fetch historical data: {e}"}

            # Try to include the most recent intraday price for real-time data
            try:
                intraday = stock.history(period="1d", interval="1m")
                if not intraday.empty:
                    latest = intraday.iloc[[-1]].copy()
                    latest.index = pd.to_datetime([end.strftime("%Y-%m-%d")])
                    if hist.empty:
                        hist = latest
                    elif hist.index[-1].date() < end.date():
                        hist = pd.concat([hist, latest])
                    else:
                        # Update today's row with latest intraday data
                        hist.iloc[-1] = latest.iloc[0]
            except Exception:
                pass

            if self.postgres_store and not hist.empty:
                try:
                    self.postgres_store.upsert_prices(self.ticker, hist)
                    hist = self.postgres_store.load_prices(self.ticker, start, end)
                except Exception:
                    pass

        if hist.empty:
            return {"error": "No historical data available"}

        records = []
        for date, row in hist.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        closes = hist["Close"]
        return {
            "records": records,
            "summary": {
                "period_start": records[0]["date"],
                "period_end": records[-1]["date"],
                "start_price": records[0]["close"],
                "end_price": records[-1]["close"],
                "high": round(closes.max(), 2),
                "low": round(closes.min(), 2),
                "avg": round(closes.mean(), 2),
                "change_pct": round(((records[-1]["close"] - records[0]["close"]) / records[0]["close"]) * 100, 2),
                "trading_days": len(records),
            },
        }

    def _fetch_analyst_recommendations(self) -> dict:
        try:
            stock = yf.Ticker(self.ticker)
            recs = stock.recommendations
        except Exception as e:
            return self._empty_recommendations(error=f"Failed to fetch analyst recommendations: {e}")
        if recs is None or recs.empty:
            return self._empty_recommendations()

        recent = recs.tail(20)
        rec_list = []
        for _, row in recent.iterrows():
            entry = {}
            for col in recent.columns:
                val = row[col]
                entry[col.lower()] = str(val) if not isinstance(val, (int, float, str)) else val
            rec_list.append(entry)

        grades = recent.iloc[:, 0].astype(str).str.lower() if len(recent.columns) > 0 else []
        buy_count = sum(1 for g in grades if any(k in g for k in ["buy", "outperform", "overweight"]))
        sell_count = sum(1 for g in grades if any(k in g for k in ["sell", "underperform", "underweight"]))
        hold_count = sum(1 for g in grades if any(k in g for k in ["hold", "neutral", "equal", "market perform"]))
        total = buy_count + sell_count + hold_count

        if total == 0:
            consensus = "N/A"
        elif buy_count / max(total, 1) > 0.6:
            consensus = "Strong Buy"
        elif buy_count / max(total, 1) > 0.4:
            consensus = "Buy"
        elif sell_count / max(total, 1) > 0.4:
            consensus = "Sell"
        else:
            consensus = "Hold"

        return {
            "recommendations": rec_list,
            "consensus": consensus,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
        }

    def _fetch_news(self) -> dict:
        try:
            stock = yf.Ticker(self.ticker)
            news = stock.news or []
        except Exception as e:
            return {"articles": [], "count": 0, "error": f"Failed to fetch news: {e}"}
        articles = []
        for item in news[:15]:
            content = item.get("content", {}) if isinstance(item.get("content"), dict) else {}
            articles.append({
                "title": content.get("title") or item.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher", ""),
                "link": item.get("link", content.get("canonicalUrl", {}).get("url", "")),
                "published": content.get("pubDate", item.get("providerPublishTime", "")),
            })
        return {"articles": articles, "count": len(articles)}

    def _analyze_with_llm(self, prompt: str) -> str:
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
            return response.choices[0].message.content.strip()
        except Exception as e:
            # Return valid JSON so downstream parsing remains stable.
            return json.dumps({
                "signal": "HOLD",
                "confidence": 0.0,
                "target_price": 0,
                "potential_upside_pct": 0,
                "potential_downside_pct": 0,
                "stop_loss": 0,
                "sentiment_score": 0,
                "reasoning": f"LLM analysis unavailable: {e}",
            })

    # ── Agentic lifecycle ─────────────────────────────────────────────

    def plan(self):
        self._state["plan"] = [
            "Fetch current price and basic info",
            "Fetch historical price data",
            "Fetch analyst recommendations",
            "Fetch recent news",
            "Analyze all data with LLM",
            "Generate final buy/sell/hold signal",
        ]

    def perceive(self):
        data = self._state["data"]
        try:
            data["current_price_info"] = self.use_tool("fetch_current_price")
        except Exception as e:
            data["current_price_info"] = self._empty_current_price_info(error=f"Tool failure: {e}")
        self.debug_log("Current Price Info", data["current_price_info"])

        try:
            data["price_history"] = self.use_tool("fetch_price_history")
        except Exception as e:
            data["price_history"] = {"error": f"Tool failure: {e}"}
        self.debug_log("Price History", data["price_history"])

        try:
            data["analyst_recommendations"] = self.use_tool("fetch_analyst_recommendations")
        except Exception as e:
            data["analyst_recommendations"] = self._empty_recommendations(error=f"Tool failure: {e}")
        self.debug_log("Analyst Recommendations", data["analyst_recommendations"])

        try:
            data["news"] = self.use_tool("fetch_news")
        except Exception as e:
            data["news"] = {"articles": [], "count": 0, "error": f"Tool failure: {e}"}
        self.debug_log("News Articles", data["news"])

    def reason(self):
        data = self._state["data"]
        current = data["current_price_info"]
        history = data["price_history"]
        recs = data["analyst_recommendations"]
        news = data["news"]

        headlines = [a["title"] for a in news.get("articles", []) if a.get("title")]

        prompt = f"""Analyze the following stock data for {self.ticker} and provide a trading signal.

## Current Info
- Name: {current.get('name')}
- Current Price: ${current.get('current_price')}
- Previous Close: ${current.get('previous_close')}
- P/E Ratio: {current.get('pe_ratio')}
- Forward P/E: {current.get('forward_pe')}
- 52-Week High: ${current.get('fifty_two_week_high')}
- 52-Week Low: ${current.get('fifty_two_week_low')}
- Market Cap: {current.get('market_cap')}
- Sector: {current.get('sector')}

## Price History ({self.past_days} days)
{json.dumps(history.get('summary', {}), indent=2)}

## Analyst Recommendations
- Consensus: {recs.get('consensus')}
- Buy ratings: {recs.get('buy_count', 0)}, Sell ratings: {recs.get('sell_count', 0)}, Hold ratings: {recs.get('hold_count', 0)}

## Recent News Headlines
{chr(10).join('- ' + h for h in headlines) if headlines else '- No recent news available'}

Based on this data, provide your analysis as JSON with these exact fields:
{{
  "signal": "BUY" or "SELL" or "HOLD",
  "confidence": 0.0 to 1.0,
  "target_price": estimated target price as number,
  "potential_upside_pct": percentage upside as number,
  "potential_downside_pct": percentage downside as negative number,
  "stop_loss": suggested stop loss price as number,
  "sentiment_score": -1.0 to 1.0 based on news sentiment,
  "reasoning": "2-3 sentence explanation"
}}"""

        raw = self.use_tool("analyze_with_llm", prompt=prompt)

        # Strip markdown fencing if present
        cleaned = raw
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            self._state["reasoning"] = json.loads(cleaned)
        except json.JSONDecodeError:
            self._state["reasoning"] = {
                "signal": "HOLD",
                "confidence": 0.0,
                "target_price": current.get("current_price", 0),
                "potential_upside_pct": 0,
                "potential_downside_pct": 0,
                "stop_loss": 0,
                "sentiment_score": 0,
                "reasoning": f"LLM response could not be parsed. Raw: {raw[:200]}",
            }

    def act(self):
        data = self._state["data"]
        reasoning = self._state["reasoning"]
        current_price = data["current_price_info"].get("current_price")
        news = data["news"]
        recs = data["analyst_recommendations"]

        # Build sources list
        sources = [
            {"name": "Yahoo Finance", "url": f"https://finance.yahoo.com/quote/{self.ticker}"},
            {"name": "Yahoo Finance News", "url": f"https://finance.yahoo.com/quote/{self.ticker}/news"},
        ]

        self._state["actions"] = {
            "ticker": self.ticker,
            "current_price": current_price,
            "signal": reasoning.get("signal", "HOLD"),
            "confidence": reasoning.get("confidence", 0),
            "target_price": reasoning.get("target_price"),
            "potential_upside_pct": reasoning.get("potential_upside_pct"),
            "potential_downside_pct": reasoning.get("potential_downside_pct"),
            "stop_loss": reasoning.get("stop_loss"),
            "analyst_consensus": recs.get("consensus", "N/A"),
            "sentiment_score": reasoning.get("sentiment_score", 0),
            "reasoning": reasoning.get("reasoning", ""),
            "articles_analyzed": news.get("count", 0),
            "data_period_days": self.past_days,
            "sources": sources,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_signal(self) -> dict:
        """Convenience method: return just the final signal output."""
        return self._state.get("actions", {})
