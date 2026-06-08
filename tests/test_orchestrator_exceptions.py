"""Tests for OrchestratorAgent exception handling in sub-agent runners."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime


def get_mock_yfinance_ticker():
    """Create a comprehensive mock yfinance Ticker."""
    mock_ticker = MagicMock()

    mock_ticker.info = {
        "currentPrice": 150.0,
        "regularMarketPrice": 150.0,
        "previousClose": 148.0,
        "marketCap": 2500000000000,
        "trailingPE": 25.5,
        "recommendationKey": "buy",
        "recommendationMean": 2.0,
    }

    mock_ticker.recommendations = pd.DataFrame({
        "strongBuy": [10], "buy": [15], "hold": [10], "sell": [3], "strongSell": [2],
    })

    mock_ticker.upgrades_downgrades = pd.DataFrame()
    mock_ticker.analyst_price_targets = {"mean": 175.0}

    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    mock_ticker.history.return_value = pd.DataFrame({
        'Open': [150.0] * 100, 'High': [152.0] * 100,
        'Low': [148.0] * 100, 'Close': [151.0] * 100,
        'Volume': [50000000] * 100,
    }, index=dates)

    mock_ticker.news = []
    mock_ticker.insider_transactions = pd.DataFrame()
    mock_ticker.insider_purchases = pd.DataFrame()
    mock_ticker.institutional_holders = pd.DataFrame()
    mock_ticker.major_holders = pd.DataFrame()
    mock_ticker.calendar = {}
    mock_ticker.dividends = pd.Series(dtype=float)
    mock_ticker.options = []

    return mock_ticker


class TestOrchestratorSubAgentExceptions:
    """Test exception handling in orchestrator sub-agent runners."""

    @patch('yfinance.Ticker')
    def test_run_technical_agent_exception(self, mock_ticker_class):
        """Test _run_technical_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_technical_agent()

        # Should return None on exception
        assert result is None

    @patch('yfinance.Ticker')
    def test_run_news_agent_exception(self, mock_ticker_class):
        """Test _run_news_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_news_agent()

        assert result is None

    @patch('agents.sec_filing_agent.SECFilingAgent.execute')
    def test_run_sec_agent_exception(self, mock_execute):
        """Test _run_sec_agent handles exceptions."""
        mock_execute.side_effect = Exception("Agent error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_sec_agent()

        assert result is None

    @patch('agents.zacks_agent.ZacksAnalysisAgent.execute')
    def test_run_zacks_agent_exception(self, mock_execute):
        """Test _run_zacks_agent handles exceptions."""
        mock_execute.side_effect = Exception("Agent error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_zacks_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_tipranks_agent_exception(self, mock_ticker_class):
        """Test _run_tipranks_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_tipranks_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_seekingalpha_agent_exception(self, mock_ticker_class):
        """Test _run_seekingalpha_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_seekingalpha_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_insider_agent_exception(self, mock_ticker_class):
        """Test _run_insider_institutional_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_insider_institutional_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_motleyfool_agent_exception(self, mock_ticker_class):
        """Test _run_motleyfool_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_motleyfool_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_stockstory_agent_exception(self, mock_ticker_class):
        """Test _run_stockstory_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_stockstory_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_yahoofinance_agent_exception(self, mock_ticker_class):
        """Test _run_yahoofinance_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_yahoofinance_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_morningstar_agent_exception(self, mock_ticker_class):
        """Test _run_morningstar_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_morningstar_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_gurufocus_agent_exception(self, mock_ticker_class):
        """Test _run_gurufocus_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_gurufocus_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_tradingview_agent_exception(self, mock_ticker_class):
        """Test _run_tradingview_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_tradingview_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_stockrover_agent_exception(self, mock_ticker_class):
        """Test _run_stockrover_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_stockrover_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_simplywallst_agent_exception(self, mock_ticker_class):
        """Test _run_simplywallst_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_simplywallst_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_alphaspread_agent_exception(self, mock_ticker_class):
        """Test _run_alphaspread_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_alphaspread_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_factset_agent_exception(self, mock_ticker_class):
        """Test _run_factset_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_factset_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_capitaliq_agent_exception(self, mock_ticker_class):
        """Test _run_capitaliq_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_capitaliq_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_marketbeat_agent_exception(self, mock_ticker_class):
        """Test _run_marketbeat_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_marketbeat_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_refinitiv_agent_exception(self, mock_ticker_class):
        """Test _run_refinitiv_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_refinitiv_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_macrotrends_agent_exception(self, mock_ticker_class):
        """Test _run_macrotrends_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_macrotrends_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_ycharts_agent_exception(self, mock_ticker_class):
        """Test _run_ycharts_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_ycharts_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_koyfin_agent_exception(self, mock_ticker_class):
        """Test _run_koyfin_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_koyfin_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_valueline_agent_exception(self, mock_ticker_class):
        """Test _run_valueline_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_valueline_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_xtwitter_agent_exception(self, mock_ticker_class):
        """Test _run_xtwitter_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_xtwitter_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_facebook_agent_exception(self, mock_ticker_class):
        """Test _run_facebook_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_facebook_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_instagram_agent_exception(self, mock_ticker_class):
        """Test _run_instagram_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_instagram_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_cnbc_agent_exception(self, mock_ticker_class):
        """Test _run_cnbc_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_cnbc_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_bloomberg_agent_exception(self, mock_ticker_class):
        """Test _run_bloomberg_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_bloomberg_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_wsj_agent_exception(self, mock_ticker_class):
        """Test _run_wsj_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_wsj_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_marketwatch_agent_exception(self, mock_ticker_class):
        """Test _run_marketwatch_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_marketwatch_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_foxbusiness_agent_exception(self, mock_ticker_class):
        """Test _run_foxbusiness_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_foxbusiness_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_barrons_agent_exception(self, mock_ticker_class):
        """Test _run_barrons_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_barrons_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_insidermonkey_agent_exception(self, mock_ticker_class):
        """Test _run_insidermonkey_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_insidermonkey_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_quiverquant_agent_exception(self, mock_ticker_class):
        """Test _run_quiverquant_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_quiverquant_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_dataroma_agent_exception(self, mock_ticker_class):
        """Test _run_dataroma_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_dataroma_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_openinsider_agent_exception(self, mock_ticker_class):
        """Test _run_openinsider_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_openinsider_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_whalewisdom_agent_exception(self, mock_ticker_class):
        """Test _run_whalewisdom_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="AAPL")
        result = orchestrator._run_whalewisdom_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_etfcom_agent_exception(self, mock_ticker_class):
        """Test _run_etfcom_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="SPY")
        result = orchestrator._run_etfcom_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_etfdb_agent_exception(self, mock_ticker_class):
        """Test _run_etfdb_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="SPY")
        result = orchestrator._run_etfdb_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_globalxetf_agent_exception(self, mock_ticker_class):
        """Test _run_globalxetf_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="BOTZ")
        result = orchestrator._run_globalxetf_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_arkinvest_agent_exception(self, mock_ticker_class):
        """Test _run_arkinvest_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="ARKK")
        result = orchestrator._run_arkinvest_agent()

        assert result is None

    @patch('yfinance.Ticker')
    def test_run_morningstaretf_agent_exception(self, mock_ticker_class):
        """Test _run_morningstaretf_agent handles exceptions."""
        mock_ticker_class.side_effect = Exception("API error")

        from agents.orchestrator_agent import OrchestratorAgent

        orchestrator = OrchestratorAgent(ticker="SPY")
        result = orchestrator._run_morningstaretf_agent()

        assert result is None
