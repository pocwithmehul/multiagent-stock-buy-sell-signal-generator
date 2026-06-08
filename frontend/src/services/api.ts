/**
 * Stock Signal API Client
 *
 * This module provides a typed API client for communicating with the
 * FastAPI backend. It uses Axios for HTTP requests and exports
 * a structured API object with methods for each endpoint.
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         API Client                               │
 * │                    (services/api.ts)                             │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   React Components                                              │
 * │         │                                                        │
 * │         ▼                                                        │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              stockApi                                    │   │
 * │   │   (Typed methods for each endpoint)                      │   │
 * │   │                                                          │   │
 * │   │   • health()      → GET  /health                         │   │
 * │   │   • analyze()     → POST /analyze                        │   │
 * │   │   • getAnalysis() → GET  /analysis/:ticker               │   │
 * │   │   • downloadPdf() → GET  /report/:ticker/pdf             │   │
 * │   │   • sendSms()     → POST /notify/sms                     │   │
 * │   │   • sendEmail()   → POST /notify/email                   │   │
 * │   │   • Watchlist CRUD                                       │   │
 * │   │   • Schedule CRUD                                        │   │
 * │   │                                                          │   │
 * │   └──────────────────────────┬──────────────────────────────┘   │
 * │                              │                                   │
 * │                              ▼                                   │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Axios Instance                              │   │
 * │   │   • Base URL: VITE_API_BASE_URL or /api                  │   │
 * │   │   • Content-Type: application/json                       │   │
 * │   └──────────────────────────┬──────────────────────────────┘   │
 * │                              │                                   │
 * │                              ▼                                   │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              FastAPI Backend                             │   │
 * │   │   (api.py - Stock Signal REST API)                       │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Configuration:
 *   Set VITE_API_BASE_URL in .env to override the default /api base.
 *   Example: VITE_API_BASE_URL=http://localhost:8000/api
 *
 * Dependencies:
 *   - axios: HTTP client library
 *
 * References:
 *   - Axios: https://axios-http.com/
 *   - Vite env variables: https://vitejs.dev/guide/env-and-mode.html
 */

import axios from 'axios'
import type {
  StockAnalysis,
  AnalysisRequest,
  HealthResponse,
  FeatureFlagsResponse,
  ScheduleConfig,
  ScheduleConfigRequest,
} from '../types'

// ─────────────────────────────────────────────────────────────────────────────
// Axios Instance Configuration
// ─────────────────────────────────────────────────────────────────────────────

/**
 * API base URL from environment or default to /api.
 *
 * In development: Uses Vite proxy to forward /api to backend
 * In production: API is served at /api path (same origin)
 *
 * Override with: VITE_API_BASE_URL=http://localhost:8000/api
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

/**
 * Configured Axios instance for all API requests.
 *
 * Features:
 *   - Consistent base URL for all endpoints
 *   - JSON content type header
 *   - Can be extended with interceptors for auth, logging, etc.
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ─────────────────────────────────────────────────────────────────────────────
// Stock API Methods
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Stock Signal API client with typed methods for each endpoint.
 *
 * All methods return Promises and handle the Axios response unwrapping.
 * Type safety is provided by TypeScript interfaces from ../types.
 *
 * Usage with TanStack Query:
 *   const { data } = useQuery({
 *     queryKey: ['analysis', ticker],
 *     queryFn: () => stockApi.analyze({ ticker })
 *   })
 */
export const stockApi = {
  // ───────────────────────────────────────────────────────────────────────────
  // Health & Status
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Check API health status.
   *
   * Used by the Layout component to display the environment badge
   * and verify the backend is accessible.
   *
   * @returns {Promise<HealthResponse>} Health status with environment info
   *
   * @example
   *   const health = await stockApi.health()
   *   console.log(health.environment) // "local"
   */
  health: async (): Promise<HealthResponse> => {
    const { data } = await api.get('/health')
    return data
  },

  /**
   * Get current feature flags and provider information.
   *
   * @returns {Promise<FeatureFlagsResponse>} Feature flags payload
   */
  getFeatureFlags: async (): Promise<FeatureFlagsResponse> => {
    const { data } = await api.get('/v1/features')
    return data
  },

  // ───────────────────────────────────────────────────────────────────────────
  // Stock Analysis
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Run stock analysis for a given ticker.
   *
   * This is the primary analysis endpoint. It triggers either single-agent
   * or multi-agent (47 agents) analysis based on the request parameters.
   *
   * @param {AnalysisRequest} request - Analysis parameters
   * @returns {Promise<StockAnalysis>} Complete analysis result
   *
   * @example
   *   const result = await stockApi.analyze({
   *     ticker: 'AAPL',
   *     multi_agent: true,
   *     verbose: true,
   *     days: 90
   *   })
   *   console.log(result.signal) // "BUY"
   */
  analyze: async (request: AnalysisRequest): Promise<StockAnalysis> => {
    const { data } = await api.post('/analyze', request)
    return data
  },

  /**
   * Get cached analysis for a ticker (if available).
   *
   * Retrieves previously computed analysis without triggering a new run.
   * Returns null if no cached analysis exists.
   *
   * @param {string} ticker - Stock symbol
   * @returns {Promise<StockAnalysis | null>} Cached analysis or null
   *
   * @example
   *   const cached = await stockApi.getAnalysis('AAPL')
   *   if (cached) {
   *     console.log('Using cached:', cached.timestamp)
   *   }
   */
  getAnalysis: async (ticker: string): Promise<StockAnalysis | null> => {
    try {
      const { data } = await api.get(`/analysis/${ticker}`)
      return data
    } catch {
      // Return null if analysis not found (404)
      return null
    }
  },

  // ───────────────────────────────────────────────────────────────────────────
  // Reports & Notifications
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Download PDF report for a ticker.
   *
   * Generates and downloads a formatted PDF report containing
   * the analysis results, charts, and recommendations.
   *
   * @param {string} ticker - Stock symbol
   * @returns {Promise<Blob>} PDF file as Blob for download
   *
   * @example
   *   const blob = await stockApi.downloadPdf('AAPL')
   *   const url = URL.createObjectURL(blob)
   *   // Create download link with url
   */
  downloadPdf: async (ticker: string): Promise<Blob> => {
    const { data } = await api.get(`/report/${ticker}/pdf`, {
      responseType: 'blob', // Required for binary file download
    })
    return data
  },

  /**
   * Send SMS notification with analysis summary.
   *
   * Sends a text message to the specified phone number with
   * key analysis results (signal, confidence, target price).
   * Requires Twilio configuration on the backend.
   *
   * @param {string} ticker - Stock symbol
   * @param {string} phone - Phone number (E.164 format recommended)
   *
   * @example
   *   await stockApi.sendSms('AAPL', '+15551234567')
   */
  sendSms: async (ticker: string, phone: string): Promise<void> => {
    await api.post(`/notify/sms`, { ticker, phone })
  },

  /**
   * Send email notification with analysis report.
   *
   * Sends an email to the specified address with the full
   * analysis report, optionally including PDF attachment.
   * Requires SMTP configuration on the backend.
   *
   * @param {string} ticker - Stock symbol
   * @param {string} email - Recipient email address
   *
   * @example
   *   await stockApi.sendEmail('AAPL', 'user@example.com')
   */
  sendEmail: async (ticker: string, email: string): Promise<void> => {
    await api.post(`/notify/email`, { ticker, email })
  },

  // ───────────────────────────────────────────────────────────────────────────
  // Schedule Management (PostgreSQL-backed)
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * List all schedule configurations.
   *
   * Retrieves all saved schedules from the database.
   * Used to display existing schedules in the dashboard.
   *
   * @returns {Promise<ScheduleConfig[]>} Array of schedule configurations
   */
  listSchedules: async (): Promise<ScheduleConfig[]> => {
    const { data } = await api.get('/schedules')
    return data.schedules ?? []
  },

  /**
   * Create or update a schedule configuration.
   *
   * Saves the schedule to PostgreSQL. The n8n workflow
   * reads these schedules to determine when to run analyses.
   *
   * @param {ScheduleConfigRequest} request - Schedule parameters
   * @returns {Promise<ScheduleConfig>} Saved schedule with computed fields
   */
  saveSchedule: async (request: ScheduleConfigRequest): Promise<ScheduleConfig> => {
    const { data } = await api.post('/schedules', request)
    return data.schedule
  },

  /**
   * Delete a schedule by ID.
   *
   * Permanently removes the schedule from the database.
   *
   * @param {number} id - Schedule database ID
   */
  deleteSchedule: async (id: number): Promise<void> => {
    await api.delete(`/schedules/${id}`)
  },

  // ───────────────────────────────────────────────────────────────────────────
  // Watchlist Management (PostgreSQL-backed)
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Get the current watchlist.
   *
   * Retrieves all tickers in the user's watchlist from the database.
   *
   * @returns {Promise<string[]>} Array of ticker symbols
   *
   * @example
   *   const tickers = await stockApi.getWatchlist()
   *   // ["AAPL", "MSFT", "NVDA"]
   */
  getWatchlist: async (): Promise<string[]> => {
    const { data } = await api.get('/watchlist')
    return data.tickers ?? []
  },

  /**
   * Replace the entire watchlist.
   *
   * Overwrites the existing watchlist with the provided tickers.
   * Used when saving the watchlist from the input field.
   *
   * @param {string[]} tickers - New watchlist tickers
   * @returns {Promise<string[]>} Updated watchlist
   */
  replaceWatchlist: async (tickers: string[]): Promise<string[]> => {
    const { data } = await api.put('/watchlist', { tickers })
    return data.tickers ?? []
  },

  /**
   * Add a single ticker to the watchlist.
   *
   * Appends the ticker if not already present.
   *
   * @param {string} ticker - Ticker to add
   * @returns {Promise<string[]>} Updated watchlist
   */
  addWatchlistTicker: async (ticker: string): Promise<string[]> => {
    const { data } = await api.post(`/watchlist/${ticker}`)
    return data.tickers ?? []
  },

  /**
   * Remove a ticker from the watchlist.
   *
   * @param {string} ticker - Ticker to remove
   * @returns {Promise<string[]>} Updated watchlist
   */
  removeWatchlistTicker: async (ticker: string): Promise<string[]> => {
    const { data } = await api.delete(`/watchlist/${ticker}`)
    return data.tickers ?? []
  },
}

/**
 * Export the raw Axios instance for advanced use cases.
 *
 * Use this if you need to:
 *   - Add request/response interceptors
 *   - Make requests not covered by stockApi
 *   - Access response headers or status codes
 */
export default api
