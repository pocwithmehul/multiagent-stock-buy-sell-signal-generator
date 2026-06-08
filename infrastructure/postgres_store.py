"""PostgreSQL store for historical OHLCV prices."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from infrastructure.config import Config


class PostgresPriceStore:
    """Small repository for daily OHLCV cache in PostgreSQL."""

    def __init__(self):
        self.host = Config.POSTGRES_HOST
        self.port = Config.POSTGRES_PORT
        self.database = Config.POSTGRES_DATABASE
        self.user = Config.POSTGRES_USER
        self.password = Config.POSTGRES_PASSWORD
        self.sslmode = Config.POSTGRES_SSLMODE
        self.connect_timeout = Config.POSTGRES_CONNECT_TIMEOUT
        self.table = Config.POSTGRES_PRICES_TABLE

    def _connect(self):
        import psycopg2

        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
            sslmode=self.sslmode,
            connect_timeout=self.connect_timeout,
        )

    def ensure_schema(self):
        """Create table used for cached daily OHLCV data, migrating old schema if needed."""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.table} (
            ticker VARCHAR(16) NOT NULL,
            price_date DATE NOT NULL,
            open DOUBLE PRECISION NOT NULL,
            high DOUBLE PRECISION NOT NULL,
            low DOUBLE PRECISION NOT NULL,
            close DOUBLE PRECISION NOT NULL,
            adj_close DOUBLE PRECISION,
            volume BIGINT NOT NULL,
            source VARCHAR(32) NOT NULL DEFAULT 'yfinance',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (ticker, price_date)
        );
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)

                # Migrate old schema: rename 'date' column to 'price_date' if it exists
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = %s AND column_name = 'date'
                """, (self.table,))
                if cur.fetchone():
                    cur.execute(f"ALTER TABLE {self.table} RENAME COLUMN date TO price_date")

                # Add missing columns introduced in the updated schema
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = %s
                """, (self.table,))
                existing_cols = {r[0] for r in cur.fetchall()}

                if "adj_close" not in existing_cols:
                    cur.execute(f"ALTER TABLE {self.table} ADD COLUMN adj_close DOUBLE PRECISION")
                if "source" not in existing_cols:
                    cur.execute(f"ALTER TABLE {self.table} ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'yfinance'")
                if "updated_at" not in existing_cols:
                    cur.execute(f"ALTER TABLE {self.table} ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")

            conn.commit()

    @staticmethod
    def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize yfinance DataFrame columns and index."""
        if df is None or df.empty:
            return pd.DataFrame()

        normalized = df.copy()
        normalized.columns = [str(c).strip() for c in normalized.columns]
        if "Adj Close" not in normalized.columns:
            normalized["Adj Close"] = normalized.get("Close")

        expected = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        missing = [col for col in expected if col not in normalized.columns]
        if missing:
            return pd.DataFrame()

        normalized = normalized[expected].dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
        return normalized

    def upsert_prices(self, ticker: str, df: pd.DataFrame):
        """Upsert price rows from DataFrame into PostgreSQL."""
        normalized = self._normalize_history_df(df)
        if normalized.empty:
            return

        rows = []
        for idx, row in normalized.iterrows():
            rows.append(
                (
                    ticker.upper(),
                    idx.date(),
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Adj Close"]) if pd.notna(row["Adj Close"]) else None,
                    int(row["Volume"]),
                    "yfinance",
                )
            )

        upsert_sql = f"""
        INSERT INTO {self.table}
        (ticker, price_date, open, high, low, close, adj_close, volume, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, price_date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume,
            source = EXCLUDED.source,
            updated_at = NOW();
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(upsert_sql, rows)
            conn.commit()

    def load_prices(self, ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Load OHLCV price range from PostgreSQL into a DataFrame."""
        sql = f"""
        SELECT price_date, open, high, low, close, adj_close, volume
        FROM {self.table}
        WHERE ticker = %s
          AND price_date >= %s
          AND price_date <= %s
        ORDER BY price_date ASC;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (ticker.upper(), start.date(), end.date()))
                rows = cur.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            rows,
            columns=["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"],
        )
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        return df

    def query(self, question: str, model: str = None, api_base: str = None) -> dict:
        """
        Answer a natural language question about the PostgreSQL database.

        Converts the question to a SQL query via LLM (READ-only), executes it,
        and returns a human-readable answer.

        Args:
            question: Natural language question, e.g. "Which tickers have the most price history?"
            model: LiteLLM model string (defaults to gpt-4o-mini)
            api_base: Optional custom API base URL

        Returns:
            {"question": str, "sql": str, "results": list[dict], "answer": str}
        """
        _model = model or Config.DEFAULT_MODEL

        _schema = """
PostgreSQL database schema (database: stock_signal):

Table: stock_prices_daily
  ticker      VARCHAR(16)   -- stock ticker symbol e.g. AAPL
  price_date  DATE          -- trading date
  open        DOUBLE PRECISION
  high        DOUBLE PRECISION
  low         DOUBLE PRECISION
  close       DOUBLE PRECISION
  adj_close   DOUBLE PRECISION
  volume      BIGINT
  source      VARCHAR(32)   -- e.g. 'yfinance'
  updated_at  TIMESTAMPTZ
  PRIMARY KEY (ticker, price_date)

Table: stock_watchlist
  ticker      VARCHAR(16)   PRIMARY KEY
  enabled     BOOLEAN
  source      VARCHAR(32)   -- e.g. 'dashboard'
  created_at  TIMESTAMPTZ
  updated_at  TIMESTAMPTZ

Table: stock_schedule_configs
  id           SERIAL PRIMARY KEY
  name         VARCHAR(128)
  enabled      BOOLEAN
  session_type VARCHAR(32)   -- e.g. 'intraday', 'pre_market'
  run_time     TIME
  timezone     VARCHAR(64)
  weekdays_only BOOLEAN
  email        VARCHAR(255)
  model        VARCHAR(64)
  days         INTEGER
  top_n        INTEGER
  next_run_at  TIMESTAMP
  last_run_at  TIMESTAMP
  last_status  VARCHAR(32)
  last_error   TEXT
  created_at   TIMESTAMP
  updated_at   TIMESTAMP
"""

        # Step 1: Generate SQL via LLM
        sql = ""
        try:
            import litellm
            prompt = (
                f"{_schema}\n"
                f"Write a single READ-ONLY SQL SELECT query to answer:\n"
                f'"{question}"\n\n'
                "Rules:\n"
                "- Use only SELECT statements — no INSERT, UPDATE, DELETE, DROP, or DDL\n"
                "- Return ONLY the SQL query, no explanation, no markdown fences"
            )
            kwargs = {"model": _model, "messages": [{"role": "user", "content": prompt}]}
            if api_base:
                kwargs["api_base"] = api_base
            resp = litellm.completion(**kwargs)
            sql = resp.choices[0].message.content.strip().strip("`").strip()
            if sql.lower().startswith("sql"):
                sql = sql[3:].strip()
        except Exception as e:
            return {"question": question, "sql": "", "results": [], "answer": f"LLM error: {e}"}

        # Safety check — block any non-SELECT statements
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return {"question": question, "sql": sql, "results": [],
                    "answer": "Only SELECT queries are allowed."}

        # Step 2: Execute SQL
        raw_results = []
        columns = []
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        raw_results = [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            return {"question": question, "sql": sql, "results": [],
                    "answer": f"SQL execution error: {e}"}

        # Step 3: Summarise via LLM
        answer = ""
        try:
            import litellm
            result_text = str(raw_results[:50]) if raw_results else "No rows returned."
            summary_prompt = (
                f"Question: {question}\n"
                f"SQL used: {sql}\n"
                f"Results: {result_text}\n\n"
                "Write a concise, human-readable answer. If no results, say so clearly."
            )
            kwargs = {"model": _model, "messages": [{"role": "user", "content": summary_prompt}]}
            if api_base:
                kwargs["api_base"] = api_base
            resp = litellm.completion(**kwargs)
            answer = resp.choices[0].message.content.strip()
        except Exception:
            answer = str(raw_results[:10]) if raw_results else "No results."

        return {"question": question, "sql": sql, "results": raw_results, "answer": answer}
