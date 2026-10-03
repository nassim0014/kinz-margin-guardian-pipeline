"""Offline demo of the Margin Guardian pipeline: no Docker, no Postgres, no secrets.

Seeds a handful of synthetic KINZ-style products, simulates today's competitor
prices with the same +/-5% noise model as ``simulate_competitor_prices.py``, then
runs each product through the real ``src.margin_engine`` calculation and prints a
readable table. Any product whose margin falls below its alert threshold also gets
the human-readable alert line that would otherwise go to Slack, rendered via
``src.alert_manager.format_alert_message`` -- the pure helper documented as safe to
use without the private ``astk`` package (unlike ``send_slack_alert``, which needs
astk's ``Alert``/``SlackNotifier`` classes even just to build the alert object).

Usage:
    python scripts/demo.py
    python scripts/demo.py --seed 7 --json /tmp/demo_output.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.alert_manager import format_alert_message
from src.margin_engine import MarginResult, compute_product_margins


@dataclass(frozen=True)
class DemoProduct:
    """A synthetic catalogue entry -- no database row behind it."""
    product_id: int
    name: str
    cogs_tnd: float
    base_price_tnd: float


# Five products, deliberately including one priced to fall below the default 40%
# alert threshold (Argan Oil 100ml: COGS 19.0 against a ~25 TND street price is a
# ~24% margin) so the demo always has something real to alert on.
DEMO_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct(1, "Argan Oil 100ml", cogs_tnd=19.0, base_price_tnd=25.0),
    DemoProduct(2, "Prickly Pear Seed Oil 30ml", cogs_tnd=22.0, base_price_tnd=58.0),
    DemoProduct(3, "Black Seed Oil 100ml", cogs_tnd=9.5, base_price_tnd=22.0),
    DemoProduct(4, "Rosemary Hydrosol 200ml", cogs_tnd=6.0, base_price_tnd=18.0),
    DemoProduct(5, "Gift Coffret - Trio", cogs_tnd=28.0, base_price_tnd=79.0),
)


def simulate_competitor_prices(
    products: tuple[DemoProduct, ...], seed: int
) -> dict[int, float]:
    """Today's simulated competitor price per product, +/-5% noise.

    Mirrors ``scripts/simulate_competitor_prices.py``'s noise model so the demo's
    numbers are representative of what the real DAG would feed into the engine --
    but entirely in memory, with a fixed seed for reproducibility.
    """
    rng = np.random.default_rng(seed)
    prices = {}
    for product in products:
        noise = rng.uniform(-0.05, 0.05)
        prices[product.product_id] = round(product.base_price_tnd * (1 + noise), 3)
    return prices


def run_demo(seed: int) -> list[MarginResult]:
    """Run the full ingest -> calculate -> threshold pipeline in memory."""
    competitor_prices = simulate_competitor_prices(DEMO_PRODUCTS, seed)
    return [
        compute_product_margins(
            product_id=product.product_id,
            product_name=product.name,
            cogs=product.cogs_tnd,
            competitor_price=competitor_prices[product.product_id],
        )
        for product in DEMO_PRODUCTS
    ]


def render_table(results: list[MarginResult]) -> str:
    headers = (
        "Product", "COGS", "Competitor", "B2C Price", "B2B Price",
        "B2C Margin", "B2B Margin", "Alert",
    )
    rows = []
    for r in results:
        alert = "ALERT" if (r.b2c_alert or r.b2b_alert) else "ok"
        rows.append((
            r.product_name,
            f"{r.cogs_tnd:.3f}",
            f"{r.competitor_price_tnd:.3f}",
            f"{r.b2c_price_tnd:.3f}",
            f"{r.b2b_price_tnd:.3f}",
            f"{r.b2c_margin_pct:.2f}%",
            f"{r.b2b_margin_pct:.2f}%",
            alert,
        ))
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    lines = []
    lines.append("  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)))
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)))
    return "\n".join(lines)


def render_alert_lines(results: list[MarginResult]) -> list[str]:
    lines = []
    for r in results:
        if r.b2c_alert:
            lines.append(format_alert_message(r.product_name, "B2C", r.b2c_margin_pct, r.threshold_pct))
        if r.b2b_alert:
            lines.append(format_alert_message(r.product_name, "B2B", r.b2b_margin_pct, r.threshold_pct))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for simulated competitor prices.")
    parser.add_argument("--json", type=Path, default=None, help="Also write results as JSON to this path.")
    args = parser.parse_args(argv)

    results = run_demo(args.seed)

    print(render_table(results))

    alert_lines = render_alert_lines(results)
    if alert_lines:
        print("\nAlerts (would be sent to Slack if a webhook were configured):")
        for line in alert_lines:
            print(f"  - {line}")

    if args.json:
        args.json.write_text(json.dumps([asdict(r) for r in results], indent=2))
        print(f"\nWrote {len(results)} product results to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
