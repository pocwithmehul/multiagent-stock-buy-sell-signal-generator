#!/usr/bin/env python3
"""Initialize Qdrant collections, Kafka topics, and Unleash feature flags on service startup.

Runs as a Docker init container to eagerly create all collections, topics, and flags
so they appear in dashboards immediately without needing an analysis run first.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# ── Configuration (mirrors infrastructure/config.py env var names) ────────────
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
UNLEASH_URL = os.getenv("UNLEASH_URL", "http://localhost:4242")
UNLEASH_ADMIN_TOKEN = os.getenv("UNLEASH_ADMIN_TOKEN", "*:*.unleash-insecure-admin-api-token")
UNLEASH_PROJECT = os.getenv("UNLEASH_PROJECT", "default")
UNLEASH_ENVIRONMENT = os.getenv("UNLEASH_ENVIRONMENT", "development")

# Default collections (mirrors QdrantStore.DEFAULT_COLLECTIONS)
QDRANT_COLLECTIONS = [
    os.getenv("QDRANT_COLLECTION_NEWS", "stock_news"),
    os.getenv("QDRANT_COLLECTION_FILINGS", "sec_filings"),
    os.getenv("QDRANT_COLLECTION_PRICES", "stock_prices"),
]
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# Default topics (mirrors KafkaProducerWrapper.DEFAULT_TOPICS)
KAFKA_TOPICS = [
    os.getenv("KAFKA_TOPIC_PRICES", "stock-prices"),
    os.getenv("KAFKA_TOPIC_NEWS", "stock-news"),
    os.getenv("KAFKA_TOPIC_FILINGS", "sec-filings"),
]

# All feature flags with their default enabled state (mirrors FEATURE_FLAG_DEFAULTS)
FEATURE_FLAGS = {
    # Core analysis
    "single_stock_analysis": True,
    "watchlist_analysis": False,
    "premarket_analysis": False,
    "aftermarket_analysis": False,
    # ML pipeline
    "ml_analysis": True,
    # Per-agent flags (all enabled by default)
    "agent_technical": True,
    "agent_news": True,
    "agent_sec": True,
    "agent_sentiment": True,
    "agent_zacks": True,
    "agent_tipranks": True,
    "agent_seekingalpha": True,
    "agent_insider": True,
    "agent_motleyfool": True,
    "agent_stockstory": True,
    "agent_yahoofinance": True,
    "agent_morningstar": True,
    "agent_gurufocus": True,
    "agent_tradingview": True,
    "agent_stockrover": True,
    "agent_simplywallst": True,
    "agent_alphaspread": True,
    "agent_factset": True,
    "agent_capitaliq": True,
    "agent_marketbeat": True,
    "agent_refinitiv": True,
    "agent_macrotrends": True,
    "agent_ycharts": True,
    "agent_koyfin": True,
    "agent_valueline": True,
    "agent_xtwitter": True,
    "agent_facebook": True,
    "agent_instagram": True,
    "agent_cnbc": True,
    "agent_bloomberg": True,
    "agent_wsj": True,
    "agent_marketwatch": True,
    "agent_foxbusiness": True,
    "agent_barrons": True,
    "agent_insidermonkey": True,
    "agent_quiverquant": True,
    "agent_dataroma": True,
    "agent_openinsider": True,
    "agent_whalewisdom": True,
    "agent_etfcom": True,
    "agent_etfdb": True,
    "agent_globalxetf": True,
    "agent_arkinvest": True,
    "agent_morningstaretf": True,
    "agent_reddit": True,
    "agent_stocktwits": True,
    "agent_options_flow": True,
}


# ── Qdrant ─────────────────────────────────────────────────────────────────────

def init_qdrant() -> bool:
    """Create default Qdrant collections if they don't exist."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    for attempt in range(1, 13):  # up to 60s
        try:
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            client.get_collections()  # probe
            break
        except Exception as e:
            if attempt == 12:
                print(f"  [qdrant] ERROR: not ready after 60s: {e}", file=sys.stderr)
                return False
            print(f"  [qdrant] Not ready (attempt {attempt}/12), retrying in 5s...")
            time.sleep(5)

    try:
        existing = {c.name for c in client.get_collections().collections}
        for name in QDRANT_COLLECTIONS:
            if name not in existing:
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                print(f"  [qdrant] Created collection: {name}")
            else:
                print(f"  [qdrant] Already exists: {name}")
        return True
    except Exception as e:
        print(f"  [qdrant] ERROR: {e}", file=sys.stderr)
        return False


# ── Kafka ──────────────────────────────────────────────────────────────────────

def init_kafka() -> bool:
    """Create default Kafka topics if they don't exist."""
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError

    print(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
    for attempt in range(1, 13):  # up to 60s
        try:
            admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
            admin.list_topics()  # probe
            break
        except Exception as e:
            if attempt == 12:
                print(f"  [kafka] ERROR: not ready after 60s: {e}", file=sys.stderr)
                return False
            print(f"  [kafka] Not ready (attempt {attempt}/12), retrying in 5s...")
            time.sleep(5)

    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

        try:
            existing = set(admin.list_topics())
            to_create = [
                NewTopic(name=t, num_partitions=1, replication_factor=1)
                for t in KAFKA_TOPICS
                if t not in existing
            ]
            if to_create:
                admin.create_topics(to_create)
                for t in to_create:
                    print(f"  [kafka] Created topic: {t.name}")
            for t in KAFKA_TOPICS:
                if t in existing:
                    print(f"  [kafka] Already exists: {t}")
        except TopicAlreadyExistsError:
            print("  [kafka] Topics already exist")
        finally:
            admin.close()

        return True
    except Exception as e:
        print(f"  [kafka] ERROR: {e}", file=sys.stderr)
        return False


# ── Unleash ────────────────────────────────────────────────────────────────────

def _unleash_request(method: str, path: str, body: dict = None) -> tuple[int, dict]:
    """Make an authenticated request to the Unleash admin API."""
    url = f"{UNLEASH_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": UNLEASH_ADMIN_TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw.strip() else {})


def _unleash_ready() -> bool:
    """Check if Unleash is up and accepting requests."""
    try:
        req = urllib.request.Request(f"{UNLEASH_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def init_unleash() -> bool:
    """Create all feature flags in Unleash and set their enabled state."""
    print(f"Connecting to Unleash at {UNLEASH_URL}...")

    # Wait up to 30s for Unleash to be ready
    for _ in range(6):
        if _unleash_ready():
            break
        print("  [unleash] Not ready yet, waiting 5s...")
        time.sleep(5)
    else:
        print("  [unleash] ERROR: Unleash not reachable after 30s", file=sys.stderr)
        return False

    project = UNLEASH_PROJECT
    env = UNLEASH_ENVIRONMENT
    created = skipped = errors = 0

    for name, enabled in FEATURE_FLAGS.items():
        # 1. Create the flag (idempotent — 409 means it already exists)
        status, _ = _unleash_request(
            "POST",
            f"/api/admin/projects/{project}/features",
            {"name": name, "type": "release", "impressionData": False},
        )
        if status in (200, 201):
            created += 1
            print(f"  [unleash] Created: {name} (enabled={enabled})")
        elif status == 409:
            skipped += 1
        else:
            errors += 1
            print(f"  [unleash] WARNING: unexpected status {status} for {name}", file=sys.stderr)
            continue

        # 2. Set enabled state in the target environment
        action = "on" if enabled else "off"
        status, _ = _unleash_request(
            "POST",
            f"/api/admin/projects/{project}/features/{name}/environments/{env}/{action}",
        )
        if status not in (200, 201):
            print(f"  [unleash] WARNING: could not set {name} {action} (status={status})", file=sys.stderr)

    print(f"  [unleash] Done — created: {created}, already existed: {skipped}, errors: {errors}")
    return errors == 0


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== Infrastructure Init ===")

    qdrant_ok = init_qdrant()
    kafka_ok = init_kafka()
    unleash_ok = init_unleash()

    if qdrant_ok and kafka_ok and unleash_ok:
        print("\nAll infrastructure initialized successfully.")
        sys.exit(0)
    else:
        failed = [name for name, ok in [("Qdrant", qdrant_ok), ("Kafka", kafka_ok), ("Unleash", unleash_ok)] if not ok]
        print(f"\nFailed to initialize: {', '.join(failed)}. Will retry...", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
