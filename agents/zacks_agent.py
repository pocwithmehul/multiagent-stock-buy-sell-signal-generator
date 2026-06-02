"""Zacks analysis agent that scrapes rank, style scores, and target price."""

import re
import uuid
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from agentic_ai_base import AgenticAIBase
from infrastructure.config import Config
from schemas.messages import AgentOutput, ZacksMessage


class ZacksAnalysisAgent(AgenticAIBase):
    """Scrapes Zacks Rank, style scores, and analyst target price from zacks.com."""

    RANK_LABELS = {
        1: "Strong Buy",
        2: "Buy",
        3: "Hold",
        4: "Sell",
        5: "Strong Sell",
    }

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
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": Config.ZACKS_USER_AGENT})

        self.register_tool("fetch_zacks_data", self._fetch_zacks_data,
                           "Scrape Zacks rank and scores")
        if self.kafka_enabled:
            self.register_tool("publish_to_kafka", self._publish_to_kafka,
                               "Publish Zacks data to Kafka")
        if self.qdrant_enabled:
            self.register_tool("store_in_qdrant", self._store_in_qdrant,
                               "Store Zacks data embeddings in Qdrant")

    # ── Tool implementations ──────────────────────────────────────────

    def _apply_recommendation_fallback(self, data: dict) -> None:
        """Fallback: infer Zacks-like rank from yfinance recommendationMean."""
        if data.get("zacks_rank") is not None:
            return

        try:
            import yfinance as yf

            info = yf.Ticker(self.ticker).info or {}
            rec_mean = info.get("recommendationMean")
            if rec_mean is None:
                return

            rec = float(rec_mean)
            if rec <= 1.5:
                rank = 1
            elif rec <= 2.5:
                rank = 2
            elif rec <= 3.5:
                rank = 3
            elif rec <= 4.5:
                rank = 4
            else:
                rank = 5

            data["zacks_rank"] = rank
            data["rank_label"] = self.RANK_LABELS.get(rank, "")
        except Exception:
            return

    def _fetch_zacks_data(self) -> dict:
        """Scrape zacks.com for rank, style scores, industry rank, and target price."""
        url = f"{Config.ZACKS_BASE_URL}/{self.ticker}"
        data = {
            "zacks_rank": None,
            "rank_label": "",
            "style_scores": {},
            "industry_rank": "",
            "target_price": None,
        }

        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            self._apply_recommendation_fallback(data)
            return data

        # -- Zacks Rank --
        try:
            # Strategy 1: rank_view paragraph contains "2-Buy" pattern
            rank_view = soup.find("p", class_="rank_view")
            if rank_view:
                rank_text = rank_view.get_text(strip=True)
                m = re.search(r"(\d)\s*-\s*(Strong\s*Buy|Buy|Hold|Sell|Strong\s*Sell)", rank_text, re.IGNORECASE)
                if m:
                    data["zacks_rank"] = int(m.group(1))
            # Strategy 2: Regex on raw HTML for same pattern
            if data["zacks_rank"] is None:
                m = re.search(r'rank_view">\s*(\d)\s*-\s*(Strong\s*Buy|Buy|Hold|Sell|Strong\s*Sell)', html, re.IGNORECASE)
                if m:
                    data["zacks_rank"] = int(m.group(1))
            # Strategy 3: Broader fallback
            if data["zacks_rank"] is None:
                m = re.search(r"(\d)\s*-\s*(Strong\s*Buy|Buy|Hold|Sell|Strong\s*Sell)", html, re.IGNORECASE)
                if m:
                    data["zacks_rank"] = int(m.group(1))
            if data["zacks_rank"] is not None:
                data["rank_label"] = self.RANK_LABELS.get(data["zacks_rank"], "")
        except Exception:
            pass

        # -- Style Scores (Value, Growth, Momentum, VGM) --
        try:
            # Strategy 1: composite_val spans followed by style name
            # Pattern: <span class="composite_val">F</span>&nbsp;Value
            # VGM has: <span class="composite_val composite_val_vgm">B</span>&nbsp;VGM
            for style in ["Value", "Growth", "Momentum", "VGM"]:
                m = re.search(
                    rf'composite_val[^"]*">\s*([A-F])\s*</span>\s*(?:&nbsp;)?\s*{style}',
                    html, re.IGNORECASE
                )
                if m:
                    data["style_scores"][style] = m.group(1)
            # Strategy 2: Broader regex for grade-style pairs
            if not data["style_scores"]:
                for style in ["Value", "Growth", "Momentum", "VGM"]:
                    m = re.search(rf"([A-F])\s*(?:&nbsp;|\s)+{style}", html)
                    if m:
                        data["style_scores"][style] = m.group(1)
        except Exception:
            pass

        # -- Industry Rank --
        try:
            # Strategy 1: Find industry rank text
            ind_el = soup.find(string=re.compile(r"Industry Rank", re.IGNORECASE))
            if ind_el:
                parent = ind_el.find_parent()
                if parent:
                    rank_text = parent.get_text(strip=True)
                    m = re.search(r"(\d+)\s*(?:out\s+of|/)\s*(\d+)", rank_text)
                    if m:
                        data["industry_rank"] = f"{m.group(1)} out of {m.group(2)}"
                    else:
                        # Just capture any trailing number info
                        m = re.search(r"Industry Rank\s*[:\-]?\s*(.+?)(?:\s*$)", rank_text, re.IGNORECASE)
                        if m:
                            data["industry_rank"] = m.group(1).strip()[:100]
            # Strategy 2: Regex on raw HTML
            if not data["industry_rank"]:
                m = re.search(r"Industry Rank.*?(\d+\s*(?:out of|/)\s*\d+)", html, re.DOTALL | re.IGNORECASE)
                if m:
                    data["industry_rank"] = m.group(1).strip()
        except Exception:
            pass

        # -- Analyst Target Price --
        try:
            # Strategy 1: Look for target price element
            target_el = soup.find(string=re.compile(r"(?:Average\s+)?Target\s+Price", re.IGNORECASE))
            if target_el:
                parent = target_el.find_parent()
                if parent:
                    m = re.search(r"\$\s*([\d,]+\.?\d*)", parent.get_text())
                    if m:
                        data["target_price"] = float(m.group(1).replace(",", ""))
            # Strategy 2: Regex on raw HTML
            if data["target_price"] is None:
                m = re.search(r"(?:target|average)\s*price.*?\$\s*([\d,]+\.?\d*)", html, re.IGNORECASE | re.DOTALL)
                if m:
                    data["target_price"] = float(m.group(1).replace(",", ""))
            # Strategy 3: Look for price target in broader context
            if data["target_price"] is None:
                m = re.search(r"price\s*target.*?\$\s*([\d,]+\.?\d*)", html, re.IGNORECASE | re.DOTALL)
                if m:
                    data["target_price"] = float(m.group(1).replace(",", ""))
        except Exception:
            pass

        self._apply_recommendation_fallback(data)
        return data

    def _publish_to_kafka(self, zacks_data: dict) -> int:
        if not self.kafka_producer:
            return 0
        msg = ZacksMessage(
            ticker=self.ticker,
            zacks_rank=zacks_data.get("zacks_rank"),
            rank_label=zacks_data.get("rank_label", ""),
            style_scores=zacks_data.get("style_scores", {}),
            industry_rank=zacks_data.get("industry_rank", ""),
            target_price=zacks_data.get("target_price"),
        )
        self.kafka_producer.send(Config.KAFKA_TOPIC_ZACKS, key=self.ticker,
                                 value=msg.model_dump_json())
        return 1

    def _store_in_qdrant(self, zacks_data: dict) -> int:
        if not self.qdrant_store or not self.embedder:
            return 0
        summary = (
            f"Zacks Rank {zacks_data.get('zacks_rank', 'N/A')} "
            f"({zacks_data.get('rank_label', '')}) for {self.ticker}. "
            f"VGM: {zacks_data.get('style_scores', {}).get('VGM', 'N/A')}. "
            f"Industry: {zacks_data.get('industry_rank', 'N/A')}. "
            f"Target: ${zacks_data.get('target_price', 'N/A')}."
        )
        embeddings = self.embedder.embed([summary])
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.ticker}:zacks"))
        points = [{
            "id": point_id,
            "vector": embeddings[0],
            "payload": {
                "ticker": self.ticker,
                "zacks_rank": zacks_data.get("zacks_rank"),
                "rank_label": zacks_data.get("rank_label", ""),
                "style_scores": zacks_data.get("style_scores", {}),
                "industry_rank": zacks_data.get("industry_rank", ""),
                "target_price": zacks_data.get("target_price"),
            },
        }]
        self.qdrant_store.upsert(Config.QDRANT_COLLECTION_ZACKS, points)
        return 1

    # ── Signal mapping ────────────────────────────────────────────────

    def _compute_signal(self, zacks_data: dict) -> tuple[str, float]:
        """Map Zacks Rank to signal and confidence, adjusted by VGM grade."""
        rank = zacks_data.get("zacks_rank")
        if rank is None:
            return "NEUTRAL", 0.0

        signal_map = {
            1: ("BULLISH", 0.9),
            2: ("BULLISH", 0.7),
            3: ("NEUTRAL", 0.5),
            4: ("BEARISH", 0.7),
            5: ("BEARISH", 0.9),
        }
        signal, confidence = signal_map.get(rank, ("NEUTRAL", 0.0))

        # Adjust confidence by VGM grade
        vgm = zacks_data.get("style_scores", {}).get("VGM", "")
        if vgm in ("A", "B"):
            confidence = min(1.0, confidence + 0.05)
        elif vgm in ("D", "F"):
            confidence = max(0.0, confidence - 0.05)

        return signal, confidence

    # ── Agentic lifecycle ─────────────────────────────────────────────

    def plan(self):
        self._state["plan"] = [
            "Fetch Zacks rank and style scores",
            "Publish to Kafka (if enabled)",
            "Store embeddings in Qdrant (if enabled)",
        ]

    def perceive(self):
        zacks_data = self.use_tool("fetch_zacks_data")
        self._state["data"]["zacks"] = zacks_data
        if not zacks_data.get("zacks_rank"):
            self.debug_log_no_data("Zacks", "Could not fetch Zacks rank data (scraping may have failed)")
        else:
            self.debug_log("Zacks Data", zacks_data)

    def reason(self):
        zacks_data = self._state["data"].get("zacks", {})
        signal, confidence = self._compute_signal(zacks_data)
        self._state["reasoning"] = {
            "signal": signal,
            "confidence": confidence,
            "zacks_rank": zacks_data.get("zacks_rank"),
            "rank_label": zacks_data.get("rank_label", ""),
            "style_scores": zacks_data.get("style_scores", {}),
            "industry_rank": zacks_data.get("industry_rank", ""),
            "target_price": zacks_data.get("target_price"),
        }

    def act(self):
        zacks_data = self._state["data"].get("zacks", {})
        reasoning = self._state["reasoning"]

        if self.kafka_enabled:
            self._publish_to_kafka(zacks_data)
        if self.qdrant_enabled:
            self._store_in_qdrant(zacks_data)

        rank = reasoning.get("zacks_rank")
        rank_str = f"Rank {rank} ({reasoning.get('rank_label', '')})" if rank else "N/A"
        vgm = reasoning.get("style_scores", {}).get("VGM", "N/A")
        target = reasoning.get("target_price")
        target_str = f"${target}" if target else "N/A"

        output = AgentOutput(
            agent_name="ZacksAnalysisAgent",
            ticker=self.ticker,
            signal=reasoning["signal"],
            confidence=reasoning["confidence"],
            summary=f"Zacks {rank_str}, VGM={vgm}, Target={target_str}",
            data={
                "zacks_rank": reasoning.get("zacks_rank"),
                "rank_label": reasoning.get("rank_label", ""),
                "style_scores": reasoning.get("style_scores", {}),
                "industry_rank": reasoning.get("industry_rank", ""),
                "target_price": reasoning.get("target_price"),
            },
        )
        self._state["actions"] = output.model_dump()

    def get_output(self) -> dict:
        return self._state.get("actions", {})
