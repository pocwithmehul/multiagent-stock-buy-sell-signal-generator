/**
 * Layout Component
 *
 * This component provides the consistent page structure (header, footer)
 * that wraps all pages in the application. It uses React Router's Outlet
 * to render the matched child route content.
 *
 * Layout Structure:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                           Header                                 │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │ 📈 Stock Signal                    [ENV Badge]          │   │
 * │   │    (Link to /)                     (from health API)    │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                           Main                                   │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │                                                          │   │
 * │   │               <Outlet />                                 │   │
 * │   │   (Renders Dashboard or Analysis based on route)         │   │
 * │   │                                                          │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                           Footer                                 │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │        Stock Signal Dashboard - AI-Powered               │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Features:
 *   - Dark theme with gray-900 background
 *   - Responsive container (max-w-7xl)
 *   - Health status indicator in header
 *   - Navigation via header logo
 *
 * Dependencies:
 *   - react-router-dom: For Outlet and Link
 *   - useHealthCheck: For API status polling
 *
 * References:
 *   - React Router Outlet: https://reactrouter.com/en/main/components/outlet
 *   - Tailwind CSS: https://tailwindcss.com/docs
 */

import { Outlet, Link } from 'react-router-dom'
import { useHealthCheck } from '../hooks/useStockAnalysis'

/**
 * Main layout wrapper component.
 *
 * Renders on all routes as the parent route element in App.tsx.
 * The Outlet component renders the matched child route (Dashboard or Analysis).
 *
 * Health Status:
 *   - Polls /health every 30 seconds via useHealthCheck
 *   - Displays environment badge (LOCAL, QA, STG, PROD)
 *   - Green dot indicates healthy API connection
 *
 * Styling:
 *   - Uses Tailwind CSS utility classes
 *   - Dark theme (bg-gray-900 base)
 *   - Responsive padding and max-width constraints
 *
 * @returns {JSX.Element} Layout structure with header, main content, and footer
 */
export function Layout() {
  // Poll API health status every 30 seconds
  // Used to display environment badge in header
  const { data: health } = useHealthCheck()

  return (
    <div className="min-h-screen bg-gray-900">
      {/* ─────────────────────────────────────────────────────────────────────
          Header Section
          - Contains logo/brand link to home
          - Displays API environment status badge
          ───────────────────────────────────────────────────────────────────── */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Brand/Logo - Links back to dashboard */}
            <Link to="/" className="flex items-center space-x-2">
              <span className="text-2xl">📈</span>
              <span className="text-xl font-bold text-white">Stock Signal</span>
            </Link>

            {/* Environment Status Badge */}
            <div className="flex items-center space-x-4">
              {health && (
                <span className="flex items-center text-sm text-gray-400">
                  {/* Green status dot - indicates healthy API */}
                  <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                  {/* Environment name (LOCAL, QA, STG, PROD) */}
                  {health.environment.toUpperCase()}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────────────
          Main Content Area
          - Outlet renders the matched child route component
          - Dashboard for "/" or Analysis for "/analysis/:ticker"
          ───────────────────────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* React Router Outlet - renders child routes defined in App.tsx */}
        <Outlet />
      </main>

      {/* ─────────────────────────────────────────────────────────────────────
          Footer Section
          - Simple branding footer
          - mt-auto pushes footer to bottom of viewport
          ───────────────────────────────────────────────────────────────────── */}
      <footer className="bg-gray-800 border-t border-gray-700 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-gray-400 text-sm">
            Stock Signal Dashboard - AI-Powered Stock Analysis
          </p>
        </div>
      </footer>
    </div>
  )
}
