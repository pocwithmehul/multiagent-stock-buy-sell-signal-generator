# n8n Workflows

## Stock Signal Watchlist Workflow

File: `n8n/stock-signal-watchlist-workflow.json`

### What it does

- Trigger manually or on weekday schedule (`09:35`).
- Expands a watchlist into per-ticker jobs.
- Calls `POST /signal` on the Stock AI Assistant API.
- Retries failed HTTP requests (3 tries, 5s delay).
- Applies policy gate: alert only when `signal == BUY` and `confidence >= min_confidence`.
- Produces structured payloads for:
  - alert delivery (includes ensemble signal + target price when ML is enabled)
  - audit logging (includes `ml_enabled`, `ensemble_signal`, `ensemble_confidence`, `target_price`)
  - failure audit

### Import steps

1. Open n8n UI.
2. Go to `Workflows` -> `Import from File`.
3. Select `n8n/stock-signal-watchlist-workflow.json`.
4. Update `Set Workflow Config` values:
   - `api_base`
   - `watchlist`
   - `model` (default: `claude-sonnet-4-6`)
   - `days`
   - `min_confidence`
   - `ml_analysis` (default: `true` — enables LSTM + XGBoost + Ensemble via feature flag)
5. Activate the workflow.

### Notes

- Default API endpoint is `http://localhost:8000/signal`.
- Keep API server running before executing workflow.
- `Build Alert Payload` and `Build Audit Payload` are integration handoff nodes; attach Slack/Email/DB/Webhook nodes after them based on your environment.
- When `ml_analysis: true`, the alert message automatically includes:
  - `ensemble=<signal>(<confidence>)` from the weighted ML ensemble
  - `target=$<price>` from the LSTM price predictor

### Feature Flags

The `ml_analysis` field is passed in the POST body and controls the full ML pipeline server-side:

| Field in body | Effect on server |
|---|---|
| `ml_analysis: true` | LSTM price predictor + XGBoost classifier + Ensemble scorer all run |
| `ml_analysis: false` | ML pipeline skipped; orchestrator signal used directly |

Per-agent feature flags (48 flags, one per sub-agent) are controlled entirely server-side via Unleash (local) or AWS AppConfig (cloud). No workflow changes are needed to control individual agents.

**XGBoost** is automatically enabled whenever `ml_analysis` is ON — no `ENABLE_XGBOOST` environment variable required.

### Response fields captured

| Field | Description |
|---|---|
| `ticker` | Stock ticker symbol |
| `signal` | `BUY` / `SELL` / `HOLD` |
| `confidence` | Orchestrator confidence score (0–1) |
| `reasoning` | LLM reasoning text |
| `mode` | `multi` or `single` |
| `agents_used` | Number of sub-agents that ran (respects per-agent flags) |
| `ml_enabled` | Whether ML pipeline ran for this request |
| `ensemble_signal` | Weighted ensemble vote (`BUY` / `SELL` / `HOLD`) |
| `ensemble_confidence` | Ensemble confidence score |
| `target_price` | LSTM 5-day price forecast |
| `timestamp` | ISO 8601 timestamp |

---

## Scheduled Buy-Now Ranking Workflow

File: `n8n/buy-now-scheduled-workflow.json`

### What it does

- Polls every 5 minutes.
- Reads due schedules from PostgreSQL via API: `GET /schedules/due`.
- Reads watchlist from PostgreSQL via API: `GET /watchlist`.
- Executes `scripts/scheduled_buy_now_report.py` for each due row.
- Marks result back in PostgreSQL via API:
  - `POST /schedules/{id}/run-result` with `success` or `failed`.
- Uses full pipeline inside runner:
  - up to 47 agents (`OrchestratorAgent`), gated by per-agent feature flags
  - ML ensemble reconciliation before ranking (when `ml_analysis` flag is ON)

### Required setup

1. Import `n8n/buy-now-scheduled-workflow.json`.
2. Update `Set Scheduler API Config` node:
   - `script_path`
   - `api_base`
   - `due_limit`
3. Create schedules from Streamlit/React dashboard (saved in PostgreSQL table).
4. Manage watchlist from Streamlit/React dashboard (saved in PostgreSQL watchlist table).
5. Ensure SMTP env vars are configured where the script runs:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `SMTP_FROM_EMAIL` (optional)
6. Ensure Python dependencies are installed and API keys for LLM/yfinance path are available.
7. Activate the workflow.

### Timezone note

- Scheduling timezone is stored per row in PostgreSQL (`timezone` column).
- Keep default as `America/New_York` unless you intentionally want a different zone.

---

## Python Launcher Script

File: `scripts/launch_n8n_workflow.py`

Use this script to launch and control the n8n workflow from terminal or other automation.

### Environment variables

- `N8N_BASE_URL` (example: `http://localhost:5678`)
- `N8N_API_KEY` (create in n8n API settings)

### Examples

1. Check workflow status:
   - `python scripts/launch_n8n_workflow.py --workflow-id <WORKFLOW_ID> --action status`
2. Activate workflow:
   - `python scripts/launch_n8n_workflow.py --workflow-id <WORKFLOW_ID> --action activate`
3. Trigger workflow immediately:
   - `python scripts/launch_n8n_workflow.py --workflow-id <WORKFLOW_ID> --action run`
4. Deactivate workflow:
   - `python scripts/launch_n8n_workflow.py --workflow-id <WORKFLOW_ID> --action deactivate`
