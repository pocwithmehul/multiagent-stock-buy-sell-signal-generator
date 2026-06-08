/**
 * Signal Badge Component
 *
 * A visual badge component that displays stock signal recommendations
 * (BUY, SELL, HOLD) with appropriate color coding. Used throughout
 * the application to highlight the AI's recommendation.
 *
 * Signal Colors:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      Signal Badge                                │
 * ├─────────────────────────────────────────────────────────────────┤
 * │                                                                  │
 * │   ┌─────────────────┐                                           │
 * │   │      BUY        │  Green - Positive recommendation          │
 * │   │  (bg-buy-light) │  Indicates buy opportunity                │
 * │   └─────────────────┘                                           │
 * │                                                                  │
 * │   ┌─────────────────┐                                           │
 * │   │     SELL        │  Red - Negative recommendation            │
 * │   │ (bg-sell-light) │  Indicates sell/exit position             │
 * │   └─────────────────┘                                           │
 * │                                                                  │
 * │   ┌─────────────────┐                                           │
 * │   │     HOLD        │  Yellow - Neutral recommendation          │
 * │   │ (bg-hold-light) │  Indicates maintain current position      │
 * │   └─────────────────┘                                           │
 * │                                                                  │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Size Variants:
 *   - sm: Small (px-2 py-0.5 text-xs) - For inline use
 *   - md: Medium (px-3 py-1 text-sm) - Default, general use
 *   - lg: Large (px-4 py-2 text-base) - For headers/highlights
 *
 * Custom Colors:
 *   The component uses custom Tailwind colors defined in tailwind.config.js:
 *   - buy-light/buy-dark: Green tones for BUY signals
 *   - sell-light/sell-dark: Red tones for SELL signals
 *   - hold-light/hold-dark: Yellow tones for HOLD signals
 *
 * Dependencies:
 *   - clsx: Utility for conditional class composition
 *
 * References:
 *   - clsx: https://github.com/lukeed/clsx
 *   - Tailwind CSS: https://tailwindcss.com/docs
 */

import { clsx } from 'clsx'
import type { Signal } from '../types'

// ─────────────────────────────────────────────────────────────────────────────
// Component Props Interface
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Props for the SignalBadge component.
 *
 * @property {Signal} signal - The signal to display (BUY, SELL, or HOLD)
 * @property {'sm' | 'md' | 'lg'} [size='md'] - Size variant for the badge
 */
interface SignalBadgeProps {
  signal: Signal
  size?: 'sm' | 'md' | 'lg'
}

// ─────────────────────────────────────────────────────────────────────────────
// SignalBadge Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Renders a colored badge displaying a stock signal.
 *
 * The badge uses semantic colors to convey the recommendation:
 *   - Green for BUY (positive/bullish)
 *   - Red for SELL (negative/bearish)
 *   - Yellow for HOLD (neutral/wait)
 *
 * @param {SignalBadgeProps} props - Component props
 * @returns {JSX.Element} Styled badge element
 *
 * @example
 *   // Basic usage
 *   <SignalBadge signal="BUY" />
 *
 *   // With custom size
 *   <SignalBadge signal="SELL" size="lg" />
 *
 *   // In analysis header
 *   <div className="flex items-center gap-2">
 *     <h2>{ticker}</h2>
 *     <SignalBadge signal={analysis.signal} size="md" />
 *   </div>
 */
export function SignalBadge({ signal, size = 'md' }: SignalBadgeProps) {
  // ───────────────────────────────────────────────────────────────────────────
  // Size Classes
  // Define padding and text size for each size variant
  // ───────────────────────────────────────────────────────────────────────────
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',   // Small - compact inline badges
    md: 'px-3 py-1 text-sm',     // Medium - default size
    lg: 'px-4 py-2 text-base',   // Large - prominent display
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Signal-Specific Colors
  // Maps each signal type to its background and text color classes
  // These use custom colors defined in tailwind.config.js
  // ───────────────────────────────────────────────────────────────────────────
  const signalClasses = {
    BUY: 'bg-buy-light text-buy-dark',    // Green tones - bullish
    SELL: 'bg-sell-light text-sell-dark', // Red tones - bearish
    HOLD: 'bg-hold-light text-hold-dark', // Yellow tones - neutral
  }

  return (
    <span
      className={clsx(
        // Base badge styling - pill shape with semibold text
        'inline-flex items-center rounded-full font-semibold',
        // Apply size-specific classes
        sizeClasses[size],
        // Apply signal-specific color classes
        signalClasses[signal]
      )}
    >
      {/* Display the signal text (BUY, SELL, or HOLD) */}
      {signal}
    </span>
  )
}
