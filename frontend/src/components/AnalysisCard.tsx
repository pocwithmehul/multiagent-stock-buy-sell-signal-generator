/**
 * Analysis Card Component
 *
 * A comprehensive card component that displays stock analysis results.
 * Shows the signal, confidence metrics, sentiment, reasoning, and
 * action buttons for exporting/sharing the analysis.
 *
 * Card Layout:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      Analysis Card                               │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ AAPL                              ┌───────────┐          │   │
 * │   │ Feb 23, 2026 3:45 PM              │    BUY    │          │   │
 * │   │                                   └───────────┘          │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
 * │   │Confidence│ │Target    │ │ Upside   │ │Stop Loss │         │
 * │   │  85%     │ │ $198.50  │ │ +12.5%   │ │ $165.00  │         │
 * │   └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ Sentiment Score                                          │   │
 * │   │ [████████████████░░░░░░░░] 0.65 (-1 to 1)                │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ Analysis                                                 │   │
 * │   │ Based on technical indicators showing bullish momentum...│   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   Mode: multi-agent                    47 agents used           │
 * │                                                                  │
 * │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
 * │   │ Download PDF │ │  Send SMS    │ │  Send Email  │           │
 * │   └──────────────┘ └──────────────┘ └──────────────┘           │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Sections:
 *   1. Header: Ticker symbol, timestamp, and signal badge
 *   2. Key Metrics: Confidence, target price, upside, stop loss
 *   3. Sentiment: Visual progress bar with score
 *   4. Reasoning: Full text analysis explanation
 *   5. Mode Info: Analysis mode and agent count
 *   6. Actions: Export and notification buttons
 *
 * Dependencies:
 *   - SignalBadge: For rendering the colored signal indicator
 *
 * References:
 *   - Tailwind CSS Cards: https://tailwindcss.com/docs/plugins#cards
 */

import { SignalBadge } from './SignalBadge'
import type { StockAnalysis } from '../types'

// ─────────────────────────────────────────────────────────────────────────────
// Component Props Interface
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Props for the AnalysisCard component.
 *
 * @property {StockAnalysis} analysis - Complete analysis data to display
 * @property {() => void} [onDownloadPdf] - Handler for PDF download action
 * @property {() => void} [onSendSms] - Handler for SMS notification action
 * @property {() => void} [onSendEmail] - Handler for email notification action
 *
 * Note: Action handlers are optional. If not provided, the corresponding
 * button will not be rendered.
 */
interface AnalysisCardProps {
  analysis: StockAnalysis
  onDownloadPdf?: () => void
  onSendSms?: () => void
  onSendEmail?: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// AnalysisCard Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Displays a complete stock analysis result in a styled card.
 *
 * The card is divided into logical sections:
 *   - Header with ticker and signal
 *   - Grid of key metrics (responsive 2-4 columns)
 *   - Sentiment score with visual indicator
 *   - Full reasoning text
 *   - Mode information
 *   - Action buttons for export/sharing
 *
 * Confidence coloring:
 *   - >= 70%: Green (high confidence)
 *   - >= 50%: Yellow (moderate confidence)
 *   - < 50%: Red (low confidence)
 *
 * @param {AnalysisCardProps} props - Component props
 * @returns {JSX.Element} Styled card with analysis details
 *
 * @example
 *   <AnalysisCard
 *     analysis={analysisResult}
 *     onDownloadPdf={() => downloadPdf(ticker)}
 *     onSendEmail={() => setShowEmailModal(true)}
 *   />
 */
export function AnalysisCard({ analysis, onDownloadPdf, onSendSms, onSendEmail }: AnalysisCardProps) {
  // ───────────────────────────────────────────────────────────────────────────
  // Computed Values
  // ───────────────────────────────────────────────────────────────────────────

  // Determine confidence color based on value thresholds
  // High confidence (>=70%) = green, moderate (>=50%) = yellow, low (<50%) = red
  const confidenceColor = analysis.confidence >= 0.7
    ? 'text-green-400'
    : analysis.confidence >= 0.5
    ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <div className="bg-gray-800 rounded-xl p-6 space-y-6">
      {/* ─────────────────────────────────────────────────────────────────────
          Header Section
          Shows ticker symbol, timestamp, and large signal badge
          ───────────────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          {/* Ticker Symbol - Large and prominent */}
          <h2 className="text-3xl font-bold text-white">{analysis.ticker}</h2>
          {/* Analysis Timestamp - Formatted for readability */}
          <p className="text-gray-400 text-sm">
            {new Date(analysis.timestamp).toLocaleString()}
          </p>
        </div>
        {/* Signal Badge - Large size for emphasis */}
        <SignalBadge signal={analysis.signal} size="lg" />
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Key Metrics Grid
          Responsive grid: 2 columns on mobile, 4 on desktop
          ───────────────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Confidence Score - Color-coded based on value */}
        <MetricCard
          label="Confidence"
          value={`${(analysis.confidence * 100).toFixed(0)}%`}
          className={confidenceColor}
        />
        {/* Target Price - AI's predicted price target */}
        <MetricCard
          label="Target Price"
          value={`$${analysis.target_price.toFixed(2)}`}
        />
        {/* Upside Potential - Percentage gain to target */}
        <MetricCard
          label="Upside"
          value={`${analysis.potential_upside_pct.toFixed(1)}%`}
          className="text-green-400"
        />
        {/* Stop Loss - Recommended exit point for risk management */}
        <MetricCard
          label="Stop Loss"
          value={`$${analysis.stop_loss.toFixed(2)}`}
          className="text-red-400"
        />
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Sentiment Score Section
          Visual progress bar showing sentiment from -1 to +1
          ───────────────────────────────────────────────────────────────────── */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-2">Sentiment Score</h3>
        {/* Progress bar background */}
        <div className="w-full bg-gray-700 rounded-full h-4">
          {/* Filled portion - width calculated from sentiment score
              Sentiment ranges from -1 to +1, normalized to 0-100% for width */}
          <div
            className={`h-4 rounded-full ${
              // Color based on sentiment value
              analysis.sentiment_score > 0.5 ? 'bg-green-500' :
              analysis.sentiment_score > 0 ? 'bg-yellow-500' : 'bg-red-500'
            }`}
            // Convert -1 to +1 range to 0% to 100% for CSS width
            style={{ width: `${((analysis.sentiment_score + 1) / 2) * 100}%` }}
          />
        </div>
        {/* Numeric sentiment value display */}
        <p className="text-gray-400 text-sm mt-1">
          {analysis.sentiment_score.toFixed(2)} (-1 to 1)
        </p>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Analysis Reasoning Section
          Full text explanation from the AI
          ───────────────────────────────────────────────────────────────────── */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-2">Analysis</h3>
        <p className="text-gray-300 leading-relaxed">{analysis.reasoning}</p>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Mode Information
          Shows analysis mode and agent count
          ───────────────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-sm text-gray-400">
        {/* Analysis mode: single-agent or multi-agent */}
        <span>Mode: {analysis.mode}</span>
        {/* Agent count (only shown for multi-agent mode) */}
        {analysis.agents_used && (
          <span>{analysis.agents_used} agents used</span>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Action Buttons
          Export and notification options (conditionally rendered)
          ───────────────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-700">
        {/* PDF Download Button - Only shown if handler provided */}
        {onDownloadPdf && (
          <button
            onClick={onDownloadPdf}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Download PDF
          </button>
        )}
        {/* SMS Button - Only shown if handler provided */}
        {onSendSms && (
          <button
            onClick={onSendSms}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
          >
            Send SMS
          </button>
        )}
        {/* Email Button - Only shown if handler provided */}
        {onSendEmail && (
          <button
            onClick={onSendEmail}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            Send Email
          </button>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// MetricCard Sub-Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Helper component for displaying a single metric in the metrics grid.
 *
 * Renders a labeled value in a semi-transparent card with
 * optional custom text color for the value.
 *
 * @param {Object} props - Component props
 * @param {string} props.label - Metric label (e.g., "Confidence")
 * @param {string} props.value - Formatted metric value (e.g., "85%")
 * @param {string} [props.className='text-white'] - CSS classes for value text
 * @returns {JSX.Element} Styled metric card
 */
function MetricCard({ label, value, className = 'text-white' }: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className="bg-gray-700/50 rounded-lg p-4">
      {/* Metric label - smaller gray text */}
      <p className="text-gray-400 text-sm">{label}</p>
      {/* Metric value - large bold text with custom color */}
      <p className={`text-2xl font-bold ${className}`}>{value}</p>
    </div>
  )
}
