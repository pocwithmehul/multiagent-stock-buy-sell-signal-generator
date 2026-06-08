"""Tests for FastAPI application."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime


class TestValidateUsTicker:
    """Test validate_us_ticker function directly."""

    @patch('api.yf')
    def test_invalid_ticker_format_too_long(self, mock_yf):
        """Test ticker format validation rejects long tickers."""
        from api import validate_us_ticker

        is_valid, message = validate_us_ticker("TOOLONG")

        assert is_valid is False
        assert "Invalid ticker format" in message

    @patch('api.yf')
    def test_invalid_ticker_format_numbers(self, mock_yf):
        """Test ticker format validation rejects numbers."""
        from api import validate_us_ticker

        is_valid, message = validate_us_ticker("ABC123")

        assert is_valid is False
        assert "Invalid ticker format" in message

    @patch('api.yf')
    def test_ticker_not_found_no_info(self, mock_yf):
        """Test ticker not found when info is empty."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = None
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("FAKE")

        assert is_valid is False
        assert "not found" in message

    @patch('api.yf')
    def test_ticker_not_found_no_price(self, mock_yf):
        """Test ticker not found when no price data."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = {"shortName": "Test Co"}  # No price fields
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("FAKE")  # 4 chars, valid format

        assert is_valid is False
        assert "not found" in message

    @patch('api.yf')
    def test_ticker_exception_in_check(self, mock_yf):
        """Test ticker validation handles exceptions in _check_ticker."""
        from api import validate_us_ticker

        mock_yf.Ticker.side_effect = Exception("Network error")

        is_valid, message = validate_us_ticker("AAPL")

        assert is_valid is False
        assert "not found" in message

    @patch('api.yf')
    def test_ticker_dot_format_conversion(self, mock_yf):
        """Test BRK.B style tickers convert to BRK-B."""
        from api import validate_us_ticker

        # First call (BRK.B) fails, second call (BRK-B) succeeds
        mock_ticker_fail = MagicMock()
        mock_ticker_fail.info = None

        mock_ticker_success = MagicMock()
        mock_ticker_success.info = {
            "currentPrice": 400.0,
            "shortName": "Berkshire Hathaway",
            "exchange": "NYQ",
            "market": "us_market",
        }

        mock_yf.Ticker.side_effect = [mock_ticker_fail, mock_ticker_success]

        is_valid, message = validate_us_ticker("BRK.B")

        assert is_valid is True
        assert message == "Berkshire Hathaway"

    @patch('api.yf')
    def test_ticker_non_us_exchange_rejected(self, mock_yf):
        """Test non-US exchange ticker is rejected."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 100.0,
            "shortName": "Foreign Co",
            "exchange": "LSE",
            "market": "uk_market",
            "currency": "GBP",
        }
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("VOD")

        assert is_valid is False
        assert "not a US market stock" in message

    @patch('api.yf')
    def test_ticker_non_us_exchange_usd_allowed(self, mock_yf):
        """Test non-standard exchange but USD currency is allowed."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 50.0,
            "shortName": "Special Fund",
            "exchange": "OTHER",
            "market": "other_market",
            "currency": "USD",
        }
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("FUND")

        assert is_valid is True
        assert message == "Special Fund"

    @patch('api.yf')
    def test_ticker_us_exchange_valid(self, mock_yf):
        """Test valid US exchange ticker."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "regularMarketPrice": 175.0,
            "shortName": "Apple Inc.",
            "exchange": "NMS",
            "market": "us_market",
        }
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("AAPL")

        assert is_valid is True
        assert message == "Apple Inc."

    @patch('api.yf')
    def test_ticker_previous_close_price_valid(self, mock_yf):
        """Test ticker with only previousClose price is valid."""
        from api import validate_us_ticker

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "previousClose": 150.0,
            "shortName": "Test Corp",
            "exchange": "NYSE",
        }
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("TEST")

        assert is_valid is True

    @patch('api.yf')
    def test_ticker_outer_exception(self, mock_yf):
        """Test outer exception handling in validate_us_ticker."""
        from api import validate_us_ticker

        # Create a mock info dict that raises on .get() after initial checks pass
        class ExplodingDict(dict):
            def __init__(self):
                super().__init__()
                self['currentPrice'] = 100.0
                self._call_count = 0

            def get(self, key, default=None):
                self._call_count += 1
                # First call gets price, second call (for exchange) explodes
                if self._call_count > 3:  # After price checks
                    raise RuntimeError("Outer error")
                return super().get(key, default)

        mock_ticker = MagicMock()
        mock_ticker.info = ExplodingDict()
        mock_yf.Ticker.return_value = mock_ticker

        is_valid, message = validate_us_ticker("TEST")

        assert is_valid is False
        assert "Error validating" in message


class TestSignalRequestValidator:
    """Test SignalRequest field validators."""

    def test_ticker_format_validator_rejects_invalid(self):
        """Test field_validator rejects invalid ticker format."""
        from api import app
        client = TestClient(app)

        # The pydantic validator at line 91 handles this
        response = client.post("/signal", json={
            "ticker": "123ABC",  # Invalid format
            "mode": "single",
        })

        assert response.status_code == 422


class TestLifespan:
    """Test application lifespan."""

    @patch('api.setup_observability')
    def test_lifespan_startup_shutdown(self, mock_setup):
        """Test lifespan context manager runs startup and shutdown."""
        from api import app
        from fastapi.testclient import TestClient

        # TestClient automatically handles lifespan
        with TestClient(app) as client:
            # Startup should have run
            mock_setup.assert_called_once()

            # Make a request to verify app is running
            response = client.get("/health")
            assert response.status_code == 200


class TestExecuteFunctions:
    """Test _execute_single_agent and _execute_multi_agent functions."""

    @patch('api.StockSignalAgent')
    def test_execute_single_agent(self, mock_agent_class):
        """Test _execute_single_agent function."""
        from api import _execute_single_agent

        mock_agent = MagicMock()
        mock_agent.get_signal.return_value = {
            "signal": "BUY",
            "confidence": 0.85,
        }
        mock_agent_class.return_value = mock_agent

        result = _execute_single_agent("AAPL", 30, "gpt-4o-mini")

        mock_agent_class.assert_called_once_with(
            stock_ticker="AAPL",
            past_days=30,
            model="gpt-4o-mini",
        )
        mock_agent.execute.assert_called_once()
        assert result["signal"] == "BUY"

    @patch('api.OrchestratorAgent')
    def test_execute_multi_agent(self, mock_orchestrator_class):
        """Test _execute_multi_agent function."""
        from api import _execute_multi_agent

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_signal.return_value = {
            "signal": "HOLD",
            "confidence": 0.70,
            "agents_used": 47,
        }
        mock_orchestrator_class.return_value = mock_orchestrator

        result = _execute_multi_agent("TSLA", 60, "gpt-4o", True)

        mock_orchestrator_class.assert_called_once_with(
            ticker="TSLA",
            past_days=60,
            model="gpt-4o",
            verbose=True,
        )
        mock_orchestrator.execute.assert_called_once()
        assert result["signal"] == "HOLD"
        assert result["agents_used"] == 47


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test health endpoint returns healthy status."""
        from api import app
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"


class TestSignalEndpoint:
    """Test signal generation endpoints."""

    @patch('api.validate_us_ticker')
    @patch('api._execute_single_agent')
    def test_generate_signal_single_mode(self, mock_execute, mock_validate):
        """Test POST /signal with single agent mode."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Apple Inc.")
        mock_execute.return_value = {
            "signal": "BUY",
            "confidence": 0.85,
            "target_price": 175.0,
            "reasoning": "Strong momentum",
        }

        response = client.post("/signal", json={
            "ticker": "AAPL",
            "days": 30,
            "mode": "single",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["signal"] == "BUY"
        assert data["confidence"] == 0.85
        assert data["mode"] == "single"

    @patch('api.validate_us_ticker')
    @patch('api._execute_multi_agent')
    def test_generate_signal_multi_mode(self, mock_execute, mock_validate):
        """Test POST /signal with multi agent mode."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Alphabet Inc.")
        mock_execute.return_value = {
            "signal": "HOLD",
            "confidence": 0.65,
            "agents_used": 44,
            "reasoning": "Mixed signals",
        }

        response = client.post("/signal", json={
            "ticker": "GOOGL",
            "days": 60,
            "mode": "multi",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "GOOGL"
        assert data["signal"] == "HOLD"
        assert data["mode"] == "multi"
        assert data["agents_used"] == 44

    @patch('api.validate_us_ticker')
    @patch('api._execute_multi_agent')
    def test_generate_signal_get_endpoint(self, mock_execute, mock_validate):
        """Test GET /signal/{ticker} endpoint."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Microsoft Corporation")
        mock_execute.return_value = {
            "signal": "SELL",
            "confidence": 0.75,
        }

        response = client.get("/signal/MSFT?days=30&mode=multi")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "MSFT"
        assert data["signal"] == "SELL"

    @patch('api.validate_us_ticker')
    @patch('api._execute_single_agent')
    def test_generate_signal_with_error(self, mock_execute, mock_validate):
        """Test signal generation handles errors."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Test Inc.")
        mock_execute.side_effect = Exception("API Error")

        response = client.post("/signal", json={
            "ticker": "TEST",
            "mode": "single",
        })

        assert response.status_code == 500
        assert "API Error" in response.json()["detail"]

    def test_invalid_mode(self):
        """Test validation rejects invalid mode."""
        from api import app
        client = TestClient(app)

        response = client.post("/signal", json={
            "ticker": "AAPL",
            "mode": "invalid",
        })

        assert response.status_code == 422  # Validation error

    def test_invalid_days(self):
        """Test validation rejects invalid days."""
        from api import app
        client = TestClient(app)

        response = client.post("/signal", json={
            "ticker": "AAPL",
            "days": 0,  # Must be >= 1
        })

        assert response.status_code == 422

    @patch('api.validate_us_ticker')
    @patch('api._execute_multi_agent')
    def test_verbose_includes_agent_details(self, mock_execute, mock_validate):
        """Test verbose mode includes agent details."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Apple Inc.")
        mock_execute.return_value = {
            "signal": "BUY",
            "confidence": 0.8,
            "agent_details": {"technical": {"signal": "BULLISH"}},
        }

        response = client.post("/signal", json={
            "ticker": "AAPL",
            "verbose": True,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["agent_details"] is not None

    @patch('api.validate_us_ticker')
    @patch('api._execute_multi_agent')
    def test_non_verbose_excludes_agent_details(self, mock_execute, mock_validate):
        """Test non-verbose mode excludes agent details."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Apple Inc.")
        mock_execute.return_value = {
            "signal": "BUY",
            "confidence": 0.8,
            "agent_details": {"technical": {"signal": "BULLISH"}},
        }

        response = client.post("/signal", json={
            "ticker": "AAPL",
            "verbose": False,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["agent_details"] is None


class TestTickerValidation:
    """Test ticker validation."""

    @patch('api.validate_us_ticker')
    def test_validate_valid_ticker(self, mock_validate):
        """Test validation of valid ticker."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (True, "Apple Inc.")

        response = client.get("/validate/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["valid"] is True
        assert data["name"] == "Apple Inc."

    @patch('api.validate_us_ticker')
    def test_validate_invalid_ticker(self, mock_validate):
        """Test validation of invalid ticker."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (False, "Ticker 'INVALID' not found in market data.")

        response = client.get("/validate/INVALID")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["name"] is None

    @patch('api.validate_us_ticker')
    def test_signal_rejects_invalid_ticker(self, mock_validate):
        """Test that signal endpoint rejects invalid tickers."""
        from api import app
        client = TestClient(app)

        mock_validate.return_value = (False, "Ticker 'FAKE' not found in market data.")

        response = client.post("/signal", json={"ticker": "FAKE"})

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]


class TestScheduleEndpoints:
    """Test scheduler CRUD and due-run API endpoints."""

    @patch("api._require_schedule_store")
    def test_list_schedules(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.list_schedules.return_value = [{"id": 1, "name": "weekday_buy_now"}]
        mock_store_factory.return_value = mock_store

        response = client.get("/schedules")
        assert response.status_code == 200
        assert response.json()["schedules"][0]["id"] == 1

    @patch("api._require_schedule_store")
    def test_upsert_schedule(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.upsert_schedule.return_value = {"id": 1, "name": "weekday_buy_now"}
        mock_store_factory.return_value = mock_store

        payload = {
            "name": "weekday_buy_now",
            "session_type": "pre_market",
            "run_time": "06:00:00",
            "timezone": "America/New_York",
            "weekdays_only": True,
            "email": "alerts@example.com",
            "model": "gpt-4o-mini",
            "days": 90,
            "top_n": 10,
            "enabled": True,
        }
        response = client.post("/schedules", json=payload)
        assert response.status_code == 200
        assert response.json()["schedule"]["name"] == "weekday_buy_now"

    @patch("api._require_schedule_store")
    def test_get_due_schedules(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.get_due_schedules.return_value = [{"id": 99}]
        mock_store_factory.return_value = mock_store

        response = client.get("/schedules/due?limit=5")
        assert response.status_code == 200
        assert response.json()["schedules"][0]["id"] == 99

    @patch("api._require_schedule_store")
    def test_mark_schedule_result_not_found(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.mark_schedule_run.return_value = None
        mock_store_factory.return_value = mock_store

        response = client.post("/schedules/123/run-result", json={"status": "success"})
        assert response.status_code == 404

    @patch("api._require_schedule_store")
    def test_delete_schedule(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.delete_schedule.return_value = True
        mock_store_factory.return_value = mock_store

        response = client.delete("/schedules/1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    @patch("api._require_watchlist_store")
    def test_list_watchlist(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.list_watchlist.return_value = ["AAPL", "MSFT"]
        mock_store_factory.return_value = mock_store

        response = client.get("/watchlist")
        assert response.status_code == 200
        assert response.json()["tickers"] == ["AAPL", "MSFT"]

    @patch("api._require_watchlist_store")
    def test_replace_watchlist(self, mock_store_factory):
        from api import app
        client = TestClient(app)

        mock_store = MagicMock()
        mock_store.replace_watchlist.return_value = ["AAPL", "NVDA"]
        mock_store_factory.return_value = mock_store

        response = client.put("/watchlist", json={"tickers": ["aapl", "nvda"]})
        assert response.status_code == 200
        assert response.json()["tickers"] == ["AAPL", "NVDA"]


class TestAPIDocumentation:
    """Test API documentation."""

    def test_openapi_schema(self):
        """Test OpenAPI schema is available."""
        from api import app
        client = TestClient(app)

        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "Stock Signal Generator API"
        assert "/signal" in schema["paths"]
        assert "/health" in schema["paths"]
        assert "/validate/{ticker}" in schema["paths"]

    def test_docs_endpoint(self):
        """Test Swagger UI docs endpoint."""
        from api import app
        client = TestClient(app)

        response = client.get("/docs")

        assert response.status_code == 200
