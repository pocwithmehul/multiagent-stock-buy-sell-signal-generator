/**
 * TypeScript Type Definitions for Stock Signal API
 *
 * This module contains all TypeScript interfaces and types used throughout
 * the React frontend. These types mirror the backend API response schemas
 * defined in the FastAPI application (api.py).
 *
 * Type Hierarchy:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         API Types                                │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   Core Analysis Types                                           │
 * │   ─────────────────────                                         │
 * │   • Signal - BUY | SELL | HOLD                                  │
 * │   • StockAnalysis - Full analysis result                        │
 * │   • AgentOutput - Individual agent result                       │
 * │   • TechnicalIndicators - RSI, MACD, SMA, etc.                  │
 * │                                                                  │
 * │   Request/Response Types                                        │
 * │   ───────────────────────                                       │
 * │   • AnalysisRequest - POST /analyze body                        │
 * │   • HealthResponse - GET /health response                       │
 * │   • Source - Data source reference                              │
 * │                                                                  │
 * │   Scheduler Types                                               │
 * │   ────────────────                                              │
 * │   • ScheduleConfig - Stored schedule configuration              │
 * │   • ScheduleConfigRequest - Create/update schedule              │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Usage:
 *   import type { StockAnalysis, Signal } from '../types'
 *
 *   const analysis: StockAnalysis = await api.analyze(request)
 *   if (analysis.signal === 'BUY') { ... }
 *
 * References:
 *   - Backend schemas: api.py (Pydantic models)
 *   - TypeScript utility types: https://www.typescriptlang.org/docs/handbook/utility-types.html
 */

// ─────────────────────────────────────────────────────────────────────────────
// Core Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Stock signal recommendation.
 *
 * The three possible output signals from analysis:
 *   - BUY: Recommendation to purchase the stock
 *   - SELL: Recommendation to sell existing positions
 *   - HOLD: Recommendation to maintain current position
 *
 * This type is used for both individual agent signals and
 * the final synthesized signal from the orchestrator.
 */
export type Signal = 'BUY' | 'SELL' | 'HOLD'

/**
 * Complete stock analysis result from the backend API.
 *
 * This is the primary data structure returned by POST /analyze.
 * It contains the synthesized signal, confidence metrics, price targets,
 * and detailed reasoning from the AI analysis.
 *
 * Fields:
 *   - ticker: Stock symbol (e.g., "AAPL")
 *   - signal: Final recommendation (BUY/SELL/HOLD)
 *   - confidence: Model confidence 0.0-1.0 (higher = more confident)
 *   - target_price: Predicted price target
 *   - potential_upside_pct: Upside potential percentage
 *   - potential_downside_pct: Downside risk percentage
 *   - stop_loss: Recommended stop-loss price
 *   - sentiment_score: Aggregate sentiment -1.0 to 1.0
 *   - reasoning: Human-readable analysis explanation
 *   - sources: Data sources used in analysis
 *   - timestamp: ISO 8601 timestamp of analysis
 *   - mode: Analysis mode used (single-agent or multi-agent)
 *   - agents_used: Number of agents (multi-agent mode only)
 *   - agent_details: Per-agent results (with verbose=true)
 */
export interface StockAnalysis {
  ticker: string
  signal: Signal
  confidence: number
  target_price: number
  potential_upside_pct: number
  potential_downside_pct: number
  stop_loss: number
  sentiment_score: number
  reasoning: string
  sources: Source[]
  timestamp: string
  mode: 'single-agent' | 'multi-agent'
  agents_used?: number
  agent_details?: AgentOutput[]
}

/**
 * Data source reference included in analysis results.
 *
 * Sources provide transparency about where data was obtained
 * for the analysis. Each source has a name and optional URL.
 *
 * Examples:
 *   - { name: "Yahoo Finance", url: "https://finance.yahoo.com/..." }
 *   - { name: "SEC EDGAR", url: "https://www.sec.gov/..." }
 *   - { name: "Technical Analysis" } // No URL for computed data
 */
export interface Source {
  name: string
  url?: string
}

/**
 * Individual agent output in multi-agent mode.
 *
 * When running with verbose=true in multi-agent mode, each of the
 * 47 specialized agents returns its individual analysis. This
 * interface captures that per-agent output.
 *
 * Fields:
 *   - agent: Agent identifier (e.g., "TechnicalAnalysisAgent")
 *   - signal: Agent's individual signal recommendation
 *   - confidence: Agent's confidence in its signal
 *   - summary: Brief text summary of findings
 *   - data: Raw data collected by the agent (varies by agent type)
 */
export interface AgentOutput {
  agent: string
  signal?: Signal
  confidence?: number
  summary: string
  data?: Record<string, unknown>
}

/**
 * Technical indicator values from TechnicalAnalysisAgent.
 *
 * These indicators are computed from historical OHLCV data
 * and used for technical analysis signal generation.
 *
 * Indicators included:
 *   - RSI (Relative Strength Index): Momentum oscillator 0-100
 *   - MACD (Moving Average Convergence Divergence): Trend indicator
 *   - SMA (Simple Moving Average): 20 and 50 period
 *   - EMA (Exponential Moving Average): 12 and 26 period
 *   - Bollinger Bands: Volatility bands around SMA
 *
 * Usage:
 *   - RSI > 70: Overbought (potential sell signal)
 *   - RSI < 30: Oversold (potential buy signal)
 *   - MACD > Signal: Bullish crossover
 *   - Price above upper Bollinger: Overbought
 */
export interface TechnicalIndicators {
  rsi: number
  macd: number
  macd_signal: number
  sma_20: number
  sma_50: number
  ema_12: number
  ema_26: number
  bollinger_upper: number
  bollinger_lower: number
  current_price: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Request Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Request body for POST /analyze endpoint.
 *
 * This interface defines the parameters for initiating a stock analysis.
 *
 * Required:
 *   - ticker: Stock symbol to analyze (e.g., "AAPL", "MSFT")
 *
 * Optional:
 *   - days: Historical data lookback period (default: 90)
 *   - multi_agent: Use 47-agent analysis (default: false)
 *   - verbose: Include per-agent details (default: false)
 *
 * Example:
 *   {
 *     ticker: "AAPL",
 *     days: 60,
 *     multi_agent: true,
 *     verbose: true
 *   }
 */
export interface AnalysisRequest {
  ticker: string
  days?: number
  multi_agent?: boolean
  verbose?: boolean
}

/**
 * Response from GET /health endpoint.
 *
 * Used to check API availability and display environment info
 * in the dashboard header (environment badge).
 *
 * Fields:
 *   - status: "healthy" if API is operational
 *   - version: API version string
 *   - environment: Deployment environment (local, qa, stg, prod)
 */
export interface HealthResponse {
  status: string
  version: string
  environment: string
}

/**
 * Response from GET /api/v1/features endpoint.
 *
 * Provides feature flag values used for UI/runtime gating.
 */
export interface FeatureFlagsResponse {
  flags: {
    single_stock_analysis: boolean
    watchlist_analysis: boolean
    premarket_analysis: boolean
    aftermarket_analysis: boolean
    [key: string]: boolean
  }
  provider: string
  environment: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Scheduler Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Request body for creating/updating a schedule configuration.
 *
 * Schedules define when automated analysis should run. The schedule
 * is stored in PostgreSQL and executed by n8n workflow automation.
 *
 * Fields:
 *   - name: Unique schedule identifier (e.g., "weekday_buy_now")
 *   - enabled: Whether schedule is active
 *   - session_type: Trading session (pre_market, intraday, after_hours)
 *   - run_time: Execution time in HH:MM:SS format
 *   - timezone: IANA timezone (default: America/New_York)
 *   - weekdays_only: Skip weekends if true
 *   - email: Email address for report delivery
 *   - model: LLM model to use (default: gpt-4o-mini)
 *   - days: Historical lookback period
 *   - top_n: Number of top stocks to include in report
 *
 * Trading Sessions:
 *   - pre_market: 4:00 AM - 9:30 AM ET
 *   - intraday: 9:30 AM - 4:00 PM ET
 *   - after_hours: 4:00 PM - 8:00 PM ET
 */
export interface ScheduleConfigRequest {
  name: string
  enabled?: boolean
  session_type: 'pre_market' | 'intraday' | 'after_hours'
  run_time: string
  timezone?: string
  weekdays_only?: boolean
  email: string
  model?: string
  days?: number
  top_n?: number
}

/**
 * Stored schedule configuration from database.
 *
 * This extends ScheduleConfigRequest with database-managed fields
 * like id, timestamps, and execution status.
 *
 * Additional fields:
 *   - id: Database primary key
 *   - next_run_at: Computed next execution time (ISO 8601)
 *   - last_run_at: Most recent execution time
 *   - last_status: Result of last run (success/failure)
 *   - last_error: Error message if last run failed
 */
export interface ScheduleConfig {
  id: number
  name: string
  enabled: boolean
  session_type: 'pre_market' | 'intraday' | 'after_hours'
  run_time: string
  timezone: string
  weekdays_only: boolean
  email: string
  model: string
  days: number
  top_n: number
  next_run_at: string
  last_run_at?: string
  last_status?: string
  last_error?: string
}
