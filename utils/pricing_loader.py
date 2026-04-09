# utils/pricing_loader.py

import json
from pathlib import Path
from typing import Dict, List


class PricingLoader:
    """
    Loads and validates pricing funnel JSON input files.
    Computes derived values (subtotals, fee totals, deltas)
    that are passed to the pricing agent as structured context.
    """

    VALID_STAGES  = ["product_page", "cart", "checkout", "payment"]
    STAGE_ORDER   = ["product_page", "cart", "checkout", "payment"]

    def load(self, file_path: str) -> dict:
        """Load and validate a pricing JSON input file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")
        if path.suffix.lower() != ".json":
            raise ValueError(f"Expected .json file, got: {path.suffix}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._validate(data)
        return data

    def _validate(self, data: dict):
        """Basic schema validation."""
        required_top = ["funnel_stages"]
        for field in required_top:
            if field not in data:
                raise ValueError(f"Missing required field: '{field}'")

        if not isinstance(data["funnel_stages"], list) or len(data["funnel_stages"]) < 2:
            raise ValueError("funnel_stages must be a list with at least 2 stages")

        for stage in data["funnel_stages"]:
            if "stage" not in stage:
                raise ValueError("Each funnel stage must have a 'stage' field")
            if stage["stage"] not in self.VALID_STAGES:
                raise ValueError(
                    f"Invalid stage '{stage['stage']}'. "
                    f"Must be one of: {self.VALID_STAGES}"
                )
            if "items" not in stage or not isinstance(stage["items"], list):
                raise ValueError(f"Stage '{stage['stage']}' must have an 'items' list")

    def compute_analysis_context(self, data: dict) -> dict:
        """
        Pre-compute all derived values so the agent has
        structured numbers to reason about directly.
        """
        stages     = {s["stage"]: s for s in data["funnel_stages"]}
        stage_list = [
            s for s in self.STAGE_ORDER if s in stages
        ]

        # ── Per-stage computations ─────────────────────────────────────────
        stage_summaries = {}
        for stage_name in stage_list:
            stage = stages[stage_name]
            item_subtotal  = sum(
                i.get("price", 0) * i.get("quantity", 1)
                for i in stage.get("items", [])
            )
            fees_total = sum(
                f.get("amount", 0)
                for f in stage.get("fees_shown", [])
            )
            stage_summaries[stage_name] = {
                "item_subtotal":   round(item_subtotal, 2),
                "fees_total":      round(fees_total, 2),
                "displayed_total": stage.get("displayed_total", item_subtotal + fees_total),
                "fee_names":       [f["name"] for f in stage.get("fees_shown", [])],
                "fee_breakdown":   stage.get("fees_shown", []),
                "items":           stage.get("items", []),
            }

        # ── Cross-stage comparisons ────────────────────────────────────────
        first_stage = stage_list[0]
        last_stage  = stage_list[-1]

        first_subtotal = stage_summaries[first_stage]["item_subtotal"]
        last_subtotal  = stage_summaries[last_stage]["item_subtotal"]
        last_total     = stage_summaries[last_stage]["displayed_total"]
        last_fees      = stage_summaries[last_stage]["fees_total"]

        # Item price delta (Bait & Switch signal)
        item_price_delta    = round(last_subtotal - first_subtotal, 2)
        item_price_delta_pct = (
            round((item_price_delta / first_subtotal) * 100, 2)
            if first_subtotal > 0 else 0.0
        )

        # Fee injection (Drip Pricing signal)
        first_fee_names = set(stage_summaries[first_stage]["fee_names"])
        last_fee_names  = set(stage_summaries[last_stage]["fee_names"])
        injected_fees   = last_fee_names - first_fee_names

        injected_fee_total = sum(
            f["amount"]
            for f in stage_summaries[last_stage]["fee_breakdown"]
            if f["name"] in injected_fees
        )
        injected_fee_pct = (
            round((injected_fee_total / first_subtotal) * 100, 2)
            if first_subtotal > 0 else 0.0
        )

        # Stage-by-stage total progression
        total_progression = [
            {
                "stage":           s,
                "item_subtotal":   stage_summaries[s]["item_subtotal"],
                "fees_total":      stage_summaries[s]["fees_total"],
                "displayed_total": stage_summaries[s]["displayed_total"],
            }
            for s in stage_list
        ]

        return {
            "platform":             data.get("platform", "unknown"),
            "session_id":           data.get("session_id", ""),
            "stages_present":       stage_list,
            "first_stage":          first_stage,
            "last_stage":           last_stage,
            "stage_summaries":      stage_summaries,
            "total_progression":    total_progression,

            # Bait & Switch signals
            "item_price_delta":     item_price_delta,
            "item_price_delta_pct": item_price_delta_pct,
            "bait_switch_threshold_pct": 5.0,
            "bait_switch_triggered": abs(item_price_delta_pct) > 5.0,

            # Drip Pricing signals
            "injected_fee_names":   list(injected_fees),
            "injected_fee_total":   round(injected_fee_total, 2),
            "injected_fee_pct":     injected_fee_pct,
            "drip_threshold_pct":   10.0,
            "drip_severity": (
                "high"   if injected_fee_pct > 10.0 else
                "medium" if injected_fee_pct > 5.0  else
                "low"    if injected_fee_pct > 0    else
                "none"
            ),
            "drip_triggered": injected_fee_pct > 0,

            # Overall
            "total_increase_amount": round(last_total - first_subtotal, 2),
            "total_increase_pct":    round(
                ((last_total - first_subtotal) / first_subtotal * 100), 2
            ) if first_subtotal > 0 else 0.0,
        }