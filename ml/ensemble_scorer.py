"""
Ensemble Scorer Module for Multi-Agent Signal Combination.

This module implements a weighted ensemble model that combines signals
from multiple specialized agents to produce a final trading recommendation.

Library Dependencies:
    - numpy: Numerical computing (https://numpy.org/doc/stable/)
    - pandas: Data manipulation (https://pandas.pydata.org/docs/)
    - typing: Type hints (https://docs.python.org/3/library/typing.html)
    - collections: Specialized container datatypes (https://docs.python.org/3/library/collections.html)
"""

# numpy: Numerical computing library
# Used for: Array operations (though not heavily used in this module)
# Reference: https://numpy.org/doc/stable/reference/
import numpy as np

# pandas: Data manipulation library
# Used for: Potential DataFrame operations in calibration
# Reference: https://pandas.pydata.org/docs/reference/index.html
import pandas as pd

# typing: Type hints for code documentation
# Dict: Dictionary type hint
# List: List type hint
# Optional: Indicates nullable type
# Reference: https://docs.python.org/3/library/typing.html
from typing import Dict, List, Optional

# collections.defaultdict: Dict subclass with default value factory
# Used for: Automatic initialization of nested dictionaries
# Reference: https://docs.python.org/3/library/collections.html#collections.defaultdict
from collections import defaultdict


class EnsembleScorer:
    """
    Ensemble model that weights and combines signals from multiple agents.

    Learns optimal weights based on historical performance or uses
    pre-defined default weights based on general reliability of each source.

    Attributes:
        weights (Dict[str, float]): Current agent weights (normalized to sum to 1)
        performance_history (defaultdict): Historical accuracy tracking per agent
        is_calibrated (bool): Whether weights have been learned from data
    """

    # ── Default Agent Weights ──────────────────────────────────────────
    # Pre-defined weights based on general reliability of each data source
    # Higher weight = more influence on final signal
    # Weights should sum to approximately 1.0
    # Class variable: Shared across all instances
    # dict literal: Create mapping of agent name to weight
    DEFAULT_WEIGHTS = {
        "technical": 0.15,        # Technical analysis - most reliable
        "news": 0.08,             # News sentiment
        "sentiment": 0.10,        # Overall sentiment aggregation
        "sec": 0.05,              # SEC filings analysis
        "zacks": 0.08,            # Zacks ratings
        "tipranks": 0.08,         # TipRanks analyst consensus
        "seekingalpha": 0.06,     # Seeking Alpha analysis
        "insider": 0.07,          # Insider/institutional trading
        "motleyfool": 0.05,       # Motley Fool recommendations
        "stockstory": 0.04,       # StockStory analysis
        "yahoofinance": 0.06,     # Yahoo Finance data
        "morningstar": 0.06,      # Morningstar ratings
        "gurufocus": 0.04,        # GuruFocus value analysis
        "reddit": 0.02,           # Reddit sentiment (less reliable)
        "stocktwits": 0.02,       # StockTwits social sentiment
        "options_flow": 0.04,     # Options market flow
    }

    # ── Signal Value Mapping ───────────────────────────────────────────
    # Convert string signals to numeric values for weighted averaging
    # Class variable: Shared mapping across all instances
    SIGNAL_VALUES = {
        "BUY": 1.0,               # Bullish signal = positive value
        "BULLISH": 1.0,           # Alternative bullish signal
        "HOLD": 0.0,              # Neutral signal = zero
        "NEUTRAL": 0.0,           # Alternative neutral signal
        "SELL": -1.0,             # Bearish signal = negative value
        "BEARISH": -1.0,          # Alternative bearish signal
    }

    def __init__(self):
        """
        Initialize the ensemble scorer.

        Creates a copy of default weights and sets up tracking structures.
        """
        # Create copy of default weights for this instance
        # dict.copy(): Shallow copy of dictionary
        # Reference: https://docs.python.org/3/library/stdtypes.html#dict.copy
        self.weights = self.DEFAULT_WEIGHTS.copy()

        # defaultdict with list factory for tracking historical accuracy
        # defaultdict(list): Auto-creates empty list for missing keys
        # Reference: https://docs.python.org/3/library/collections.html#collections.defaultdict
        self.performance_history = defaultdict(list)

        # Flag indicating if weights have been learned from data
        # bool type: Initially False until calibrate() is called
        self.is_calibrated = False

    def _signal_to_value(self, signal: str) -> float:
        """
        Convert signal string to numeric value.

        Args:
            signal (str): Signal string (BUY, SELL, HOLD, BULLISH, BEARISH, NEUTRAL)

        Returns:
            float: Numeric value (-1.0 to 1.0), defaults to 0.0 for unknown
        """
        # Normalize signal to uppercase, handle None
        # str.upper(): Convert to uppercase
        # Reference: https://docs.python.org/3/library/stdtypes.html#str.upper
        # or operator: Returns first truthy value (handles None case)
        signal = signal.upper() if signal else "NEUTRAL"

        # Look up value in mapping, default to 0.0 (neutral)
        # dict.get(key, default): Get value or default
        # Reference: https://docs.python.org/3/library/stdtypes.html#dict.get
        return self.SIGNAL_VALUES.get(signal, 0.0)

    def _value_to_signal(self, value: float) -> str:
        """
        Convert numeric value to signal string.

        Args:
            value (float): Numeric value from weighted averaging

        Returns:
            str: Signal string (BUY, SELL, or HOLD)
        """
        # Threshold-based conversion
        # Positive values above 0.3 -> BUY
        # Negative values below -0.3 -> SELL
        # Values in between -> HOLD
        if value > 0.3:
            return "BUY"
        elif value < -0.3:
            return "SELL"
        else:
            return "HOLD"

    def calibrate(self, historical_results: List[Dict]) -> Dict:
        """
        Calibrate weights based on historical performance.

        Analyzes past predictions and actual outcomes to learn
        optimal agent weights.

        Args:
            historical_results (List[Dict]): List of past predictions with outcomes.
                Each dict should contain:
                    - 'agent_signals': Dict mapping agent_name to signal
                    - 'actual_return': Actual return after prediction period

        Returns:
            Dict: Calibration results including status and learned weights
        """
        # Check minimum data requirement for calibration
        # len(): Get length of list
        if len(historical_results) < 10:
            return {"status": "Insufficient data for calibration", "using": "default_weights"}

        try:
            # Create defaultdict to track per-agent accuracy statistics
            # lambda: Factory function returning dict with 'correct' and 'total' keys
            # Reference: https://docs.python.org/3/library/collections.html#collections.defaultdict
            agent_accuracy = defaultdict(lambda: {"correct": 0, "total": 0})

            # Iterate through historical results to calculate accuracy
            # for loop: Iterate over list elements
            for result in historical_results:
                # Extract agent signals and actual return from result dict
                # dict.get(key, default): Safe access with default
                agent_signals = result.get('agent_signals', {})
                actual_return = result.get('actual_return', 0)

                # Determine what the correct signal should have been
                # Based on actual return thresholds (2%)
                if actual_return > 0.02:
                    correct_signal = "BUY"
                elif actual_return < -0.02:
                    correct_signal = "SELL"
                else:
                    correct_signal = "HOLD"

                # Check each agent's prediction against correct signal
                # dict.items(): Get key-value pairs
                # Reference: https://docs.python.org/3/library/stdtypes.html#dict.items
                for agent, signal in agent_signals.items():
                    # Normalize agent name (remove 'agent' suffix, lowercase)
                    # str.lower(): Convert to lowercase
                    # str.replace(): Replace substring
                    # str.strip(): Remove whitespace
                    agent_key = agent.lower().replace('agent', '').strip()

                    # Increment total predictions count
                    agent_accuracy[agent_key]["total"] += 1

                    # Normalize signal string, handle non-string types
                    # isinstance(): Check type
                    # Reference: https://docs.python.org/3/library/functions.html#isinstance
                    signal_upper = signal.upper() if isinstance(signal, str) else "HOLD"

                    # Check if agent prediction was correct
                    # 'in' operator: Check membership in list
                    if signal_upper in ["BUY", "BULLISH"] and correct_signal == "BUY":
                        agent_accuracy[agent_key]["correct"] += 1
                    elif signal_upper in ["SELL", "BEARISH"] and correct_signal == "SELL":
                        agent_accuracy[agent_key]["correct"] += 1
                    elif signal_upper in ["HOLD", "NEUTRAL"] and correct_signal == "HOLD":
                        agent_accuracy[agent_key]["correct"] += 1

            # ── Calculate New Weights Based on Accuracy ────────────────
            # Empty dict to store new weights
            new_weights = {}
            total_accuracy = 0

            # Calculate accuracy for each agent
            for agent, stats in agent_accuracy.items():
                if stats["total"] > 0:
                    # Accuracy = correct predictions / total predictions
                    accuracy = stats["correct"] / stats["total"]
                    new_weights[agent] = accuracy
                    total_accuracy += accuracy

            # Normalize weights to sum to 1.0
            if total_accuracy > 0:
                for agent in new_weights:
                    new_weights[agent] /= total_accuracy

            # ── Blend Learned and Default Weights ──────────────────────
            # Use 70% learned weights + 30% default weights for stability
            for agent in self.weights:
                if agent in new_weights:
                    # Weighted average of learned and default weights
                    self.weights[agent] = 0.7 * new_weights[agent] + 0.3 * self.DEFAULT_WEIGHTS.get(agent, 0.05)

            # ── Normalize Final Weights ────────────────────────────────
            # Ensure weights sum to 1.0
            # sum(): Sum all values
            # Reference: https://docs.python.org/3/library/functions.html#sum
            # dict.values(): Get all values
            weight_sum = sum(self.weights.values())
            if weight_sum > 0:
                # Dict comprehension: Create new dict with normalized values
                # Reference: https://docs.python.org/3/tutorial/datastructures.html#dictionaries
                self.weights = {k: v / weight_sum for k, v in self.weights.items()}

            # Mark as calibrated
            self.is_calibrated = True

            # Return calibration results
            # sorted(): Sort items
            # key=lambda x: x[1]: Sort by value (descending)
            # [:10]: Get top 10 weights
            return {
                "status": "success",
                "samples_used": len(historical_results),
                "calibrated_weights": {k: round(v, 4) for k, v in
                                       sorted(self.weights.items(), key=lambda x: x[1], reverse=True)[:10]}
            }

        except Exception as e:
            # Return error and continue using default weights
            # str(e): Convert exception to string
            return {"error": str(e), "using": "default_weights"}

    def score(self, agent_results: Dict) -> Dict:
        """
        Score and combine signals from multiple agents.

        Computes weighted average of agent signals and produces
        ensemble prediction with confidence.

        Args:
            agent_results (Dict): Mapping of agent_name to result dict.
                Each result should contain:
                    - 'signal': Signal string (BUY/SELL/HOLD)
                    - 'confidence': Float confidence score (0-1)

        Returns:
            Dict: Ensemble prediction with:
                - ensemble_signal: Final combined signal
                - ensemble_confidence: Confidence score
                - ensemble_score: Raw weighted score
                - signal_distribution: Count of each signal type
                - agent_contributions: Per-agent contribution details
        """
        # Handle empty input
        if not agent_results:
            return {
                "ensemble_signal": "HOLD",
                "ensemble_confidence": 0.5,
                "ensemble_score": 0.0,
                "agent_contributions": {},
                "signal_distribution": {"BUY": 0, "HOLD": 0, "SELL": 0}
            }

        # ── Initialize Accumulators ────────────────────────────────────
        # float type: Running sum of weighted signal values
        weighted_sum = 0.0

        # float type: Running sum of weights used
        total_weight = 0.0

        # dict type: Per-agent contribution details
        agent_contributions = {}

        # dict type: Count signals of each type
        signal_counts = {"BUY": 0, "HOLD": 0, "SELL": 0}

        # float type: Sum of confidence-weighted values
        confidence_weighted_sum = 0.0

        # ── Process Each Agent Result ──────────────────────────────────
        # dict.items(): Get key-value pairs for iteration
        for agent_name, result in agent_results.items():
            # Normalize agent name for weight lookup
            # Chain of str methods: lowercase, remove suffixes, strip whitespace
            agent_key = agent_name.lower().replace('agent', '').replace('analysis', '').strip()
            agent_key = agent_key.replace('_', '').replace('-', '')

            # ── Find Matching Weight ───────────────────────────────────
            # Default weight if no match found
            weight = 0.05

            # Search for matching weight key
            for key in self.weights:
                # 'in' operator: Substring check
                if key in agent_key or agent_key in key:
                    weight = self.weights[key]
                    break  # Use first match

            # ── Extract Signal and Confidence ──────────────────────────
            # dict.get(): Safe access with default
            signal = result.get('signal', 'HOLD')
            confidence = result.get('confidence', 0.5)

            # Handle string confidence values
            # isinstance(): Type check
            if isinstance(confidence, str):
                try:
                    # float(): Convert string to float
                    confidence = float(confidence)
                except:
                    # Default to 0.5 on conversion failure
                    confidence = 0.5

            # ── Calculate Contribution ─────────────────────────────────
            # Convert signal to numeric value
            signal_value = self._signal_to_value(signal)

            # Effective weight combines agent weight and confidence
            effective_weight = weight * confidence

            # Add to weighted sum
            weighted_sum += signal_value * effective_weight
            total_weight += effective_weight
            confidence_weighted_sum += confidence * weight

            # ── Track Agent Contribution ───────────────────────────────
            # Store per-agent details
            # round(): Round to specified decimal places
            agent_contributions[agent_name] = {
                "signal": signal,
                "confidence": round(confidence, 3),
                "weight": round(weight, 4),
                "contribution": round(signal_value * effective_weight, 4)
            }

            # ── Count Signal Types ─────────────────────────────────────
            # Normalize signal for counting
            signal_upper = signal.upper() if signal else "HOLD"
            if signal_upper in ["BUY", "BULLISH"]:
                signal_counts["BUY"] += 1
            elif signal_upper in ["SELL", "BEARISH"]:
                signal_counts["SELL"] += 1
            else:
                signal_counts["HOLD"] += 1

        # ── Calculate Ensemble Score ───────────────────────────────────
        # Weighted average of signal values
        if total_weight > 0:
            ensemble_score = weighted_sum / total_weight
        else:
            ensemble_score = 0.0

        # Convert numeric score to signal
        ensemble_signal = self._value_to_signal(ensemble_score)

        # ── Calculate Ensemble Confidence ──────────────────────────────
        # Get total number of agents
        # len(): Get count
        total_agents = len(agent_results)

        # Calculate agreement ratio (how many agents agree with ensemble)
        # dict access: signal_counts[ensemble_signal] gets count for winning signal
        agreement_ratio = signal_counts[ensemble_signal] / total_agents if total_agents > 0 else 0

        # Calculate average confidence across agents
        avg_confidence = confidence_weighted_sum / sum(self.weights.values()) if self.weights else 0.5

        # Combine agreement and confidence (50/50 weighting)
        ensemble_confidence = 0.5 * agreement_ratio + 0.5 * avg_confidence

        # Adjust confidence based on score strength
        # abs(): Absolute value
        score_strength = abs(ensemble_score)

        # Scale confidence: base + boost from score strength
        # min(): Cap at 0.95
        ensemble_confidence = min(0.95, ensemble_confidence * (0.7 + 0.3 * score_strength))

        # ── Sort Contributions by Impact ───────────────────────────────
        # sorted(): Sort dictionary items
        # key=lambda: Sort by absolute contribution value
        # dict(): Convert back to dictionary
        sorted_contributions = dict(sorted(
            agent_contributions.items(),
            key=lambda x: abs(x[1]['contribution']),
            reverse=True  # Descending order
        ))

        # ── Build Response ─────────────────────────────────────────────
        # List comprehension to get top bullish/bearish agents
        return {
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": round(ensemble_confidence, 3),
            "ensemble_score": round(ensemble_score, 4),
            "signal_distribution": signal_counts,
            "agreement_ratio": round(agreement_ratio, 3),
            "agent_contributions": sorted_contributions,
            # Get agent names with bullish signals
            "top_bullish_agents": [name for name, data in sorted_contributions.items()
                                   if (data.get('signal') or '').upper() in ['BUY', 'BULLISH']][:5],
            # Get agent names with bearish signals
            "top_bearish_agents": [name for name, data in sorted_contributions.items()
                                   if (data.get('signal') or '').upper() in ['SELL', 'BEARISH']][:5],
            "weights_used": "calibrated" if self.is_calibrated else "default"
        }

    def get_weights(self) -> Dict[str, float]:
        """
        Get current agent weights.

        Returns:
            Dict[str, float]: Mapping of agent name to weight, sorted descending
        """
        # sorted(): Sort by value (descending)
        # dict comprehension: Round values to 4 decimal places
        return {k: round(v, 4) for k, v in
                sorted(self.weights.items(), key=lambda x: x[1], reverse=True)}

    def set_weight(self, agent: str, weight: float) -> None:
        """
        Manually set weight for a specific agent.

        Args:
            agent (str): Agent name (will be normalized)
            weight (float): Weight value (will be clamped to [0, 1])
        """
        # Normalize agent name
        agent_key = agent.lower().replace('agent', '').strip()

        # Clamp weight to valid range [0, 1]
        # max(0, min(1, weight)): Ensure value is between 0 and 1
        # Reference: https://docs.python.org/3/library/functions.html#max
        self.weights[agent_key] = max(0, min(1, weight))

        # ── Renormalize All Weights ────────────────────────────────────
        # Ensure weights sum to 1.0 after modification
        total = sum(self.weights.values())
        if total > 0:
            # Dict comprehension: Normalize each weight
            self.weights = {k: v / total for k, v in self.weights.items()}
