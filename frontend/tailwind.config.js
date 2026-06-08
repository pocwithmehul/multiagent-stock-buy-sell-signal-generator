/**
 * Tailwind CSS Configuration
 *
 * This file configures Tailwind CSS for the Stock Signal React dashboard.
 * It defines content sources for purging unused styles and extends the
 * default theme with custom colors for stock signals.
 *
 * Configuration Structure:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                    Tailwind Config                               │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   content: [...]         → Files to scan for class usage        │
 * │                            (enables tree-shaking of CSS)        │
 * │                                                                  │
 * │   theme.extend: {        → Custom theme extensions              │
 * │     colors: {                                                    │
 * │       buy:  { light, DEFAULT, dark }  → Green for BUY signals   │
 * │       sell: { light, DEFAULT, dark }  → Red for SELL signals    │
 * │       hold: { light, DEFAULT, dark }  → Yellow for HOLD signals │
 * │     }                                                            │
 * │   }                                                              │
 * │                                                                  │
 * │   plugins: []            → Tailwind plugins (none currently)    │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Color Variants:
 *   Each signal color has three variants:
 *   - light: Background color for badges (pastel)
 *   - DEFAULT: Primary color for accents
 *   - dark: Text color for contrast on light backgrounds
 *
 * Usage in CSS/Components:
 *   - bg-buy-light     → Light green background
 *   - text-buy-dark    → Dark green text
 *   - border-sell      → Red border (uses DEFAULT)
 *   - bg-hold-light    → Light yellow background
 *
 * Build Process:
 *   Tailwind scans files in `content` array during build and only
 *   includes CSS for classes that are actually used, reducing bundle size.
 *
 * References:
 *   - Tailwind Configuration: https://tailwindcss.com/docs/configuration
 *   - Custom Colors: https://tailwindcss.com/docs/customizing-colors
 *   - Content Configuration: https://tailwindcss.com/docs/content-configuration
 */

/** @type {import('tailwindcss').Config} */
export default {
  // ───────────────────────────────────────────────────────────────────────────
  // Content Sources
  // Files to scan for Tailwind class usage (enables tree-shaking)
  // ───────────────────────────────────────────────────────────────────────────
  content: [
    "./index.html",           // Main HTML template
    "./src/**/*.{js,ts,jsx,tsx}",  // All source files (React components)
  ],

  // ───────────────────────────────────────────────────────────────────────────
  // Theme Configuration
  // Extends Tailwind's default theme with custom values
  // ───────────────────────────────────────────────────────────────────────────
  theme: {
    extend: {
      // Custom color palette for stock signals
      colors: {
        // ─────────────────────────────────────────────────────────────────────
        // BUY Signal Colors (Green)
        // Used for positive/bullish recommendations
        // ─────────────────────────────────────────────────────────────────────
        buy: {
          light: '#dcfce7',   // Pastel green - badge background
          DEFAULT: '#22c55e', // Vibrant green - accents, borders
          dark: '#166534',    // Dark green - text on light background
        },

        // ─────────────────────────────────────────────────────────────────────
        // SELL Signal Colors (Red)
        // Used for negative/bearish recommendations
        // ─────────────────────────────────────────────────────────────────────
        sell: {
          light: '#fee2e2',   // Pastel red - badge background
          DEFAULT: '#ef4444', // Vibrant red - accents, borders
          dark: '#991b1b',    // Dark red - text on light background
        },

        // ─────────────────────────────────────────────────────────────────────
        // HOLD Signal Colors (Yellow/Amber)
        // Used for neutral/wait recommendations
        // ─────────────────────────────────────────────────────────────────────
        hold: {
          light: '#fef3c7',   // Pastel yellow - badge background
          DEFAULT: '#f59e0b', // Vibrant amber - accents, borders
          dark: '#92400e',    // Dark amber - text on light background
        },
      },
    },
  },

  // ───────────────────────────────────────────────────────────────────────────
  // Plugins
  // Tailwind plugins for additional functionality (none currently)
  // ───────────────────────────────────────────────────────────────────────────
  plugins: [],
}
