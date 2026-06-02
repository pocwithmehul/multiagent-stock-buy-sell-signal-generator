import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from stock_signal_agent import StockSignalAgent


def main():
    parser = argparse.ArgumentParser(description="Stock Buy/Sell Signal Agent")
    parser.add_argument("--ticker", required=False, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--days", type=int, default=365, help="Number of past days to analyze (default: 365)")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use (default: gpt-4o-mini)")
    parser.add_argument("--base-url", default=None, help="Base URL for local/custom API (e.g. http://localhost:11434 for Ollama)")
    parser.add_argument("--multi-agent", action="store_true", help="Use multi-agent mode with specialized agents")
    parser.add_argument("--kafka", action="store_true", help="Enable Kafka streaming (or set kafka.enabled=true in application.yml)")
    parser.add_argument("--qdrant", action="store_true", help="Enable Qdrant vector storage (or set qdrant.enabled=true in application.yml)")
    parser.add_argument("--verbose", action="store_true", help="Include sub-agent details in output (multi-agent mode)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode to see data fetched by each agent")
    parser.add_argument("--nogui", action="store_true", help="Disable GUI dashboard (CLI mode only, requires --ticker)")
    parser.add_argument("--react", action="store_true", help="Use React dashboard instead of Streamlit (default: Streamlit)")
    args = parser.parse_args()

    # Set DEBUG environment variable based on flag
    if args.debug:
        os.environ["DEBUG"] = "true"

    # If no ticker and not nogui, launch dashboard
    if not args.ticker and not args.nogui:
        _launch_dashboard(use_react=args.react)
        return

    # If nogui but no ticker, show error
    if args.nogui and not args.ticker:
        parser.error("--ticker is required when using --nogui")

    # Check if multi-agent mode should be used (CLI flag OR config setting)
    from infrastructure.config import Config
    use_multi_agent = args.multi_agent or Config.MULTI_AGENT_ENABLED

    if use_multi_agent:
        _run_multi_agent(args)
    else:
        _run_single_agent(args)


def _launch_dashboard(use_react: bool = False):
    """Launch the dashboard (Streamlit by default, React with --react flag)."""
    if use_react:
        _launch_react_dashboard()
    else:
        _launch_streamlit_dashboard()


def _launch_streamlit_dashboard():
    """Launch the Streamlit dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")
    print("Launching Stock Signal Generator Dashboard (Streamlit)...", file=sys.stderr)
    print("Open http://localhost:8501 in your browser", file=sys.stderr)
    result = subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])
    if result.returncode != 0:
        fallback_port = "8502"
        print(f"Retrying Streamlit on port {fallback_port}...", file=sys.stderr)
        print(f"Open http://localhost:{fallback_port} in your browser", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "streamlit", "run", dashboard_path, "--server.port", fallback_port]
        )
    if result.returncode != 0:
        print("", file=sys.stderr)
        print(
            "Error: Streamlit dashboard failed to start.",
            file=sys.stderr,
        )
        print(
            "If port 8501 is unavailable or blocked, try:",
            file=sys.stderr,
        )
        print(
            f"  {sys.executable} -m streamlit run {dashboard_path} --server.port 8502",
            file=sys.stderr,
        )
        print(
            "Or run CLI mode directly:",
            file=sys.stderr,
        )
        print(
            "  python main.py --nogui --ticker AAPL",
            file=sys.stderr,
        )
        sys.exit(result.returncode)


def _launch_react_dashboard():
    """Launch the React dashboard."""
    frontend_path = Path(__file__).parent / "frontend"

    if not frontend_path.exists():
        print("Error: frontend/ directory not found.", file=sys.stderr)
        print("Please run 'cd frontend && npm install' first.", file=sys.stderr)
        sys.exit(1)

    # Check if node_modules exists
    node_modules = frontend_path / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...", file=sys.stderr)
        result = subprocess.run(
            ["npm", "install"],
            cwd=frontend_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error installing dependencies: {result.stderr}", file=sys.stderr)
            sys.exit(1)

    print("Launching Stock Signal Generator Dashboard (React)...", file=sys.stderr)
    print("Open http://localhost:3000 in your browser", file=sys.stderr)
    print("", file=sys.stderr)
    print("Note: Make sure the API server is running on port 8000", file=sys.stderr)
    print("      Run 'python -m uvicorn api:app --reload' in another terminal", file=sys.stderr)

    try:
        subprocess.run(["npm", "run", "dev"], cwd=frontend_path)
    except KeyboardInterrupt:
        print("\nReact dashboard stopped.", file=sys.stderr)


def _run_single_agent(args):
    """Original single-agent mode (backward compatible)."""
    agent = StockSignalAgent(
        stock_ticker=args.ticker,
        past_days=args.days,
        model=args.model,
        api_base=args.base_url,
    )

    print(f"Analyzing {args.ticker.upper()} (past {args.days} days)...", file=sys.stderr)
    agent.execute()

    signal = agent.get_signal()
    print(json.dumps(signal, indent=2))


def _run_multi_agent(args):
    """Multi-agent mode with orchestrator."""
    from agents.orchestrator_agent import OrchestratorAgent
    from infrastructure.config import Config

    kafka_producer = None
    qdrant_store = None
    embedder = None

    # Determine if Kafka/Qdrant should be enabled
    # CLI flags override config settings; config settings are used as defaults
    use_kafka = args.kafka or Config.KAFKA_ENABLED
    use_qdrant = args.qdrant or Config.QDRANT_ENABLED

    # Initialize Kafka if enabled (via CLI flag OR config)
    if use_kafka:
        try:
            from infrastructure.kafka_producer import KafkaProducerWrapper
            kafka_producer = KafkaProducerWrapper()
            print(f"  [Init] Kafka connected to {Config.KAFKA_BOOTSTRAP_SERVERS}", file=sys.stderr)
            print(f"  [Init] Kafka topics ensured: {', '.join(KafkaProducerWrapper.DEFAULT_TOPICS)}", file=sys.stderr)
        except Exception as e:
            print(f"  [Init] Kafka not available: {e}", file=sys.stderr)
            print("  [Init] Continuing without Kafka...", file=sys.stderr)

    # Initialize Qdrant if enabled (via CLI flag OR config)
    if use_qdrant:
        try:
            from infrastructure.qdrant_store import QdrantStore
            from infrastructure.embeddings import Embedder
            qdrant_store = QdrantStore()
            embedder = Embedder()
            if embedder.is_available():
                print(f"  [Init] Qdrant connected to {Config.QDRANT_HOST}:{Config.QDRANT_PORT}", file=sys.stderr)
                print(f"  [Init] Qdrant collections ensured: {', '.join(QdrantStore.DEFAULT_COLLECTIONS)}", file=sys.stderr)
            else:
                reason = embedder.disabled_reason or "embedding model unavailable"
                print(f"  [Init] Qdrant disabled: {reason}", file=sys.stderr)
                print("  [Init] Continuing without Qdrant...", file=sys.stderr)
                qdrant_store = None
                embedder = None
        except Exception as e:
            print(f"  [Init] Qdrant not available: {e}", file=sys.stderr)
            print("  [Init] Continuing without Qdrant...", file=sys.stderr)

    print(f"Analyzing {args.ticker.upper()} with multi-agent system (past {args.days} days)...", file=sys.stderr)

    orchestrator = OrchestratorAgent(
        ticker=args.ticker,
        past_days=args.days,
        model=args.model,
        api_base=args.base_url,
        kafka_enabled=use_kafka and kafka_producer is not None,
        kafka_producer=kafka_producer,
        qdrant_enabled=use_qdrant and qdrant_store is not None,
        qdrant_store=qdrant_store,
        embedder=embedder,
        verbose=args.verbose,
    )

    orchestrator.execute()
    signal = orchestrator.get_signal()
    print(json.dumps(signal, indent=2, default=str))

    # Cleanup
    if kafka_producer:
        kafka_producer.close()


if __name__ == "__main__":
    main()
