"""Tests for SeekingAlpha agent."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime


class TestSeekingAlphaAgentInit:
    """Test SeekingAlphaAgent initialization."""

    @patch('agents.seekingalpha_agent.yf')
    def test_init_basic(self, mock_yf):
        """Test basic initialization."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")

        assert agent.ticker == "AAPL"
        assert not agent.kafka_enabled
        assert not agent.qdrant_enabled

    @patch('agents.seekingalpha_agent.yf')
    def test_init_with_kafka(self, mock_yf):
        """Test initialization with Kafka enabled."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_producer = MagicMock()
        agent = SeekingAlphaAgent("AAPL", kafka_producer=mock_producer, kafka_enabled=True)

        assert agent.kafka_enabled
        assert "publish_to_kafka" in agent._tools

    @patch('agents.seekingalpha_agent.yf')
    def test_init_with_qdrant(self, mock_yf):
        """Test initialization with Qdrant enabled."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        agent = SeekingAlphaAgent(
            "AAPL",
            qdrant_store=mock_store,
            qdrant_enabled=True,
            embedder=mock_embedder
        )

        assert agent.qdrant_enabled
        assert "store_in_qdrant" in agent._tools


class TestSeekingAlphaDataFetching:
    """Test data fetching functionality."""

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_earnings_estimates(self, mock_yf):
        """Test fetching earnings estimates."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        # Mock earnings estimate DataFrame
        mock_ticker.earnings_estimate = pd.DataFrame({
            "avg": [2.5],
            "low": [2.0],
            "high": [3.0],
            "yearAgoEps": [2.0],
            "numberOfAnalysts": [15],
            "growth": [0.25],
        }, index=["0q"])

        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert data["earnings_estimates"]["avg"] == 2.5
        assert data["earnings_estimates"]["number_of_analysts"] == 15
        assert data["earnings_estimates"]["growth"] == 0.25

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_revenue_estimates(self, mock_yf):
        """Test fetching revenue estimates."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = pd.DataFrame({
            "avg": [100000000000],
            "low": [95000000000],
            "high": [105000000000],
            "numberOfAnalysts": [20],
            "yearAgoRevenue": [90000000000],
            "growth": [0.11],
        }, index=["0q", "+1q", "0y"])
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert data["revenue_estimates"]["avg"] == 100000000000
        assert data["revenue_estimates"]["growth"] == 0.11

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_growth_estimates(self, mock_yf):
        """Test fetching growth estimates."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = pd.DataFrame({
            "AAPL": [0.15, 0.20, 0.18],
            "S&P 500": [0.10, 0.12, 0.11],
        }, index=["0q", "+1q", "0y"])
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert "0q" in data["growth_estimates"]
        assert data["growth_estimates"]["0q"]["stock_trend"] == 0.15
        assert data["growth_estimates"]["0q"]["index_trend"] == 0.10

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_earnings_history(self, mock_yf):
        """Test fetching earnings history."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = pd.DataFrame({
            "epsActual": [2.5, 2.3],
            "epsEstimate": [2.4, 2.2],
            "epsDifference": [0.1, 0.1],
            "surprisePercent": [4.17, 4.55],
        }, index=pd.to_datetime(["2024-01-15", "2023-10-15"]))
        mock_ticker.eps_trend = None
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert len(data["earnings_history"]) == 2
        assert data["earnings_history"][0]["eps_actual"] == 2.5
        assert data["earnings_history"][0]["surprise_percent"] == 4.17

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_eps_trend(self, mock_yf):
        """Test fetching EPS trend."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = pd.DataFrame({
            "current": [2.5],
            "7daysAgo": [2.45],
            "30daysAgo": [2.40],
            "60daysAgo": [2.35],
            "90daysAgo": [2.30],
        }, index=["0q"])
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert data["eps_trend"]["current"] == 2.5
        assert data["eps_trend"]["30days_ago"] == 2.40

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_valuation_metrics(self, mock_yf):
        """Test fetching valuation metrics."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {
            "trailingPE": 25.5,
            "forwardPE": 22.0,
            "priceToBook": 8.5,
            "dividendYield": 0.005,
            "profitMargins": 0.25,
            "returnOnEquity": 0.40,
            "revenueGrowth": 0.15,
            "earningsGrowth": 0.22,
        }

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        assert data["valuation"]["trailing_pe"] == 25.5
        assert data["valuation"]["earnings_growth"] == 0.22

    @patch('agents.seekingalpha_agent.yf')
    def test_fetch_handles_all_exceptions(self, mock_yf):
        """Test that all data fetching handles exceptions gracefully."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        # All properties raise exceptions
        mock_ticker.earnings_estimate = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).earnings_estimate = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).revenue_estimate = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).growth_estimates = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).earnings_history = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).eps_trend = property(lambda x: (_ for _ in ()).throw(Exception("Error")))
        type(mock_ticker).info = property(lambda x: (_ for _ in ()).throw(Exception("Error")))

        agent = SeekingAlphaAgent("AAPL")
        data = agent._fetch_seekingalpha_data()

        # Should return empty data structure, not raise
        assert data["earnings_estimates"] == {}
        assert data["valuation"] == {}


class TestSeekingAlphaSignalComputation:
    """Test signal computation logic."""

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_all_beats(self, mock_yf):
        """Test signal with all earnings beats."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [
                {"surprise_percent": 5.0},
                {"surprise_percent": 3.0},
                {"surprise_percent": 2.0},
                {"surprise_percent": 4.0},
            ],
            "eps_trend": {"current": 2.5, "30days_ago": 2.0},
            "valuation": {"earnings_growth": 0.25},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BULLISH"
        assert confidence > 0.5

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_75pct_beats(self, mock_yf):
        """Test signal with 75% earnings beats."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [
                {"surprise_percent": 5.0},
                {"surprise_percent": 3.0},
                {"surprise_percent": 2.0},
                {"surprise_percent": -1.0},
            ],
            "eps_trend": {},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        # With 75% beats and no other factors, should be bullish
        assert signal == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_50pct_beats(self, mock_yf):
        """Test signal with 50% earnings beats."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [
                {"surprise_percent": 5.0},
                {"surprise_percent": 3.0},
                {"surprise_percent": -2.0},
                {"surprise_percent": -1.0},
            ],
            "eps_trend": {},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "NEUTRAL"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_25pct_beats(self, mock_yf):
        """Test signal with 25% earnings beats."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [
                {"surprise_percent": 5.0},
                {"surprise_percent": -3.0},
                {"surprise_percent": -2.0},
                {"surprise_percent": -1.0},
            ],
            "eps_trend": {},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BEARISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_no_beats(self, mock_yf):
        """Test signal with no earnings beats."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [
                {"surprise_percent": -5.0},
                {"surprise_percent": -3.0},
                {"surprise_percent": -2.0},
                {"surprise_percent": -1.0},
            ],
            "eps_trend": {},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BEARISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_eps_revision_up(self, mock_yf):
        """Test signal with EPS revisions upward."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {"current": 2.5, "30days_ago": 2.0},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_eps_revision_down(self, mock_yf):
        """Test signal with EPS revisions downward."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {"current": 2.0, "30days_ago": 2.5},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BEARISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_eps_revision_flat(self, mock_yf):
        """Test signal with flat EPS revisions."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {"current": 2.5, "30days_ago": 2.5},
            "valuation": {},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "NEUTRAL"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_high_growth(self, mock_yf):
        """Test signal with high earnings growth."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {"earnings_growth": 0.25},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_moderate_growth(self, mock_yf):
        """Test signal with moderate earnings growth."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {"earnings_growth": 0.15},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_low_growth(self, mock_yf):
        """Test signal with low earnings growth."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {"earnings_growth": 0.05},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "NEUTRAL"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_negative_growth(self, mock_yf):
        """Test signal with negative earnings growth."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {"earnings_growth": -0.10},
        }

        signal, confidence = agent._compute_signal(data)

        assert signal == "BEARISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_compute_signal_no_data(self, mock_yf):
        """Test signal with no data."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        data = {}

        signal, confidence = agent._compute_signal(data)

        assert signal == "NEUTRAL"
        assert confidence == 0.0


class TestSeekingAlphaKafkaQdrant:
    """Test Kafka and Qdrant integration."""

    @patch('agents.seekingalpha_agent.yf')
    def test_publish_to_kafka(self, mock_yf):
        """Test publishing to Kafka."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_producer = MagicMock()
        agent = SeekingAlphaAgent("AAPL", kafka_producer=mock_producer, kafka_enabled=True)

        data = {
            "earnings_estimates": {"avg": 2.5},
            "revenue_estimates": {"avg": 100000000000},
            "growth_estimates": {},
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {},
        }

        result = agent._publish_to_kafka(data)

        assert result == 1
        mock_producer.send.assert_called_once()

    @patch('agents.seekingalpha_agent.yf')
    def test_publish_to_kafka_no_producer(self, mock_yf):
        """Test publishing without producer returns 0."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")

        result = agent._publish_to_kafka({})

        assert result == 0

    @patch('agents.seekingalpha_agent.yf')
    def test_store_in_qdrant(self, mock_yf):
        """Test storing in Qdrant."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]

        agent = SeekingAlphaAgent(
            "AAPL",
            qdrant_store=mock_store,
            qdrant_enabled=True,
            embedder=mock_embedder
        )

        data = {
            "valuation": {"trailing_pe": 25.0, "forward_pe": 22.0},
            "earnings_estimates": {"avg": 2.5, "growth": 0.15},
            "eps_trend": {"current": 2.5},
        }

        result = agent._store_in_qdrant(data)

        assert result == 1
        mock_embedder.embed.assert_called_once()
        mock_store.upsert.assert_called_once()

    @patch('agents.seekingalpha_agent.yf')
    def test_store_in_qdrant_no_store(self, mock_yf):
        """Test storing without store returns 0."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")

        result = agent._store_in_qdrant({})

        assert result == 0


class TestSeekingAlphaLifecycle:
    """Test agentic lifecycle methods."""

    @patch('agents.seekingalpha_agent.yf')
    def test_plan(self, mock_yf):
        """Test plan phase."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        agent.plan()

        assert len(agent._state["plan"]) == 3

    @patch('agents.seekingalpha_agent.yf')
    def test_perceive(self, mock_yf):
        """Test perceive phase."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {"trailingPE": 25.0}

        agent = SeekingAlphaAgent("AAPL")
        agent.perceive()

        assert "seekingalpha" in agent._state["data"]

    @patch('agents.seekingalpha_agent.yf')
    def test_perceive_no_data(self, mock_yf):
        """Test perceive phase with no data."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {}

        agent = SeekingAlphaAgent("AAPL")
        agent.perceive()

        # Valuation dict is populated with None values from empty info
        valuation = agent._state["data"]["seekingalpha"]["valuation"]
        assert valuation["trailing_pe"] is None

    @patch('agents.seekingalpha_agent.yf')
    @patch.dict('os.environ', {"DEBUG": "true"})
    def test_perceive_with_debug_no_data(self, mock_yf):
        """Test perceive phase with debug and no data triggers debug log."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        # Make info raise so valuation stays empty
        type(mock_ticker).info = property(lambda x: (_ for _ in ()).throw(Exception("Error")))

        agent = SeekingAlphaAgent("AAPL")
        # This should trigger debug_log_no_data since valuation will be {}
        agent.perceive()

        # Verify no exception raised and valuation is empty
        assert "seekingalpha" in agent._state["data"]
        assert agent._state["data"]["seekingalpha"]["valuation"] == {}

    @patch('agents.seekingalpha_agent.yf')
    def test_reason(self, mock_yf):
        """Test reason phase."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        agent._state["data"]["seekingalpha"] = {
            "earnings_history": [{"surprise_percent": 5.0}],
            "eps_trend": {},
            "valuation": {},
        }
        agent.reason()

        assert "signal" in agent._state["reasoning"]
        assert "confidence" in agent._state["reasoning"]

    @patch('agents.seekingalpha_agent.yf')
    def test_act(self, mock_yf):
        """Test act phase."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        agent._state["data"]["seekingalpha"] = {
            "earnings_estimates": {"avg": 2.5, "growth": 0.15},
            "revenue_estimates": {},
            "growth_estimates": {},
            "earnings_history": [{"surprise_percent": 5.0}],
            "eps_trend": {},
            "valuation": {"trailing_pe": 25.0},
        }
        agent._state["reasoning"] = {
            "signal": "BULLISH",
            "confidence": 0.75,
            "earnings_estimates": {"avg": 2.5, "growth": 0.15},
            "revenue_estimates": {},
            "growth_estimates": {},
            "earnings_history": [{"surprise_percent": 5.0}],
            "eps_trend": {},
            "valuation": {"trailing_pe": 25.0},
        }
        agent.act()

        assert "actions" in agent._state
        assert agent._state["actions"]["signal"] == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_act_with_kafka_qdrant(self, mock_yf):
        """Test act phase with Kafka and Qdrant."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_producer = MagicMock()
        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]

        agent = SeekingAlphaAgent(
            "AAPL",
            kafka_producer=mock_producer,
            kafka_enabled=True,
            qdrant_store=mock_store,
            qdrant_enabled=True,
            embedder=mock_embedder
        )
        agent._state["data"]["seekingalpha"] = {
            "earnings_estimates": {},
            "revenue_estimates": {},
            "growth_estimates": {},
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {},
        }
        agent._state["reasoning"] = {
            "signal": "NEUTRAL",
            "confidence": 0.5,
            "earnings_estimates": {},
            "revenue_estimates": {},
            "growth_estimates": {},
            "earnings_history": [],
            "eps_trend": {},
            "valuation": {},
        }
        agent.act()

        mock_producer.send.assert_called_once()
        mock_store.upsert.assert_called_once()

    @patch('agents.seekingalpha_agent.yf')
    def test_get_output(self, mock_yf):
        """Test get_output method."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        agent = SeekingAlphaAgent("AAPL")
        agent._state["actions"] = {"signal": "BULLISH", "confidence": 0.8}

        output = agent.get_output()

        assert output["signal"] == "BULLISH"

    @patch('agents.seekingalpha_agent.yf')
    def test_full_execute(self, mock_yf):
        """Test full execute lifecycle."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        mock_ticker = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker
        mock_ticker.earnings_estimate = None
        mock_ticker.revenue_estimate = None
        mock_ticker.growth_estimates = None
        mock_ticker.earnings_history = None
        mock_ticker.eps_trend = None
        mock_ticker.info = {"trailingPE": 25.0, "earningsGrowth": 0.25}

        agent = SeekingAlphaAgent("AAPL")
        agent.execute()

        output = agent.get_output()
        assert output["agent_name"] == "SeekingAlphaAgent"
        assert output["ticker"] == "AAPL"


class TestSeekingAlphaSafeFloat:
    """Test _safe_float helper method."""

    @patch('agents.seekingalpha_agent.yf')
    def test_safe_float_with_valid_number(self, mock_yf):
        """Test safe_float with valid number."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        result = SeekingAlphaAgent._safe_float(3.14)
        assert result == 3.14

    @patch('agents.seekingalpha_agent.yf')
    def test_safe_float_with_none(self, mock_yf):
        """Test safe_float with None."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        result = SeekingAlphaAgent._safe_float(None)
        assert result is None

    @patch('agents.seekingalpha_agent.yf')
    def test_safe_float_with_nan(self, mock_yf):
        """Test safe_float with NaN."""
        from agents.seekingalpha_agent import SeekingAlphaAgent
        import math

        result = SeekingAlphaAgent._safe_float(float('nan'))
        assert result is None

    @patch('agents.seekingalpha_agent.yf')
    def test_safe_float_with_string(self, mock_yf):
        """Test safe_float with invalid string."""
        from agents.seekingalpha_agent import SeekingAlphaAgent

        result = SeekingAlphaAgent._safe_float("not a number")
        assert result is None
