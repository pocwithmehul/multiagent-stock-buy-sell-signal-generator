"""Observability module with Langfuse and LiteLLM callback integration."""

import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Any
from functools import wraps

import litellm
from litellm.integrations.custom_logger import CustomLogger


# Environment variables for configuration
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Try to import langfuse
langfuse_client = None
if LANGFUSE_ENABLED and LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        from langfuse import Langfuse
        langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        print(f"[Observability] Langfuse enabled at {LANGFUSE_HOST}")
    except ImportError:
        print("[Observability] Langfuse not installed. Run: pip install langfuse")
    except Exception as e:
        print(f"[Observability] Langfuse init failed: {e}")


class StockSignalLogger(CustomLogger):
    """Custom LiteLLM logger for observability."""

    def __init__(self):
        self.call_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
        self.current_trace = None

    def log_pre_api_call(self, model, messages, kwargs):
        """Called before LLM API call."""
        self.call_count += 1
        print(f"[LLM] Calling {model}...")

    def log_post_api_call(self, kwargs, response_obj, start_time, end_time):
        """Called after successful LLM API call."""
        latency = end_time - start_time
        self.total_latency += latency

        # Extract usage info
        usage = getattr(response_obj, "usage", None)
        if usage:
            tokens = getattr(usage, "total_tokens", 0)
            self.total_tokens += tokens
            print(f"[LLM] Completed in {latency:.2f}s, {tokens} tokens")

        # Log to Langfuse if enabled
        if langfuse_client and self.current_trace:
            try:
                model = kwargs.get("model", "unknown")
                messages = kwargs.get("messages", [])
                self.current_trace.generation(
                    name="llm_call",
                    model=model,
                    input=messages,
                    output=response_obj.choices[0].message.content if response_obj.choices else "",
                    usage={
                        "input": getattr(usage, "prompt_tokens", 0) if usage else 0,
                        "output": getattr(usage, "completion_tokens", 0) if usage else 0,
                    },
                    metadata={"latency_ms": int(latency * 1000)},
                )
            except Exception as e:
                print(f"[Observability] Langfuse logging failed: {e}")

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        """Called on LLM API failure."""
        latency = end_time - start_time
        error = str(response_obj) if response_obj else "Unknown error"
        print(f"[LLM] Failed after {latency:.2f}s: {error}")

        if langfuse_client and self.current_trace:
            try:
                self.current_trace.event(
                    name="llm_error",
                    metadata={"error": error, "latency_ms": int(latency * 1000)},
                )
            except Exception:
                pass

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        """Called on successful completion."""
        pass  # Already handled in log_post_api_call

    def get_stats(self) -> dict:
        """Get accumulated statistics."""
        return {
            "call_count": self.call_count,
            "total_tokens": self.total_tokens,
            "total_latency_seconds": round(self.total_latency, 2),
            "avg_latency_seconds": round(self.total_latency / max(self.call_count, 1), 2),
        }

    def reset_stats(self):
        """Reset statistics."""
        self.call_count = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0


# Global logger instance
stock_logger = StockSignalLogger()


def setup_observability():
    """Initialize observability with LiteLLM callbacks."""
    # Add custom logger to LiteLLM
    litellm.callbacks = [stock_logger]

    # Enable verbose logging if DEBUG mode
    if os.getenv("DEBUG", "false").lower() == "true":
        litellm.set_verbose = True

    print("[Observability] LiteLLM callbacks configured")

    if langfuse_client:
        print("[Observability] Langfuse tracing enabled")
    else:
        print("[Observability] Langfuse disabled (set LANGFUSE_ENABLED=true to enable)")


@contextmanager
def track_agent_execution(ticker: str, mode: str):
    """Context manager to track agent execution with Langfuse."""
    start_time = time.time()
    trace = None

    # Create Langfuse trace if enabled
    if langfuse_client:
        try:
            trace = langfuse_client.trace(
                name="signal_generation",
                metadata={
                    "ticker": ticker,
                    "mode": mode,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            stock_logger.current_trace = trace
        except Exception as e:
            print(f"[Observability] Failed to create trace: {e}")

    try:
        yield trace
    finally:
        end_time = time.time()
        duration = end_time - start_time

        # Log completion
        stats = stock_logger.get_stats()
        print(f"[Observability] {ticker} ({mode}) completed in {duration:.2f}s")
        print(f"[Observability] LLM calls: {stats['call_count']}, tokens: {stats['total_tokens']}")

        # Update Langfuse trace
        if trace:
            try:
                trace.update(
                    output={
                        "duration_seconds": round(duration, 2),
                        "llm_stats": stats,
                    },
                )
            except Exception:
                pass

        # Reset for next request
        stock_logger.current_trace = None
        stock_logger.reset_stats()

        # Flush Langfuse
        if langfuse_client:
            try:
                langfuse_client.flush()
            except Exception:
                pass


def track_function(name: Optional[str] = None):
    """Decorator to track function execution in Langfuse."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = name or func.__name__
            start_time = time.time()

            # Create span if trace exists
            span = None
            if langfuse_client and stock_logger.current_trace:
                try:
                    span = stock_logger.current_trace.span(name=func_name)
                except Exception:
                    pass

            try:
                result = func(*args, **kwargs)

                if span:
                    try:
                        span.end(output={"status": "success"})
                    except Exception:
                        pass

                return result
            except Exception as e:
                if span:
                    try:
                        span.end(output={"status": "error", "error": str(e)})
                    except Exception:
                        pass
                raise
            finally:
                duration = time.time() - start_time
                if duration > 1.0:  # Only log slow operations
                    print(f"[Observability] {func_name} took {duration:.2f}s")

        return wrapper
    return decorator


def log_agent_output(agent_name: str, output: dict):
    """Log agent output to Langfuse."""
    if langfuse_client and stock_logger.current_trace:
        try:
            stock_logger.current_trace.event(
                name=f"agent_output_{agent_name}",
                metadata={
                    "agent": agent_name,
                    "signal": output.get("signal"),
                    "confidence": output.get("confidence"),
                },
            )
        except Exception:
            pass


def get_observability_stats() -> dict:
    """Get current observability statistics."""
    return {
        "langfuse_enabled": langfuse_client is not None,
        "llm_stats": stock_logger.get_stats(),
    }
