/**
 * Vite Environment Type Definitions
 *
 * This file provides TypeScript type declarations for Vite-specific
 * features and environment variables. It extends the global types
 * with Vite's client-side APIs.
 *
 * Purpose:
 *   - Enables TypeScript support for Vite's import.meta.env
 *   - Provides types for Vite's module hot reloading (HMR)
 *   - Supports static asset imports (.svg, .png, etc.)
 *
 * Environment Variables:
 *   Vite exposes environment variables via import.meta.env:
 *
 *   Built-in:
 *     - import.meta.env.MODE      → "development" or "production"
 *     - import.meta.env.DEV       → true in dev mode
 *     - import.meta.env.PROD      → true in production
 *     - import.meta.env.BASE_URL  → Base URL for the app
 *
 *   Custom (prefixed with VITE_):
 *     - import.meta.env.VITE_API_BASE_URL → API base URL
 *
 * Usage:
 *   // Access environment variables with type safety
 *   const apiUrl = import.meta.env.VITE_API_BASE_URL || '/api'
 *
 *   // Check environment
 *   if (import.meta.env.DEV) {
 *     console.log('Development mode')
 *   }
 *
 * References:
 *   - Vite Env Variables: https://vitejs.dev/guide/env-and-mode.html
 *   - TypeScript Triple-Slash: https://www.typescriptlang.org/docs/handbook/triple-slash-directives.html
 */

/// <reference types="vite/client" />
