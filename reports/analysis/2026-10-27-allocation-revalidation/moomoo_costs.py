"""Illustrative fee arithmetic, not a historical or fill-calibrated cost model."""

from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path

D = Decimal
SOURCE = "https://www.moomoo.com/my/support/topic9_136?from_platform=4&lang=en-us&platform_langArea=my"


def example(notional, side):
    amount = D(notional)
    # Deliberately synthetic price and FX: neither is a current market quote.
    price, fx = D(100), D(4)
    shares = amount / price
    commission = (amount * D("0.0003")).quantize(D("0.01"), rounding=ROUND_CEILING)
    stamp = min((amount * fx / 1000).to_integral_value(rounding=ROUND_CEILING), D(1000)) / fx
    fees = {
        "commission": commission, "platform": D("0.99"), "stamp_duty": stamp,
        "settlement": min(shares * D("0.003"), amount * D("0.01")),
        "sec": max(amount * D("0.0000206"), D("0.01")) if side == "sell" else D(0),
        "taf": min(max(shares * D("0.000195"), D("0.01")), D("9.79")) if side == "sell" else D(0),
        "cat_as_listed_by_broker": shares * D("0.000003"),
    }
    total = sum(fees.values())
    return {"notional_usd": notional, "side": side,
            "components_usd": {k: float(v) for k, v in fees.items()},
            "subtotal_usd": float(total), "subtotal_bps": float(total / amount * 10000)}


if __name__ == "__main__":
    result = {
        "broker": "Moomoo Securities Malaysia", "market": "US ordinary shares",
        "source": SOURCE, "review_date": "2026-10-27",
        "retrieval": "Official support search extraction; direct page returned JS/403. Effective-date history not reconstructed.",
        "status": "published_tariff_identified_execution_calibration_incomplete",
        "assumptions": {
            "share_price_usd": 100, "usd_myr": 4,
            "price_and_fx_are_illustrative_not_observed": True,
            "single_order_single_fill_same_day": True,
            "promotion": "standard commission; no introductory waiver",
            "rounding": "Commission rounded up to cents; stamp up to MYR1; other component precision retained, actual rounding unverified",
        },
        "excluded_unresolved": ["spread_and_slippage", "currency_conversion_cost",
                                "SST_applicability", "ADR_charges", "dividend_tax",
                                "historical_tariff_changes", "multi_fill_rounding"],
        "actual_order_notional_usd": None, "calibrated_bps_per_side": None,
        "promotion_ready": False,
        "examples": [example(n, side) for n in (100, 500, 1000, 5000) for side in ("buy", "sell")],
    }
    Path(__file__).with_name("moomoo-cost-evidence.json").write_text(json.dumps(result, indent=2) + "\n")
    for row in result["examples"]:
        print(f"${row['notional_usd']:5} {row['side']:4}: {row['subtotal_bps']:.2f} bps tariff subtotal")
