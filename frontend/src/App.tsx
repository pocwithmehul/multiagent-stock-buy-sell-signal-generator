/**
 * Root Application Component
 *
 * This component sets up the client-side routing for the Stock Signal
 * dashboard using React Router. It defines the application's URL structure
 * and maps routes to their corresponding page components.
 *
 * Route Structure:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         BrowserRouter                           │
 * │                    (HTML5 History API)                          │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   Route: "/" (Layout wrapper)                                   │
 * │   ┌─────────────────────────────────────────────────────────┐   │
 * │   │                      Layout                              │   │
 * │   │   (Header + Footer + <Outlet/>)                          │   │
 * │   │                                                          │   │
 * │   │   ┌─────────────────────────────────────────────────┐   │   │
 * │   │   │ Route: "/" (index)                               │   │   │
 * │   │   │ Component: Dashboard                             │   │   │
 * │   │   │ - Ticker input form                              │   │   │
 * │   │   │ - Watchlist management                           │   │   │
 * │   │   │ - Schedule configuration                         │   │   │
 * │   │   │ - Analysis results display                       │   │   │
 * │   │   └─────────────────────────────────────────────────┘   │   │
 * │   │                                                          │   │
 * │   │   ┌─────────────────────────────────────────────────┐   │   │
 * │   │   │ Route: "/analysis/:ticker"                       │   │   │
 * │   │   │ Component: Analysis                              │   │   │
 * │   │   │ - Displays cached analysis for specific ticker   │   │   │
 * │   │   │ - URL parameter: ticker (e.g., /analysis/AAPL)   │   │   │
 * │   │   └─────────────────────────────────────────────────┘   │   │
 * │   │                                                          │   │
 * │   └─────────────────────────────────────────────────────────┘   │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Navigation Flow:
 *   1. User lands on "/" → Dashboard with input form
 *   2. User enters ticker → Analysis runs inline
 *   3. User can navigate to "/analysis/AAPL" → View cached analysis
 *
 * Dependencies:
 *   - react-router-dom: Client-side routing library
 *
 * References:
 *   - React Router: https://reactrouter.com/
 *   - Outlet (nested routes): https://reactrouter.com/en/main/components/outlet
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Analysis } from './pages/Analysis'

/**
 * Root App component that configures application routing.
 *
 * Uses BrowserRouter for clean URLs (no hash) via HTML5 History API.
 * The Layout component wraps all routes, providing consistent header/footer.
 *
 * Route Configuration:
 *   - "/" (index): Main dashboard with ticker input and analysis
 *   - "/analysis/:ticker": Individual stock analysis view (deep link)
 *
 * @returns {JSX.Element} The configured router with all application routes
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/*
          Layout route wraps all pages with consistent header/footer.
          The <Outlet /> in Layout renders the matched child route.
        */}
        <Route path="/" element={<Layout />}>
          {/*
            Index route - Dashboard is the default landing page.
            Rendered when URL is exactly "/"
          */}
          <Route index element={<Dashboard />} />

          {/*
            Analysis route with dynamic ticker parameter.
            Example: /analysis/AAPL, /analysis/MSFT
            The :ticker segment is accessible via useParams() hook
          */}
          <Route path="analysis/:ticker" element={<Analysis />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
