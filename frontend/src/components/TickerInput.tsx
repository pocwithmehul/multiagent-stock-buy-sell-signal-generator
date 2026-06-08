/**
 * Ticker Input Component
 *
 * A form component for entering stock ticker symbols and initiating analysis.
 * Includes an input field, submit button, and multi-agent mode toggle.
 *
 * Component Structure:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      Ticker Input Form                           │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ [Enter ticker (e.g., AAPL)     ]  [ Analyze ]           │   │
 * │   │      Text Input                     Submit Button        │   │
 * │   │      (auto-uppercase)              (disabled while       │   │
 * │   │                                     loading)              │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ [✓] Use Multi-Agent Analysis (47 specialized agents)    │   │
 * │   │     Checkbox - toggles between single and multi-agent   │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Features:
 *   - Auto-uppercase ticker input (user types "aapl" → "AAPL")
 *   - Validation (prevents empty submissions)
 *   - Loading state with spinner
 *   - Multi-agent toggle (defaults to true)
 *   - Disabled state during analysis
 *
 * Props:
 *   - onSubmit: Callback with (ticker, multiAgent) when form submitted
 *   - isLoading: Shows loading state and disables input
 *
 * References:
 *   - React Forms: https://react.dev/reference/react-dom/components/form
 *   - Tailwind CSS Forms: https://tailwindcss.com/docs/plugins#forms
 */

import { useState, FormEvent } from 'react'

// ─────────────────────────────────────────────────────────────────────────────
// Component Props Interface
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Props for the TickerInput component.
 *
 * @property {(ticker: string, multiAgent: boolean) => void} onSubmit
 *   Callback invoked when the form is submitted with valid input.
 *   Receives the uppercase ticker symbol and multi-agent flag.
 *
 * @property {boolean} [isLoading]
 *   When true, shows loading spinner and disables input/button.
 *   Used to prevent duplicate submissions during analysis.
 */
interface TickerInputProps {
  onSubmit: (ticker: string, multiAgent: boolean) => void
  isLoading?: boolean
}

// ─────────────────────────────────────────────────────────────────────────────
// TickerInput Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Form component for entering stock tickers and triggering analysis.
 *
 * Manages local state for:
 *   - ticker: The input value (auto-uppercased)
 *   - multiAgent: Whether to use 47-agent analysis
 *
 * Validation:
 *   - Trims whitespace from input
 *   - Converts to uppercase for consistency
 *   - Prevents submission of empty input
 *
 * @param {TickerInputProps} props - Component props
 * @returns {JSX.Element} Form with input, button, and checkbox
 *
 * @example
 *   function Dashboard() {
 *     const [isAnalyzing, setIsAnalyzing] = useState(false)
 *
 *     const handleAnalyze = async (ticker: string, multiAgent: boolean) => {
 *       setIsAnalyzing(true)
 *       await runAnalysis(ticker, multiAgent)
 *       setIsAnalyzing(false)
 *     }
 *
 *     return (
 *       <TickerInput
 *         onSubmit={handleAnalyze}
 *         isLoading={isAnalyzing}
 *       />
 *     )
 *   }
 */
export function TickerInput({ onSubmit, isLoading }: TickerInputProps) {
  // ───────────────────────────────────────────────────────────────────────────
  // Local State
  // ───────────────────────────────────────────────────────────────────────────

  // Ticker input value - stored as uppercase
  const [ticker, setTicker] = useState('')

  // Multi-agent mode toggle - defaults to enabled
  // When true, uses 47 specialized agents; when false, uses single agent
  const [multiAgent, setMultiAgent] = useState(true)

  // ───────────────────────────────────────────────────────────────────────────
  // Form Submission Handler
  // ───────────────────────────────────────────────────────────────────────────

  /**
   * Handles form submission.
   *
   * Prevents default form behavior, validates input,
   * and calls onSubmit with normalized values.
   *
   * @param {FormEvent} e - Form submit event
   */
  const handleSubmit = (e: FormEvent) => {
    // Prevent page reload on form submit
    e.preventDefault()

    // Validate: only submit if ticker has content after trimming
    if (ticker.trim()) {
      // Call parent callback with uppercase ticker and multi-agent flag
      onSubmit(ticker.trim().toUpperCase(), multiAgent)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* ─────────────────────────────────────────────────────────────────────
          Input Row: Ticker Input + Submit Button
          ───────────────────────────────────────────────────────────────────── */}
      <div className="flex gap-4">
        {/* Ticker Input Field */}
        <input
          type="text"
          value={ticker}
          // Auto-uppercase as user types for consistent formatting
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Enter ticker (e.g., AAPL)"
          className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          // Disable input while analysis is running
          disabled={isLoading}
        />

        {/* Submit Button */}
        <button
          type="submit"
          // Disabled when loading or no input provided
          disabled={isLoading || !ticker.trim()}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
        >
          {isLoading ? (
            // Loading State: Show spinner and "Analyzing..." text
            <span className="flex items-center">
              {/* Animated spinner SVG */}
              <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Analyzing...
            </span>
          ) : (
            // Default State: Show "Analyze" button text
            'Analyze'
          )}
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────
          Multi-Agent Mode Toggle
          ───────────────────────────────────────────────────────────────────── */}
      <label className="flex items-center space-x-2 text-gray-300">
        <input
          type="checkbox"
          checked={multiAgent}
          onChange={(e) => setMultiAgent(e.target.checked)}
          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
        />
        {/* Descriptive label explaining the option */}
        <span>Use Multi-Agent Analysis (47 specialized agents)</span>
      </label>
    </form>
  )
}
