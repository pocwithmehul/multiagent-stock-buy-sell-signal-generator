"""
Neuro-Symbolic Validator for trading signals.

Applies hard symbolic rules on top of neural ensemble output to enforce
domain constraints that the LLM/ensemble cannot guarantee on its own.

Rule structure:
  Each rule is a function that receives a context dict and returns a
  RuleResult (triggered, action, reason).  Rules are evaluated in order;
  later rules can override earlier ones.

Actions:
  "override_hold"   – force signal to HOLD
  "cap_confidence"  – reduce confidence to at most the rule's cap value
  "reduce_confidence" – multiply confidence by a penalty factor
  (no action / None) – rule triggered for logging only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    triggered: bool
    rule_name: str
    reason: str = ""
    action: Optional[str] = None       # "override_hold" | "cap_confidence" | "reduce_confidence"
    value: Optional[float] = None      # cap value or penalty factor


@dataclass
class ValidationResult:
    signal: str
    confidence: float
    rules_triggered: list[str] = field(default_factory=list)
    overridden: bool = False
    adjustments: list[str] = field(default_factory=list)


# ── Individual rules ──────────────────────────────────────────────────────────

def _rule_extreme_rsi_overbought(ctx: dict) -> RuleResult:
    """RSI > 85: market is extremely overbought — override BUY to HOLD."""
    rsi = ctx.get("rsi")
    if rsi is not None and rsi > 85 and ctx["signal"] == "BUY":
        return RuleResult(
            triggered=True,
            rule_name="extreme_rsi_overbought",
            reason=f"RSI={rsi:.1f} > 85: extremely overbought, overriding BUY → HOLD",
            action="override_hold",
        )
    return RuleResult(triggered=False, rule_name="extreme_rsi_overbought")


def _rule_extreme_rsi_oversold(ctx: dict) -> RuleResult:
    """RSI < 15: market is extremely oversold — override SELL to HOLD."""
    rsi = ctx.get("rsi")
    if rsi is not None and rsi < 15 and ctx["signal"] == "SELL":
        return RuleResult(
            triggered=True,
            rule_name="extreme_rsi_oversold",
            reason=f"RSI={rsi:.1f} < 15: extremely oversold, overriding SELL → HOLD",
            action="override_hold",
        )
    return RuleResult(triggered=False, rule_name="extreme_rsi_oversold")


def _rule_rsi_overbought_cap(ctx: dict) -> RuleResult:
    """RSI > 70: overbought — cap BUY confidence at 0.55."""
    rsi = ctx.get("rsi")
    if rsi is not None and rsi > 70 and ctx["signal"] == "BUY":
        return RuleResult(
            triggered=True,
            rule_name="rsi_overbought_cap",
            reason=f"RSI={rsi:.1f} > 70: overbought, capping BUY confidence at 0.55",
            action="cap_confidence",
            value=0.55,
        )
    return RuleResult(triggered=False, rule_name="rsi_overbought_cap")


def _rule_rsi_oversold_cap(ctx: dict) -> RuleResult:
    """RSI < 30: oversold — cap SELL confidence at 0.55."""
    rsi = ctx.get("rsi")
    if rsi is not None and rsi < 30 and ctx["signal"] == "SELL":
        return RuleResult(
            triggered=True,
            rule_name="rsi_oversold_cap",
            reason=f"RSI={rsi:.1f} < 30: oversold, capping SELL confidence at 0.55",
            action="cap_confidence",
            value=0.55,
        )
    return RuleResult(triggered=False, rule_name="rsi_oversold_cap")


def _rule_macd_divergence(ctx: dict) -> RuleResult:
    """
    Signal diverges from MACD histogram direction — reduce confidence by 20%.

    BUY signal but MACD histogram strongly negative (< -0.5): bearish momentum
    SELL signal but MACD histogram strongly positive (> 0.5): bullish momentum
    """
    histogram = ctx.get("macd_histogram")
    signal = ctx["signal"]
    if histogram is None:
        return RuleResult(triggered=False, rule_name="macd_divergence")

    if signal == "BUY" and histogram < -0.5:
        return RuleResult(
            triggered=True,
            rule_name="macd_divergence",
            reason=f"MACD histogram={histogram:.3f} < -0.5: bearish momentum conflicts with BUY signal",
            action="reduce_confidence",
            value=0.80,
        )
    if signal == "SELL" and histogram > 0.5:
        return RuleResult(
            triggered=True,
            rule_name="macd_divergence",
            reason=f"MACD histogram={histogram:.3f} > 0.5: bullish momentum conflicts with SELL signal",
            action="reduce_confidence",
            value=0.80,
        )
    return RuleResult(triggered=False, rule_name="macd_divergence")


def _rule_price_below_sma200(ctx: dict) -> RuleResult:
    """Price is more than 20% below SMA-200 — cap BUY confidence at 0.50 (distressed asset)."""
    price = ctx.get("current_price")
    sma200 = ctx.get("sma_200")
    if price and sma200 and ctx["signal"] == "BUY":
        pct_below = (sma200 - price) / sma200
        if pct_below > 0.20:
            return RuleResult(
                triggered=True,
                rule_name="price_below_sma200",
                reason=f"Price {price:.2f} is {pct_below*100:.1f}% below SMA-200 ({sma200:.2f}): distressed asset, capping BUY confidence at 0.50",
                action="cap_confidence",
                value=0.50,
            )
    return RuleResult(triggered=False, rule_name="price_below_sma200")


def _rule_price_above_upper_bollinger(ctx: dict) -> RuleResult:
    """Price above upper Bollinger Band — reduce BUY confidence by 15%."""
    price = ctx.get("current_price")
    bb_upper = ctx.get("bollinger_upper")
    if price and bb_upper and ctx["signal"] == "BUY" and price > bb_upper:
        return RuleResult(
            triggered=True,
            rule_name="price_above_upper_bollinger",
            reason=f"Price {price:.2f} above upper Bollinger Band {bb_upper:.2f}: overextended, reducing BUY confidence",
            action="reduce_confidence",
            value=0.85,
        )
    return RuleResult(triggered=False, rule_name="price_above_upper_bollinger")


def _rule_price_below_lower_bollinger(ctx: dict) -> RuleResult:
    """Price below lower Bollinger Band — reduce SELL confidence by 15%."""
    price = ctx.get("current_price")
    bb_lower = ctx.get("bollinger_lower")
    if price and bb_lower and ctx["signal"] == "SELL" and price < bb_lower:
        return RuleResult(
            triggered=True,
            rule_name="price_below_lower_bollinger",
            reason=f"Price {price:.2f} below lower Bollinger Band {bb_lower:.2f}: oversold territory, reducing SELL confidence",
            action="reduce_confidence",
            value=0.85,
        )
    return RuleResult(triggered=False, rule_name="price_below_lower_bollinger")


def _rule_rate_sensitive_sector_buy(ctx: dict) -> RuleResult:
    """Utilities / Real Estate + BUY — reduce confidence by 15% (rate-sensitive sector)."""
    kg = ctx.get("kg_context") or {}
    if kg.get("is_rate_sensitive") and ctx["signal"] == "BUY":
        sector = kg.get("sector", "rate-sensitive sector")
        return RuleResult(
            triggered=True,
            rule_name="rate_sensitive_sector_buy",
            reason=(
                f"Sector '{sector}' is highly rate-sensitive (Utilities/Real Estate): "
                f"reducing BUY confidence by 15%"
            ),
            action="reduce_confidence",
            value=0.85,
        )
    return RuleResult(triggered=False, rule_name="rate_sensitive_sector_buy")


def _rule_cyclical_sector_sell(ctx: dict) -> RuleResult:
    """Consumer Discretionary / Materials + SELL — reduce confidence by 10% (cyclical amplification)."""
    kg = ctx.get("kg_context") or {}
    if kg.get("is_cyclical") and ctx["signal"] == "SELL":
        sector = kg.get("sector", "cyclical sector")
        return RuleResult(
            triggered=True,
            rule_name="cyclical_sector_sell",
            reason=(
                f"Sector '{sector}' is cyclical (Consumer Discretionary/Materials): "
                f"reducing SELL confidence by 10% to temper cycle-driven over-conviction"
            ),
            action="reduce_confidence",
            value=0.90,
        )
    return RuleResult(triggered=False, rule_name="cyclical_sector_sell")


def _rule_low_confidence_floor(ctx: dict) -> RuleResult:
    """Confidence below 0.35 after adjustments — downgrade to HOLD."""
    if ctx["confidence"] < 0.35 and ctx["signal"] != "HOLD":
        return RuleResult(
            triggered=True,
            rule_name="low_confidence_floor",
            reason=f"Confidence {ctx['confidence']:.3f} < 0.35: insufficient conviction, overriding to HOLD",
            action="override_hold",
        )
    return RuleResult(triggered=False, rule_name="low_confidence_floor")


# ── Rule registry (ordered — override rules run last) ─────────────────────────

_RULES = [
    # Knowledge-graph-aware rules first (cheap dict lookups, no override)
    _rule_rate_sensitive_sector_buy,
    _rule_cyclical_sector_sell,
    # Technical rules
    _rule_rsi_overbought_cap,
    _rule_rsi_oversold_cap,
    _rule_macd_divergence,
    _rule_price_below_sma200,
    _rule_price_above_upper_bollinger,
    _rule_price_below_lower_bollinger,
    # Override rules after all caps/reductions
    _rule_extreme_rsi_overbought,
    _rule_extreme_rsi_oversold,
    _rule_low_confidence_floor,     # must be last (reads accumulated confidence)
]


# ── Validator ─────────────────────────────────────────────────────────────────

class SymbolicValidator:
    """
    Applies hard symbolic rules to a neural ensemble signal.

    Usage:
        validator = SymbolicValidator()
        result = validator.validate("BUY", 0.82, technical_data)
        print(result.signal, result.confidence, result.rules_triggered)
    """

    def validate(
        self,
        signal: str,
        confidence: float,
        technical_data: dict,
        kg_context: dict = None,
    ) -> ValidationResult:
        """
        Validate and potentially adjust a signal using symbolic rules.

        Args:
            signal: Neural ensemble signal (BUY / SELL / HOLD)
            confidence: Neural ensemble confidence (0–1)
            technical_data: Dict from TechnicalAnalysisAgent output, expected keys:
                indicators: {rsi, macd, macd_signal, macd_histogram, sma_20, sma_50,
                             sma_200, ema_20, bollinger_upper, bollinger_lower}
                current_price: float
            kg_context: Optional dict from StockKnowledgeGraph.get_context(), keys:
                sector, industry, macro_sensitivities, is_rate_sensitive, is_cyclical

        Returns:
            ValidationResult with (possibly adjusted) signal and confidence,
            plus metadata about which rules fired.
        """
        signal = (signal or "HOLD").upper()
        confidence = float(confidence or 0.0)

        indicators = technical_data.get("indicators", {})

        ctx = {
            "signal": signal,
            "confidence": confidence,
            "current_price": technical_data.get("current_price"),
            "rsi": indicators.get("rsi"),
            "macd": indicators.get("macd"),
            "macd_signal": indicators.get("macd_signal"),
            "macd_histogram": indicators.get("macd_histogram"),
            "sma_20": indicators.get("sma_20"),
            "sma_50": indicators.get("sma_50"),
            "sma_200": indicators.get("sma_200"),
            "ema_20": indicators.get("ema_20"),
            "bollinger_upper": indicators.get("bollinger_upper"),
            "bollinger_lower": indicators.get("bollinger_lower"),
            "kg_context": kg_context or {},
        }

        rules_triggered = []
        adjustments = []
        overridden = False

        for rule_fn in _RULES:
            # Pass current (possibly updated) signal and confidence
            ctx["signal"] = signal
            ctx["confidence"] = confidence

            result = rule_fn(ctx)
            if not result.triggered:
                continue

            rules_triggered.append(result.rule_name)

            if result.action == "override_hold":
                signal = "HOLD"
                overridden = True
                adjustments.append(result.reason)

            elif result.action == "cap_confidence":
                if confidence > result.value:
                    confidence = result.value
                    adjustments.append(result.reason)

            elif result.action == "reduce_confidence":
                confidence = round(confidence * result.value, 4)
                adjustments.append(result.reason)

        return ValidationResult(
            signal=signal,
            confidence=round(confidence, 4),
            rules_triggered=rules_triggered,
            overridden=overridden,
            adjustments=adjustments,
        )
