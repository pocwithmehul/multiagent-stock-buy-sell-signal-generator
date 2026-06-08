#!/usr/bin/env python3
"""Scheduled buy-now report runner for n8n cron jobs."""

import argparse
import json
import os
from datetime import datetime

import yfinance as yf

from agents.orchestrator_agent import OrchestratorAgent
from infrastructure.report_utils import (
    generate_buy_now_email_body,
    generate_buy_now_pdf_report,
    send_email,
)
from ml import EnsembleScorer


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_signal(signal: str) -> str:
    sig = (signal or "").upper().strip()
    if sig in ("BUY", "BULLISH"):
        return "BUY"
    if sig in ("SELL", "BEARISH"):
        return "SELL"
    return "HOLD"


def extract_market_session_data(info: dict) -> dict:
    """Extract pre-market, intraday, and after-hours quote metrics."""
    info = info or {}
    prev_close = _safe_float(info.get("regularMarketPreviousClose")) or _safe_float(info.get("previousClose"))

    pre_price = _safe_float(info.get("preMarketPrice"))
    pre_change_pct = _safe_float(info.get("preMarketChangePercent"))
    if pre_change_pct is None and pre_price is not None and prev_close:
        pre_change_pct = ((pre_price - prev_close) / prev_close) * 100

    intraday_price = _safe_float(info.get("regularMarketPrice")) or _safe_float(info.get("currentPrice"))
    intraday_change_pct = _safe_float(info.get("regularMarketChangePercent"))
    if intraday_change_pct is None and intraday_price is not None and prev_close:
        intraday_change_pct = ((intraday_price - prev_close) / prev_close) * 100

    after_price = _safe_float(info.get("postMarketPrice"))
    after_change_pct = _safe_float(info.get("postMarketChangePercent"))
    if after_change_pct is None and after_price is not None and intraday_price:
        after_change_pct = ((after_price - intraday_price) / intraday_price) * 100

    return {
        "pre_market_price": pre_price,
        "pre_market_change_pct": pre_change_pct,
        "intraday_price": intraday_price,
        "intraday_change_pct": intraday_change_pct,
        "after_hours_price": after_price,
        "after_hours_change_pct": after_change_pct,
        "prev_close": prev_close,
    }


def calculate_buy_now_score(result: dict, session_data: dict, current_session: str) -> float:
    """Calculate buy-now score with higher weight for active scheduled session."""
    signal = _normalize_signal(result.get("reconciled_signal") or result.get("signal"))
    confidence = float(result.get("reconciled_confidence") or result.get("confidence") or 0.0)
    upside = float(result.get("potential_upside_pct") or 0.0)

    signal_component = {"BUY": 35.0, "HOLD": 5.0, "SELL": -30.0}.get(signal, 0.0)
    confidence_component = min(max(confidence, 0.0), 1.0) * 50.0

    session_weights = {
        "pre_market": (0.65, 0.25, 0.10),
        "intraday": (0.20, 0.65, 0.15),
        "after_hours": (0.15, 0.25, 0.60),
    }
    pre_w, intra_w, after_w = session_weights.get(current_session, (0.20, 0.60, 0.20))

    momentum_values = [
        (session_data.get("pre_market_change_pct"), pre_w),
        (session_data.get("intraday_change_pct"), intra_w),
        (session_data.get("after_hours_change_pct"), after_w),
    ]
    weighted_sum = 0.0
    weight_total = 0.0
    for value, weight in momentum_values:
        if value is not None:
            weighted_sum += float(value) * weight
            weight_total += weight
    avg_momentum = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    momentum_component = max(min(avg_momentum * 2.0, 15.0), -15.0)

    upside_component = max(min(upside * 0.5, 15.0), 0.0)
    return round(signal_component + confidence_component + momentum_component + upside_component, 2)


def reconcile_signal_decision(result: dict, ensemble_result: dict | None = None) -> dict:
    """Reconcile orchestrator signal with ML ensemble signal."""
    primary_signal = _normalize_signal(result.get("signal"))
    primary_conf = float(result.get("confidence") or 0.0)

    if not ensemble_result:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": primary_conf,
            "decision_source": "primary",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": None,
            "ensemble_confidence": None,
        }

    ensemble_signal = _normalize_signal(ensemble_result.get("ensemble_signal"))
    ensemble_conf = float(ensemble_result.get("ensemble_confidence") or 0.0)

    if primary_signal == ensemble_signal:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": max(primary_conf, ensemble_conf),
            "decision_source": "aligned",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }

    edge = 0.20
    if ensemble_conf >= primary_conf + edge:
        return {
            "reconciled_signal": ensemble_signal,
            "reconciled_confidence": ensemble_conf,
            "decision_source": "ensemble_override",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }
    if primary_conf >= ensemble_conf + edge:
        return {
            "reconciled_signal": primary_signal,
            "reconciled_confidence": primary_conf,
            "decision_source": "primary_override",
            "primary_signal": primary_signal,
            "primary_confidence": primary_conf,
            "ensemble_signal": ensemble_signal,
            "ensemble_confidence": ensemble_conf,
        }

    return {
        "reconciled_signal": "HOLD",
        "reconciled_confidence": max(0.55, (primary_conf + ensemble_conf) / 2),
        "decision_source": "tie_break_hold",
        "primary_signal": primary_signal,
        "primary_confidence": primary_conf,
        "ensemble_signal": ensemble_signal,
        "ensemble_confidence": ensemble_conf,
    }


def run_ticker_analysis(ticker: str, days: int, model: str, api_base: str | None) -> dict:
    """
    Run full recommendation pipeline:
    1) 47-agent orchestrator
    2) ML ensemble scoring
    3) reconciliation
    """
    orchestrator = OrchestratorAgent(
        ticker=ticker,
        past_days=days,
        model=model,
        api_base=api_base,
        verbose=False,
    )
    orchestrator.execute()
    result = orchestrator.get_signal() or {}

    agent_details = result.get("agent_details") or {}
    ensemble_result = None
    if agent_details:
        try:
            scorer = EnsembleScorer()
            ensemble_result = scorer.score(agent_details)
        except Exception as exc:
            print(f"[WARN] ML ensemble scoring failed for {ticker}: {exc}")

    decision = reconcile_signal_decision(result, ensemble_result)
    result.update(decision)
    result["ensemble_result"] = ensemble_result
    return result


def rank_watchlist(
    watchlist: list[str],
    days: int,
    model: str,
    session: str,
    api_base: str | None,
) -> list[dict]:
    """Build ranked watchlist candidates."""
    ranked = []
    for ticker in watchlist:
        tk = ticker.upper().strip()
        if not tk:
            continue
        try:
            result = run_ticker_analysis(tk, days=days, model=model, api_base=api_base)
            quote_info = yf.Ticker(tk).info or {}
            session_data = extract_market_session_data(quote_info)
            buy_now_score = calculate_buy_now_score(result, session_data, session)
            ranked.append(
                {
                    "ticker": tk,
                    "company_name": quote_info.get("shortName", tk),
                    "signal": _normalize_signal(result.get("reconciled_signal") or result.get("signal")),
                    "confidence": float(result.get("reconciled_confidence") or result.get("confidence") or 0.0),
                    "buy_now_score": buy_now_score,
                    "target_price": result.get("target_price"),
                    "potential_upside_pct": result.get("potential_upside_pct"),
                    "session_data": session_data,
                }
            )
        except Exception as exc:
            print(f"[WARN] Skipping {tk}: {exc}")

    ranked.sort(key=lambda x: x.get("buy_now_score", 0.0), reverse=True)
    return ranked


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scheduled buy-now stock ranking report.")
    parser.add_argument("--session", choices=["pre_market", "intraday", "after_hours"], required=True)
    parser.add_argument("--watchlist", default=os.getenv("BUY_NOW_WATCHLIST", "AAPL,MSFT,GOOGL,NVDA,META"))
    parser.add_argument("--days", type=int, default=int(os.getenv("BUY_NOW_DAYS", "90")))
    parser.add_argument("--model", default=os.getenv("BUY_NOW_MODEL", "gpt-4o-mini"))
    parser.add_argument("--api-base", default=os.getenv("BUY_NOW_API_BASE"))
    parser.add_argument("--top-n", type=int, default=int(os.getenv("BUY_NOW_TOP_N", "10")))
    parser.add_argument("--email", default=os.getenv("BUY_NOW_REPORT_EMAIL"))
    parser.add_argument("--save-pdf", action="store_true", default=True)
    parser.add_argument("--output-dir", default=os.getenv("BUY_NOW_OUTPUT_DIR", "reports"))
    return parser.parse_args()


def main():
    args = parse_args()
    watchlist = [w.strip().upper() for w in args.watchlist.split(",") if w.strip()]
    if not watchlist:
        raise ValueError("No valid watchlist symbols provided")

    ranked = rank_watchlist(
        watchlist=watchlist,
        days=args.days,
        model=args.model,
        session=args.session,
        api_base=args.api_base,
    )[: args.top_n]

    title = f"Best Stocks to Buy Now ({args.session.replace('_', ' ').title()} Run)"
    pdf_bytes = generate_buy_now_pdf_report(ranked_stocks=ranked, title=title)
    email_body = generate_buy_now_email_body(ranked_stocks=ranked, title=title)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.save_pdf:
        os.makedirs(args.output_dir, exist_ok=True)
        pdf_path = os.path.join(args.output_dir, f"buy_now_{args.session}_{timestamp}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"[INFO] Saved PDF: {pdf_path}")

    if args.email:
        success, message = send_email(
            to_email=args.email,
            subject=title,
            body=email_body,
            pdf_attachment=pdf_bytes,
            pdf_filename=f"buy_now_{args.session}_{timestamp}.pdf",
        )
        if success:
            print(f"[INFO] {message}")
        else:
            print(f"[ERROR] {message}")
    else:
        print("[INFO] BUY_NOW_REPORT_EMAIL not set; skipping email send.")

    print(json.dumps({"session": args.session, "count": len(ranked), "top": ranked[:3]}, default=str))


if __name__ == "__main__":
    main()
