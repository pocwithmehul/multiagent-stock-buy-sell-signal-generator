#!/usr/bin/env bash
# start.sh — Start all Docker Compose services with optional custom data path.
#
# Usage:
#   ./scripts/start.sh                          # named volumes (default)
#   ./scripts/start.sh --data-path /my/data     # bind mounts under /my/data
#
# With a custom data path the script creates the required subdirectories and
# exports per-service volume env vars before calling docker compose.

set -euo pipefail

DATA_PATH=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-path)
      DATA_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--data-path /absolute/path]"
      exit 1
      ;;
  esac
done

# If DATA_PATH is set, derive per-service bind mount paths
if [[ -n "$DATA_PATH" ]]; then
  if [[ "$DATA_PATH" != /* ]]; then
    echo "Error: --data-path must be an absolute path (got: $DATA_PATH)"
    exit 1
  fi

  export POSTGRES_VOLUME="$DATA_PATH/postgres"
  export KAFKA_VOLUME="$DATA_PATH/kafka"
  export QDRANT_VOLUME="$DATA_PATH/qdrant"
  export ZOOKEEPER_DATA_VOLUME="$DATA_PATH/zookeeper/data"
  export ZOOKEEPER_LOG_VOLUME="$DATA_PATH/zookeeper/log"

  mkdir -p \
    "$POSTGRES_VOLUME" \
    "$KAFKA_VOLUME" \
    "$QDRANT_VOLUME" \
    "$ZOOKEEPER_DATA_VOLUME" \
    "$ZOOKEEPER_LOG_VOLUME"

  echo "Using bind mounts under: $DATA_PATH"
  echo "  postgres  → $POSTGRES_VOLUME"
  echo "  kafka     → $KAFKA_VOLUME"
  echo "  qdrant    → $QDRANT_VOLUME"
  echo "  zookeeper → $ZOOKEEPER_DATA_VOLUME"
  echo "             $ZOOKEEPER_LOG_VOLUME"
else
  echo "Using named Docker volumes (default)"
fi

echo ""
# Change to project root (script may be called from any directory)
cd "$(dirname "$0")/.."

docker compose up -d

echo ""
docker compose ps
