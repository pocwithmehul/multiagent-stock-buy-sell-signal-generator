/**
 * React Application Entry Point
 *
 * This is the main entry point for the Stock Signal React dashboard.
 * It initializes the React application with necessary providers and renders
 * the root component into the DOM.
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         main.tsx                                 │
 * │                    (Application Bootstrap)                       │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │              React.StrictMode                            │   │
 * │   │   (Development checks for potential problems)            │   │
 * │   │                                                          │   │
 * │   │   ┌─────────────────────────────────────────────────┐   │   │
 * │   │   │         QueryClientProvider                      │   │   │
 * │   │   │   (TanStack Query for data fetching/caching)     │   │   │
 * │   │   │                                                  │   │   │
 * │   │   │   ┌─────────────────────────────────────────┐   │   │   │
 * │   │   │   │              App                         │   │   │   │
 * │   │   │   │   (Router + Components)                  │   │   │   │
 * │   │   │   └─────────────────────────────────────────┘   │   │   │
 * │   │   │                                                  │   │   │
 * │   │   └─────────────────────────────────────────────────┘   │   │
 * │   │                                                          │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Dependencies:
 *   - React 18: Core UI library with concurrent features
 *   - ReactDOM: DOM rendering for React components
 *   - @tanstack/react-query: Server state management and caching
 *
 * References:
 *   - React 18: https://react.dev/
 *   - TanStack Query: https://tanstack.com/query/latest
 *   - Vite: https://vitejs.dev/
 */

import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

// ─────────────────────────────────────────────────────────────────────────────
// Query Client Configuration
// ─────────────────────────────────────────────────────────────────────────────

/**
 * TanStack Query Client instance with default configuration.
 *
 * This client manages all data fetching, caching, and synchronization
 * with the backend API. It provides:
 *   - Automatic caching of API responses
 *   - Background refetching for stale data
 *   - Retry logic for failed requests
 *   - Optimistic updates support
 *
 * Configuration:
 *   - staleTime: 5 minutes - Data is considered fresh for this duration
 *   - retry: 2 attempts - Failed requests are retried up to 2 times
 *
 * Usage in components:
 *   const { data, isLoading } = useQuery({ queryKey: ['key'], queryFn: fn })
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data remains fresh for 5 minutes before refetching
      // This reduces unnecessary API calls for frequently accessed data
      staleTime: 1000 * 60 * 5, // 5 minutes

      // Retry failed requests up to 2 times
      // Helps handle transient network issues
      retry: 2,
    },
  },
})

// ─────────────────────────────────────────────────────────────────────────────
// Application Rendering
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mount the React application to the DOM.
 *
 * The application is wrapped in:
 *   1. React.StrictMode - Enables additional development checks:
 *      - Warns about deprecated lifecycle methods
 *      - Detects unexpected side effects
 *      - Ensures reusable state (double invokes effects in dev)
 *
 *   2. QueryClientProvider - Makes QueryClient available to all components
 *      via React Context for data fetching hooks
 *
 * The root element is defined in index.html as <div id="root"></div>
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
