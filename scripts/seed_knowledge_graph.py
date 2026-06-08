#!/usr/bin/env python3
"""
Seed the Neo4j knowledge graph with GICS sector/industry/macro data
and ~80 major stock tickers.

Run once after Neo4j starts:
    python scripts/seed_knowledge_graph.py

The script is idempotent — re-running it will not create duplicate nodes
because all writes use MERGE in Neo4j and seed_default_data() is
additive in NetworkX.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path when run from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.knowledge_graph import StockKnowledgeGraph
from infrastructure.config import Config


def main():
    print("Seeding knowledge graph...")
    print(f"  Neo4j enabled : {Config.NEO4J_ENABLED}")
    print(f"  Neo4j URI     : {Config.NEO4J_URI}")

    kg = StockKnowledgeGraph()

    node_count = kg._graph.number_of_nodes()
    edge_count = kg._graph.number_of_edges()
    print(f"  In-memory graph: {node_count} nodes, {edge_count} edges")

    if Config.NEO4J_ENABLED:
        print("  Syncing to Neo4j...")
        try:
            kg.sync_to_neo4j()
            print("  Neo4j sync complete.")
        except Exception as e:
            print(f"  Neo4j sync failed (NetworkX-only mode active): {e}")
    else:
        print("  NEO4J_ENABLED=false — skipping Neo4j sync (NetworkX-only mode).")

    # Spot-check a few tickers
    samples = ["AAPL", "JPM", "NEE", "XOM", "TSLA", "UNKNOWN"]
    print("\nSpot-check:")
    for ticker in samples:
        ctx = kg.get_context(ticker)
        print(
            f"  {ticker:8s} sector={ctx['sector'] or 'N/A':35s} "
            f"rate_sensitive={ctx['is_rate_sensitive']}  "
            f"cyclical={ctx['is_cyclical']}"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
