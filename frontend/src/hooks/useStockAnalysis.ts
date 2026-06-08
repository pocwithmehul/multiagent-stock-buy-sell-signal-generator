/**
 * Custom React Hooks for Stock Analysis
 *
 * This module provides reusable hooks built on TanStack Query for
 * fetching and mutating stock analysis data. These hooks handle
 * caching, loading states, error handling, and background refetching.
 *
 * Hook Pattern:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      Custom Hooks                                │
 * │                  (hooks/useStockAnalysis.ts)                     │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   Component                                                     │
 * │       │                                                          │
 * │       ▼                                                          │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │   useStockAnalysis(ticker)                               │   │
 * │   │   • Returns cached analysis                              │   │
 * │   │   • Auto-fetches when ticker changes                     │   │
 * │   │   • Manages loading/error states                         │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │   useAnalyzeMutation()                                   │   │
 * │   │   • Triggers new analysis                                │   │
 * │   │   • Returns mutation function + state                    │   │
 * │   │   • For imperative analysis requests                     │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │   useHealthCheck()                                       │   │
 * │   │   • Polls API health every 30s                           │   │
 * │   │   • Used by Layout for status badge                      │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * TanStack Query Benefits:
 *   - Automatic caching with configurable stale time
 *   - Background refetching when data becomes stale
 *   - Request deduplication (multiple components, one request)
 *   - Optimistic updates support
 *   - Built-in loading/error states
 *
 * Dependencies:
 *   - @tanstack/react-query: Data fetching and caching library
 *
 * References:
 *   - TanStack Query: https://tanstack.com/query/latest
 *   - useQuery: https://tanstack.com/query/latest/docs/react/reference/useQuery
 *   - useMutation: https://tanstack.com/query/latest/docs/react/reference/useMutation
 */

import { useMutation, useQuery } from '@tanstack/react-query'
import { stockApi } from '../services/api'
import type { AnalysisRequest } from '../types'

// ─────────────────────────────────────────────────────────────────────────────
// Analysis Hooks
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Hook to fetch cached stock analysis for a specific ticker.
 *
 * This hook retrieves previously computed analysis from the backend cache.
 * It does NOT trigger a new analysis - use useAnalyzeMutation for that.
 *
 * Query Key: ['analysis', ticker]
 *   - Caching is scoped to this key
 *   - Changing ticker triggers new fetch
 *
 * Behavior:
 *   - Enabled only when ticker is provided (prevents empty requests)
 *   - Returns null if no cached analysis exists
 *   - Automatically refetches when component remounts
 *
 * @param {string | undefined} ticker - Stock symbol or undefined
 * @returns {UseQueryResult} TanStack Query result with:
 *   - data: StockAnalysis | null
 *   - isLoading: boolean
 *   - error: Error | null
 *   - refetch: () => void
 *
 * @example
 *   function AnalysisPage() {
 *     const { ticker } = useParams()
 *     const { data, isLoading, error } = useStockAnalysis(ticker)
 *
 *     if (isLoading) return <Spinner />
 *     if (error) return <Error />
 *     if (!data) return <NotFound />
 *
 *     return <AnalysisCard analysis={data} />
 *   }
 */
export function useStockAnalysis(ticker: string | undefined) {
  return useQuery({
    // Unique query key for caching - includes ticker for per-stock caching
    queryKey: ['analysis', ticker],

    // Function that fetches the data
    queryFn: () => stockApi.getAnalysis(ticker!),

    // Only run query if ticker is defined
    // Prevents unnecessary API calls with undefined/empty ticker
    enabled: !!ticker,
  })
}

/**
 * Hook to trigger a new stock analysis.
 *
 * This mutation hook provides an imperative way to run analysis.
 * Unlike useStockAnalysis (which fetches cached data), this actively
 * triggers the 47-agent analysis pipeline on the backend.
 *
 * Use Cases:
 *   - Form submission (analyze button click)
 *   - Refresh/re-run existing analysis
 *   - Programmatic analysis triggers
 *
 * Mutation State:
 *   - isPending: Analysis is running
 *   - isError: Analysis failed
 *   - isSuccess: Analysis completed
 *   - data: Analysis result (after success)
 *
 * @returns {UseMutationResult} TanStack mutation result with:
 *   - mutate: (request) => void (fire and forget)
 *   - mutateAsync: (request) => Promise (awaitable)
 *   - isPending: boolean
 *   - isError: boolean
 *   - data: StockAnalysis | undefined
 *
 * @example
 *   function AnalyzeForm() {
 *     const mutation = useAnalyzeMutation()
 *
 *     const handleSubmit = async (ticker: string) => {
 *       try {
 *         const result = await mutation.mutateAsync({
 *           ticker,
 *           multi_agent: true,
 *           verbose: true
 *         })
 *         console.log('Signal:', result.signal)
 *       } catch (error) {
 *         console.error('Analysis failed:', error)
 *       }
 *     }
 *
 *     return (
 *       <button
 *         onClick={() => handleSubmit('AAPL')}
 *         disabled={mutation.isPending}
 *       >
 *         {mutation.isPending ? 'Analyzing...' : 'Analyze'}
 *       </button>
 *     )
 *   }
 */
export function useAnalyzeMutation() {
  return useMutation({
    // Function called when mutate/mutateAsync is invoked
    mutationFn: (request: AnalysisRequest) => stockApi.analyze(request),
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Health Check Hook
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Hook to poll API health status.
 *
 * This hook periodically checks the backend API health endpoint
 * and is used by the Layout component to display the environment
 * badge in the header.
 *
 * Features:
 *   - Polls every 30 seconds (refetchInterval)
 *   - Provides real-time API status awareness
 *   - Shows environment info (local, qa, stg, prod)
 *
 * Query Key: ['health']
 *   - Shared across all components using this hook
 *   - Single request even with multiple consumers
 *
 * @returns {UseQueryResult} TanStack Query result with:
 *   - data: HealthResponse | undefined
 *   - isLoading: boolean
 *   - error: Error | null
 *
 * @example
 *   function Header() {
 *     const { data: health } = useHealthCheck()
 *
 *     return (
 *       <header>
 *         {health && (
 *           <span className="badge">
 *             {health.environment.toUpperCase()}
 *           </span>
 *         )}
 *       </header>
 *     )
 *   }
 */
export function useHealthCheck() {
  return useQuery({
    // Query key for health check caching
    queryKey: ['health'],

    // Fetch health status from API
    queryFn: () => stockApi.health(),

    // Poll for health every 30 seconds
    // Keeps the UI in sync with backend availability
    refetchInterval: 30000, // 30 seconds
  })
}
