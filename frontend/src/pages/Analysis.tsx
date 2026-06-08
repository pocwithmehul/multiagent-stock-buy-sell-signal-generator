/**
 * Analysis Page Component
 *
 * A route-based page that displays a cached stock analysis for a specific
 * ticker. The ticker is extracted from the URL parameter and used to fetch
 * the analysis from the backend cache.
 *
 * Route: /analysis/:ticker
 *   - Example: /analysis/AAPL, /analysis/MSFT
 *
 * Page States:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      Analysis Page                               │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   State 1: Loading                                              │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │                    [Spinner]                             │   │
 * │   │            Loading analysis for AAPL...                  │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   State 2: Not Found (error or no data)                         │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              Analysis Not Found                          │   │
 * │   │   No analysis found for AAPL. Go back to dashboard.      │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   State 3: Success                                              │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              AnalysisCard                                │   │
 * │   │   (Full analysis results display)                        │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Use Cases:
 *   - Deep linking to specific analysis results
 *   - Sharing analysis URLs with others
 *   - Bookmarking analysis for later reference
 *
 * Data Flow:
 *   1. Extract ticker from URL params
 *   2. Fetch cached analysis via useStockAnalysis hook
 *   3. Display loading, error, or result state
 *
 * Dependencies:
 *   - react-router-dom: For useParams hook
 *   - useStockAnalysis: TanStack Query hook for fetching
 *   - AnalysisCard: Component for displaying results
 *
 * References:
 *   - React Router useParams: https://reactrouter.com/en/main/hooks/use-params
 */

import { useParams } from 'react-router-dom'
import { useStockAnalysis } from '../hooks/useStockAnalysis'
import { AnalysisCard } from '../components/AnalysisCard'

// ─────────────────────────────────────────────────────────────────────────────
// Analysis Page Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Page component for displaying a specific stock's analysis.
 *
 * Extracts the ticker symbol from the URL and fetches the corresponding
 * cached analysis from the backend. Handles loading and error states
 * with appropriate UI feedback.
 *
 * URL Pattern: /analysis/:ticker
 *   - The :ticker segment is a dynamic parameter
 *   - Example: /analysis/AAPL → ticker = "AAPL"
 *
 * States:
 *   - isLoading: Shows spinner while fetching
 *   - error/!data: Shows "Not Found" message
 *   - data: Shows AnalysisCard with results
 *
 * @returns {JSX.Element} Page content based on current state
 *
 * @example
 *   // In App.tsx routing
 *   <Route path="analysis/:ticker" element={<Analysis />} />
 *
 *   // Direct navigation
 *   navigate('/analysis/AAPL')
 */
export function Analysis() {
  // ───────────────────────────────────────────────────────────────────────────
  // URL Parameters
  // ───────────────────────────────────────────────────────────────────────────

  // Extract ticker from URL path parameter
  // TypeScript generic ensures type safety for the params object
  const { ticker } = useParams<{ ticker: string }>()

  // ───────────────────────────────────────────────────────────────────────────
  // Data Fetching
  // ───────────────────────────────────────────────────────────────────────────

  // Fetch cached analysis using TanStack Query
  // - data: StockAnalysis | null
  // - isLoading: true while request is in flight
  // - error: Error object if request failed
  const { data: analysis, isLoading, error } = useStockAnalysis(ticker)

  // ───────────────────────────────────────────────────────────────────────────
  // Loading State
  // Shows centered spinner while fetching analysis
  // ───────────────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          {/* Animated spinner SVG */}
          <svg className="animate-spin h-12 w-12 text-blue-500 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            {/* Outer circle - faded */}
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            {/* Inner arc - spinning indicator */}
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {/* Loading message with ticker */}
          <p className="text-gray-400 mt-4">Loading analysis for {ticker}...</p>
        </div>
      </div>
    )
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Error / Not Found State
  // Shows message when analysis doesn't exist or fetch failed
  // ───────────────────────────────────────────────────────────────────────────

  if (error || !analysis) {
    return (
      <div className="text-center py-12">
        {/* Error heading */}
        <h2 className="text-2xl font-bold text-white">Analysis Not Found</h2>
        {/* Helpful message with ticker and navigation hint */}
        <p className="text-gray-400 mt-2">
          No analysis found for {ticker}. Go back to the dashboard to run a new analysis.
        </p>
      </div>
    )
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Success State
  // Shows the full analysis card with results
  // ───────────────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl mx-auto">
      {/* Render analysis results in card format
          Note: Action buttons not provided on this page
          Users can access full functionality from Dashboard */}
      <AnalysisCard analysis={analysis} />
    </div>
  )
}
