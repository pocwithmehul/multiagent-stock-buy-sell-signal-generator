/**
 * Dashboard Page Component
 *
 * The main landing page of the Stock Signal application. Provides the
 * primary interface for running stock analysis, managing watchlists,
 * and configuring scheduled analysis runs.
 *
 * Page Structure:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         Dashboard                                │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Hero Section                                │   │
 * │   │   "AI-Powered Stock Analysis"                            │   │
 * │   │   Description of 47 specialized agents                   │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Ticker Input                                │   │
 * │   │   [Enter ticker]  [Analyze]                              │   │
 * │   │   [✓] Multi-Agent Mode                                   │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Watchlist (PostgreSQL)                      │   │
 * │   │   [AAPL,MSFT,NVDA]  [Save Watchlist]                     │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Scheduler Config (PostgreSQL)               │   │
 * │   │   Schedule form + existing schedules list                │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Analysis Results (if available)             │   │
 * │   │   AnalysisCard component                                 │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Feature Cards (when no analysis)            │   │
 * │   │   [Multi-Agent] [Technical] [Sentiment]                  │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Features:
 *   - Ticker input with multi-agent toggle
 *   - Watchlist management (DB-backed)
 *   - Schedule configuration (DB-backed, read by n8n)
 *   - Analysis results display
 *   - PDF download, SMS, and email notifications
 *
 * State Management:
 *   - Local state for form inputs and analysis results
 *   - TanStack Query mutation for analysis API calls
 *   - API calls for watchlist and schedule CRUD
 *
 * Dependencies:
 *   - TickerInput: Stock symbol input form
 *   - AnalysisCard: Analysis results display
 *   - useAnalyzeMutation: TanStack Query mutation hook
 *   - stockApi: API client for backend calls
 *
 * References:
 *   - React useState: https://react.dev/reference/react/useState
 *   - React useEffect: https://react.dev/reference/react/useEffect
 */

import { useEffect, useMemo, useState } from 'react'
import { TickerInput } from '../components/TickerInput'
import { AnalysisCard } from '../components/AnalysisCard'
import { useAnalyzeMutation } from '../hooks/useStockAnalysis'
import { stockApi } from '../services/api'
import type { StockAnalysis, ScheduleConfig, ScheduleConfigRequest } from '../types'

const DEFAULT_FEATURE_FLAGS = {
  single_stock_analysis: true,
  watchlist_analysis: false,
  premarket_analysis: false,
  aftermarket_analysis: false,
}

function getAllowedSessionTypes(flags: typeof DEFAULT_FEATURE_FLAGS): Array<ScheduleConfig['session_type']> {
  const sessions: Array<ScheduleConfig['session_type']> = ['intraday']
  if (flags.premarket_analysis) sessions.unshift('pre_market')
  if (flags.aftermarket_analysis) sessions.push('after_hours')
  return sessions
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Main dashboard page component.
 *
 * Manages multiple pieces of state:
 *   - analysis: Current analysis result (null until analysis runs)
 *   - watchlist: Array of tickers from database
 *   - watchlistInput: Text input value for watchlist editing
 *   - schedules: Array of schedule configs from database
 *   - scheduleMsg: Feedback message for schedule/watchlist operations
 *   - scheduleForm: Form state for new schedule creation
 *
 * Effects:
 *   - On mount: Loads schedules and watchlist from backend
 *
 * @returns {JSX.Element} Complete dashboard page
 */
export function Dashboard() {
  // ───────────────────────────────────────────────────────────────────────────
  // State Management
  // ───────────────────────────────────────────────────────────────────────────

  // Current analysis result - populated after successful analysis
  const [analysis, setAnalysis] = useState<StockAnalysis | null>(null)
  const [featureFlags, setFeatureFlags] = useState(DEFAULT_FEATURE_FLAGS)

  // Watchlist state - tickers stored in PostgreSQL
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [watchlistInput, setWatchlistInput] = useState<string>('')

  // Schedule configuration state - stored in PostgreSQL, read by n8n
  const [schedules, setSchedules] = useState<ScheduleConfig[]>([])
  const [scheduleMsg, setScheduleMsg] = useState<string>('')

  // Form state for creating new schedules
  // Defaults to a weekday pre-market schedule
  const [scheduleForm, setScheduleForm] = useState<ScheduleConfigRequest>({
    name: 'weekday_buy_now',
    enabled: true,
    session_type: 'pre_market',
    run_time: '06:00:00',
    timezone: 'America/New_York',
    weekdays_only: true,
    email: '',
    model: 'gpt-4o-mini',
    days: 90,
    top_n: 10,
  })

  // TanStack Query mutation for running analysis
  const analyzeMutation = useAnalyzeMutation()

  // ───────────────────────────────────────────────────────────────────────────
  // Data Loading
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Load schedule configurations from the backend.
   * Called on mount and after schedule modifications.
   */
  const loadSchedules = async () => {
    try {
      const rows = await stockApi.listSchedules()
      setSchedules(rows)
    } catch (error) {
      console.error('Failed to load schedules:', error)
    }
  }

  /**
   * Effect: Load initial data on component mount.
   *
   * Fetches:
   *   1. Schedule configurations
   *   2. Watchlist tickers
   *
   * Both are loaded from PostgreSQL via the backend API.
   */
  useEffect(() => {
    void stockApi.getFeatureFlags().then((payload) => {
      const normalized = {
        single_stock_analysis: Boolean(payload.flags.single_stock_analysis),
        watchlist_analysis: Boolean(payload.flags.watchlist_analysis),
        premarket_analysis: Boolean(payload.flags.premarket_analysis),
        aftermarket_analysis: Boolean(payload.flags.aftermarket_analysis),
      }
      setFeatureFlags(normalized)
    }).catch((err) => {
      console.error('Failed to load feature flags:', err)
    })

    // Load schedules
    void loadSchedules()

    // Load watchlist and populate input field
    void stockApi.getWatchlist().then((rows) => {
      setWatchlist(rows)
      setWatchlistInput(rows.join(','))
    }).catch((err) => console.error('Failed to load watchlist:', err))
  }, [])

  const allowedSessionTypes = useMemo(
    () => getAllowedSessionTypes(featureFlags),
    [featureFlags]
  )

  useEffect(() => {
    if (!allowedSessionTypes.includes(scheduleForm.session_type)) {
      setScheduleForm((prev) => ({ ...prev, session_type: allowedSessionTypes[0] }))
    }
  }, [allowedSessionTypes, scheduleForm.session_type])

  // ───────────────────────────────────────────────────────────────────────────
  // Event Handlers
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Handle analysis form submission.
   *
   * Triggers the stock analysis via TanStack Query mutation.
   * Results are stored in local state for display.
   *
   * @param {string} ticker - Stock symbol to analyze
   * @param {boolean} multiAgent - Whether to use multi-agent mode
   */
  const handleAnalyze = async (ticker: string, multiAgent: boolean) => {
    if (!featureFlags.single_stock_analysis) {
      setScheduleMsg('Single stock analysis is disabled by feature flag.')
      return
    }
    try {
      const result = await analyzeMutation.mutateAsync({
        ticker,
        multi_agent: multiAgent,
        verbose: true, // Include per-agent details in response
      })
      setAnalysis(result)
    } catch (error) {
      console.error('Analysis failed:', error)
    }
  }

  /**
   * Handle PDF download action.
   * TODO: Implement actual PDF download via stockApi.downloadPdf
   */
  const handleDownloadPdf = async () => {
    if (!analysis) return
    // Implementation for PDF download
    alert('PDF download - integrate with API')
  }

  /**
   * Handle SMS notification action.
   * Prompts for phone number and sends analysis via SMS.
   */
  const handleSendSms = async () => {
    if (!analysis) return
    const phone = prompt('Enter phone number:')
    if (phone) {
      alert(`SMS would be sent to ${phone}`)
    }
  }

  /**
   * Handle email notification action.
   * Prompts for email address and sends analysis report.
   */
  const handleSendEmail = async () => {
    if (!analysis) return
    const email = prompt('Enter email address:')
    if (email) {
      alert(`Email would be sent to ${email}`)
    }
  }

  /**
   * Save a new or updated schedule configuration.
   * Validates email and persists to PostgreSQL.
   */
  const handleSaveSchedule = async () => {
    try {
      if (!allowedSessionTypes.includes(scheduleForm.session_type)) {
        setScheduleMsg('Selected session type is disabled by feature flag.')
        return
      }
      // Validate email is provided and contains @
      if (!scheduleForm.email || !scheduleForm.email.includes('@')) {
        setScheduleMsg('Please provide a valid report email.')
        return
      }
      await stockApi.saveSchedule(scheduleForm)
      setScheduleMsg('Schedule saved to PostgreSQL.')
      await loadSchedules() // Refresh the schedule list
    } catch (error) {
      console.error('Schedule save failed:', error)
      setScheduleMsg('Failed to save schedule.')
    }
  }

  /**
   * Delete a schedule by ID.
   *
   * @param {number} id - Database ID of schedule to delete
   */
  const handleDeleteSchedule = async (id: number) => {
    try {
      await stockApi.deleteSchedule(id)
      await loadSchedules() // Refresh the schedule list
      setScheduleMsg('Schedule deleted.')
    } catch (error) {
      console.error('Schedule delete failed:', error)
      setScheduleMsg('Failed to delete schedule.')
    }
  }

  /**
   * Save the watchlist from the input field.
   * Parses comma-separated tickers and persists to PostgreSQL.
   */
  const handleSaveWatchlist = async () => {
    try {
      // Parse input: split by comma, trim whitespace, uppercase, remove empty
      const tickers = watchlistInput.split(',').map((x) => x.trim().toUpperCase()).filter(Boolean)
      const rows = await stockApi.replaceWatchlist(tickers)
      setWatchlist(rows)
      setWatchlistInput(rows.join(','))
      setScheduleMsg('Watchlist saved to PostgreSQL.')
    } catch (error) {
      console.error('Watchlist save failed:', error)
      setScheduleMsg('Failed to save watchlist.')
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Render
  // ───────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8">
      {/* ─────────────────────────────────────────────────────────────────────
          Hero Section
          Prominent title and description of the application
          ───────────────────────────────────────────────────────────────────── */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold text-white">
          AI-Powered Stock Analysis
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto">
          Get BUY, SELL, or HOLD signals powered by 47 specialized AI agents
          analyzing technical indicators, news sentiment, SEC filings, and more.
        </p>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Ticker Input Section
          Form for entering stock symbol and triggering analysis
          ───────────────────────────────────────────────────────────────────── */}
      <div className="max-w-2xl mx-auto">
        {featureFlags.single_stock_analysis ? (
          <TickerInput
            onSubmit={handleAnalyze}
            isLoading={analyzeMutation.isPending}
          />
        ) : (
          <div className="p-4 bg-yellow-900/40 border border-yellow-700 rounded-lg text-yellow-100">
            `single_stock_analysis` is disabled by feature flag.
          </div>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Watchlist Section
          Database-backed watchlist for batch analysis
          ───────────────────────────────────────────────────────────────────── */}
      {featureFlags.watchlist_analysis ? (
        <div className="max-w-4xl mx-auto bg-gray-800 rounded-xl p-6 space-y-4">
          <h2 className="text-2xl font-semibold text-white">Watchlist (PostgreSQL)</h2>
          <p className="text-gray-400 text-sm">
            Research runs use this DB watchlist. It is managed independently from session schedule settings.
          </p>
          {/* Watchlist input - comma-separated tickers */}
          <input
            className="bg-gray-900 text-white rounded px-3 py-2 w-full"
            placeholder="AAPL,MSFT,NVDA"
            value={watchlistInput}
            onChange={(e) => setWatchlistInput(e.target.value)}
          />
          <button
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
            onClick={handleSaveWatchlist}
          >
            Save Watchlist
          </button>
          {/* Current watchlist display */}
          <p className="text-xs text-gray-400">Current: {watchlist.join(', ') || 'None'}</p>
        </div>
      ) : (
        <div className="max-w-4xl mx-auto bg-gray-800 rounded-xl p-6">
          <h2 className="text-2xl font-semibold text-white">Watchlist</h2>
          <p className="text-sm text-yellow-100 mt-2">`watchlist_analysis` is disabled by feature flag.</p>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────
          Scheduler Configuration Section
          Database-backed schedule configs read by n8n workflow
          ───────────────────────────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto bg-gray-800 rounded-xl p-6 space-y-4">
        <h2 className="text-2xl font-semibold text-white">Scheduler Config (PostgreSQL)</h2>
        <p className="text-gray-400 text-sm">
          Save schedule timing here. n8n reads due rows from PostgreSQL and runs reports automatically.
        </p>

        {/* Schedule Form - Grid layout for form fields */}
        <div className="grid md:grid-cols-2 gap-4">
          {/* Schedule name input */}
          <input
            className="bg-gray-900 text-white rounded px-3 py-2"
            placeholder="Schedule name"
            value={scheduleForm.name}
            onChange={(e) => setScheduleForm({ ...scheduleForm, name: e.target.value })}
          />
          {/* Report email input */}
          <input
            className="bg-gray-900 text-white rounded px-3 py-2"
            placeholder="Report email"
            value={scheduleForm.email}
            onChange={(e) => setScheduleForm({ ...scheduleForm, email: e.target.value })}
          />
          {/* Session type dropdown */}
          <select
            className="bg-gray-900 text-white rounded px-3 py-2"
            value={scheduleForm.session_type}
            onChange={(e) => setScheduleForm({ ...scheduleForm, session_type: e.target.value as ScheduleConfig['session_type'] })}
          >
            {featureFlags.premarket_analysis && <option value="pre_market">pre_market</option>}
            <option value="intraday">intraday</option>
            {featureFlags.aftermarket_analysis && <option value="after_hours">after_hours</option>}
          </select>
          {/* Run time input */}
          <input
            className="bg-gray-900 text-white rounded px-3 py-2"
            placeholder="Run time (HH:MM:SS)"
            value={scheduleForm.run_time}
            onChange={(e) => setScheduleForm({ ...scheduleForm, run_time: e.target.value })}
          />
          {/* Timezone input */}
          <input
            className="bg-gray-900 text-white rounded px-3 py-2"
            placeholder="Timezone"
            value={scheduleForm.timezone}
            onChange={(e) => setScheduleForm({ ...scheduleForm, timezone: e.target.value })}
          />
        </div>

        {/* Save schedule button */}
        <button
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
          onClick={handleSaveSchedule}
        >
          Save Schedule
        </button>

        {/* Feedback message for operations */}
        {scheduleMsg && <p className="text-sm text-gray-300">{scheduleMsg}</p>}

        {/* List of existing schedules */}
        <div className="space-y-2">
          {schedules.map((s) => (
            <div key={s.id} className="bg-gray-900 rounded p-3 flex items-center justify-between">
              {/* Schedule details */}
              <div className="text-sm text-gray-200">
                {s.name} [{s.session_type}] at {s.run_time} ({s.timezone}) | next: {s.next_run_at}
              </div>
              {/* Delete button */}
              <button
                className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
                onClick={() => void handleDeleteSchedule(s.id)}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Error Message
          Shown when analysis fails
          ───────────────────────────────────────────────────────────────────── */}
      {analyzeMutation.isError && (
        <div className="max-w-2xl mx-auto p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
          Analysis failed. Please try again.
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────
          Analysis Results
          Shown after successful analysis
          ───────────────────────────────────────────────────────────────────── */}
      {analysis && (
        <div className="max-w-4xl mx-auto">
          <AnalysisCard
            analysis={analysis}
            onDownloadPdf={handleDownloadPdf}
            onSendSms={handleSendSms}
            onSendEmail={handleSendEmail}
          />
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────
          Feature Cards
          Shown when no analysis has been run yet
          ───────────────────────────────────────────────────────────────────── */}
      {!analysis && (
        <div className="grid md:grid-cols-3 gap-6 mt-12">
          <FeatureCard
            icon="🤖"
            title="Multi-Agent Analysis"
            description="47 specialized AI agents analyze different aspects of each stock"
          />
          <FeatureCard
            icon="📊"
            title="Technical Indicators"
            description="RSI, MACD, Bollinger Bands, SMA, EMA, and more"
          />
          <FeatureCard
            icon="📰"
            title="Sentiment Analysis"
            description="News, social media, and SEC filings sentiment scoring"
          />
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// FeatureCard Sub-Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Feature highlight card for the dashboard landing section.
 *
 * Displays an icon, title, and description in a centered card layout.
 * Used to showcase key features before the user runs their first analysis.
 *
 * @param {Object} props - Component props
 * @param {string} props.icon - Emoji or icon character
 * @param {string} props.title - Feature title
 * @param {string} props.description - Feature description
 * @returns {JSX.Element} Styled feature card
 */
function FeatureCard({ icon, title, description }: {
  icon: string
  title: string
  description: string
}) {
  return (
    <div className="bg-gray-800 rounded-xl p-6 text-center">
      {/* Large emoji icon */}
      <span className="text-4xl">{icon}</span>
      {/* Feature title */}
      <h3 className="text-lg font-semibold text-white mt-4">{title}</h3>
      {/* Feature description */}
      <p className="text-gray-400 mt-2">{description}</p>
    </div>
  )
}
