# agents/pricing_agent.py

import json
import importlib
import re
import time
from typing import Dict, List
from config import get_settings
from agents.pricing_pattern_definitions import PRICING_PATTERN_DEFINITIONS
from utils.pricing_loader import PricingLoader

settings = get_settings()

genai = None
client = None
GOOGLE_GENAI_PACKAGE = None

try:
    genai_module = importlib.import_module("google.genai")
    client = genai_module.Client(api_key=settings.google_api_key)
    genai = genai_module
    GOOGLE_GENAI_PACKAGE = "genai"
except ImportError:
    try:
        genai_module = importlib.import_module("google.generativeai")
        genai_module.configure(api_key=settings.google_api_key)
        client = genai_module
        genai = genai_module
        GOOGLE_GENAI_PACKAGE = "generativeai"
    except ImportError as exc:
        raise ImportError(
            "Missing Google GenAI client library. Install it with: pip install google-generativeai"
        ) from exc


def _get_content_types():
    if GOOGLE_GENAI_PACKAGE == "generativeai":
        try:
            module = importlib.import_module("google.generativeai.types")
        except ImportError:
            module = importlib.import_module("google.generativeai")
        return getattr(module, "content_types")

    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


def _build_tool_response_message(function_responses: List[dict]):
    if GOOGLE_GENAI_PACKAGE == "generativeai":
        content_types = _get_content_types()
        return content_types.to_content({
            "role": "tool",
            "parts": function_responses,
        })

    if GOOGLE_GENAI_PACKAGE == "genai":
        types_module = importlib.import_module("google.genai.types")
        return [
            types_module.Part.from_function_response(
                name=response["function_response"]["name"],
                response=response["function_response"]["response"],
            )
            for response in function_responses
        ]

    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


def _is_quota_error(exc):
    message = str(exc).lower()
    if "quota exceeded" in message or "resource_exhausted" in message:
        return True

    try:
        exceptions_module = importlib.import_module("google.api_core.exceptions")
        return isinstance(exc, getattr(exceptions_module, "ResourceExhausted", Exception))
    except ImportError:
        return False
    except Exception:
        return False


def _extract_retry_delay_seconds(exc) -> int | None:
    message = str(exc)
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    return None


def _send_pricing_chat_message(chat, content, *, max_retries: int = 1):
    attempts = 0
    while True:
        try:
            return chat.send_message(content)
        except Exception as exc:
            attempts += 1

            if _is_quota_error(exc):
                retry_delay = _extract_retry_delay_seconds(exc)
                if retry_delay is not None and attempts <= max_retries:
                    time.sleep(retry_delay)
                    continue
                raise RuntimeError(
                    "Gemini quota exhausted for the Pricing Agent. "
                    "Wait for the retry window or switch to a cheaper/lower-traffic model."
                ) from exc

            raise


def _create_pricing_chat(*, model_name: str, tools: List[dict], system_instruction: str):
    if GOOGLE_GENAI_PACKAGE == "generativeai":
        model = genai.GenerativeModel(
            model_name=model_name,
            tools=tools,
            system_instruction=system_instruction,
        )
        return model.start_chat()

    if GOOGLE_GENAI_PACKAGE == "genai":
        if hasattr(client, "GenerativeModel"):
            model = client.GenerativeModel(
                model_name=model_name,
                tools=tools,
                system_instruction=system_instruction,
            )
            return model.start_chat()
        if hasattr(client, "chats") and hasattr(client.chats, "create"):
            config = {}
            if tools is not None:
                config["tools"] = tools
            if system_instruction is not None:
                config["system_instruction"] = system_instruction
            return client.chats.create(
                model=model_name,
                config=config,
            )
        raise RuntimeError(
            "The installed google.genai package does not expose GenerativeModel or chat creation. "
            "Install google-generativeai or upgrade google-genai to a newer version "
            "that supports the Pricing Agent API."
        )

    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


def _score_bait_switch_confidence(delta_pct: float) -> float:
    if delta_pct > 15.0:
        return 0.96
    if delta_pct > 10.0:
        return 0.88
    if delta_pct > 5.0:
        return 0.76
    return 0.0


def _score_drip_confidence(injected_fee_pct: float) -> float:
    if injected_fee_pct > 10.0:
        return 0.96
    if injected_fee_pct > 5.0:
        return 0.84
    if injected_fee_pct > 0.0:
        return 0.68
    return 0.0


def _risk_from_confidence(confidence: float) -> str:
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _build_pricing_summary(ctx: dict, detections: List[dict]) -> str:
    stages = " -> ".join(ctx["stages_present"])
    parts = [
        f"Platform {ctx['platform']} moved through {stages}."
    ]

    if ctx["bait_switch_triggered"]:
        parts.append(
            f"Item prices rose from {ctx['first_stage']} to {ctx['last_stage']} by "
            f"{ctx['item_price_delta']:.2f} ({ctx['item_price_delta_pct']:.2f}%)."
        )
    else:
        parts.append("Item prices remained stable across the funnel.")

    if ctx["drip_triggered"]:
        fee_names = ", ".join(ctx["injected_fee_names"]) if ctx["injected_fee_names"] else "hidden fees"
        parts.append(
            f"New fees appeared at {ctx['last_stage']}: {fee_names}, adding "
            f"{ctx['injected_fee_total']:.2f} ({ctx['injected_fee_pct']:.2f}% of item subtotal)."
        )
    else:
        parts.append("No late-stage fee injections were found.")

    if not detections:
        parts.append("No pricing dark patterns crossed the configured thresholds.")

    return " ".join(parts)


def _run_rule_based_pricing_analysis(ctx: dict, raw_data: dict) -> Dict:
    detections = []
    first_stage = ctx["first_stage"]
    last_stage = ctx["last_stage"]

    if ctx["bait_switch_triggered"] and ctx["item_price_delta"] > 0:
        confidence = _score_bait_switch_confidence(ctx["item_price_delta_pct"])
        detections.append({
            "pattern_id": "DP07",
            "pattern_name": "Bait and Switch",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "price_evidence": {
                "reference_price": ctx["stage_summaries"][first_stage]["item_subtotal"],
                "final_price": ctx["stage_summaries"][last_stage]["item_subtotal"],
                "difference": ctx["item_price_delta"],
                "difference_pct": ctx["item_price_delta_pct"],
                "injected_fees": [],
                "affected_stages": [first_stage, last_stage],
            },
            "explanation": (
                f"The item subtotal increased from {ctx['stage_summaries'][first_stage]['item_subtotal']:.2f} "
                f"at {first_stage} to {ctx['stage_summaries'][last_stage]['item_subtotal']:.2f} at {last_stage}, "
                f"a rise of {ctx['item_price_delta_pct']:.2f}%. That exceeds the 5% bait-and-switch threshold."
            ),
            "prevention": _default_prevention("DP07"),
        })

    if ctx["drip_triggered"] and ctx["injected_fee_total"] > 0:
        comparison_stage = last_stage if last_stage in {"checkout", "payment"} else "checkout"
        reference_stage = first_stage if first_stage in {"product_page", "cart"} else "product_page"
        fee_analysis = execute_pricing_tool(
            "detect_fee_injections",
            {"reference_stage": reference_stage, "comparison_stage": comparison_stage},
            ctx,
            raw_data,
        )
        confidence = _score_drip_confidence(ctx["injected_fee_pct"])
        detections.append({
            "pattern_id": "DP08",
            "pattern_name": "Drip Pricing",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "price_evidence": {
                "reference_price": ctx["stage_summaries"][reference_stage]["item_subtotal"],
                "final_price": ctx["stage_summaries"][comparison_stage]["displayed_total"],
                "difference": ctx["injected_fee_total"],
                "difference_pct": ctx["injected_fee_pct"],
                "injected_fees": fee_analysis.get("injected_fees", []),
                "affected_stages": [reference_stage, comparison_stage],
            },
            "explanation": (
                f"Mandatory fees were introduced at {comparison_stage} that were absent at {reference_stage}. "
                f"Those late fees total {ctx['injected_fee_total']:.2f}, which is "
                f"{ctx['injected_fee_pct']:.2f}% of the item subtotal."
            ),
            "prevention": _default_prevention("DP08"),
        })

    return {
        "detections": detections,
        "funnel_summary": _build_pricing_summary(ctx, detections),
        "total_unexplained_increase": round(
            max(ctx["item_price_delta"], 0.0) + ctx["injected_fee_total"],
            2,
        ),
        "analysis_context": ctx,
    }


# ── Tool Definitions ───────────────────────────────────────────────────────

PRICING_AGENT_TOOLS = [
    {
        "name": "get_pricing_pattern_definition",
        "description": (
            "Get the full definition, detection signals, and calculation method "
            "for a pricing dark pattern. Call this before analyzing for that pattern "
            "to understand exactly what to look for."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern_id": {
                    "type":        "string",
                    "enum":        ["DP07", "DP08"],
                    "description": "DP07 = Bait and Switch, DP08 = Drip Pricing"
                }
            },
            "required": ["pattern_id"]
        }
    },
    {
        "name": "compare_stage_prices",
        "description": (
            "Compare item prices between two specific funnel stages. "
            "Use this to check if item prices changed between stages "
            "(signals Bait and Switch). "
            "Returns the price delta and percentage change per item."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stage_a": {
                    "type":        "string",
                    "enum":        ["product_page", "cart", "checkout", "payment"],
                    "description": "The earlier / reference stage"
                },
                "stage_b": {
                    "type":        "string",
                    "enum":        ["product_page", "cart", "checkout", "payment"],
                    "description": "The later / comparison stage"
                }
            },
            "required": ["stage_a", "stage_b"]
        }
    },
    {
        "name": "detect_fee_injections",
        "description": (
            "Find fees that appear in later funnel stages but were absent "
            "in earlier stages (signals Drip Pricing). "
            "Returns list of injected fees, amounts, and the stage they first appeared."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reference_stage": {
                    "type":        "string",
                    "enum":        ["product_page", "cart"],
                    "description": "The early stage to use as baseline (usually product_page)"
                },
                "comparison_stage": {
                    "type":        "string",
                    "enum":        ["checkout", "payment"],
                    "description": "The late stage to check for new fees"
                }
            },
            "required": ["reference_stage", "comparison_stage"]
        }
    },
    {
        "name": "calculate_total_progression",
        "description": (
            "Get the complete price progression across all funnel stages. "
            "Shows how item subtotal, fees, and displayed total evolved "
            "from product page to checkout. Use this for overall analysis."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "check_threshold_violations",
        "description": (
            "Check if pricing thresholds are violated. "
            "Bait and Switch: item price increase > 5%. "
            "Drip Pricing: injected fees > 5% or > 10% of item subtotal. "
            "Returns which thresholds are violated and severity."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "finalize_pricing_detections",
        "description": (
            "Submit your final confirmed pricing dark pattern detections. "
            "Call this ONCE after all analysis is complete. "
            "Only include patterns with clear numerical evidence."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "detections": {
                    "type":  "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pattern_id":   {"type": "string"},
                            "pattern_name": {"type": "string"},
                            "confidence":   {"type": "number"},
                            "risk_level":   {
                                "type": "string",
                                "enum": ["high", "medium", "low"]
                            },
                            "price_evidence": {
                                "type": "object",
                                "description": "The numerical pricing evidence",
                                "properties": {
                                    "reference_price":  {"type": "number"},
                                    "final_price":      {"type": "number"},
                                    "difference":       {"type": "number"},
                                    "difference_pct":   {"type": "number"},
                                    "injected_fees":    {
                                        "type":  "array",
                                        "items": {"type": "object"}
                                    },
                                    "affected_stages":  {
                                        "type":  "array",
                                        "items": {"type": "string"}
                                    }
                                }
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Plain English explanation of what happened"
                            },
                            "prevention": {
                                "type": "string",
                                "description": "What the user should do"
                            }
                        },
                        "required": [
                            "pattern_id", "pattern_name",
                            "confidence", "price_evidence", "explanation"
                        ]
                    }
                },
                "funnel_summary": {
                    "type":        "string",
                    "description": "One paragraph describing the full pricing journey"
                },
                "total_unexplained_increase": {
                    "type":        "number",
                    "description": "Total amount added to the bill without clear justification"
                }
            },
            "required": ["detections", "funnel_summary"]
        }
    }
]


# ── Tool Executor ──────────────────────────────────────────────────────────

def execute_pricing_tool(
    tool_name: str,
    tool_input: dict,
    analysis_context: dict,
    raw_data: dict
) -> dict:

    stages         = {s["stage"]: s for s in raw_data["funnel_stages"]}
    stage_summaries = analysis_context["stage_summaries"]

    # ── get_pricing_pattern_definition ────────────────────────────────────
    if tool_name == "get_pricing_pattern_definition":
        pid  = tool_input.get("pattern_id")
        defn = PRICING_PATTERN_DEFINITIONS.get(pid, {})
        return {
            "pattern_id":        pid,
            "name":              defn.get("name", ""),
            "description":       defn.get("description", ""),
            "detection_signals": defn.get("detection_signals", []),
            "calculation":       defn.get("calculation", ""),
            "examples":          defn.get("examples", []),
        }

    # ── compare_stage_prices ──────────────────────────────────────────────
    elif tool_name == "compare_stage_prices":
        stage_a = tool_input.get("stage_a", "product_page")
        stage_b = tool_input.get("stage_b", "checkout")

        if stage_a not in stage_summaries or stage_b not in stage_summaries:
            return {"error": f"One or both stages not found in data: {stage_a}, {stage_b}"}

        items_a = {
            i["name"]: i["price"]
            for i in stages[stage_a].get("items", [])
        }
        items_b = {
            i["name"]: i["price"]
            for i in stages[stage_b].get("items", [])
        }

        comparisons = []
        for item_name in items_a:
            price_a = items_a.get(item_name, 0)
            price_b = items_b.get(item_name, price_a)
            delta   = round(price_b - price_a, 2)
            pct     = round((delta / price_a * 100), 2) if price_a > 0 else 0.0
            comparisons.append({
                "item":            item_name,
                f"price_{stage_a}": price_a,
                f"price_{stage_b}": price_b,
                "delta":           delta,
                "delta_pct":       pct,
                "changed":         delta != 0,
                "exceeds_5pct_threshold": abs(pct) > 5.0,
            })

        subtotal_a = stage_summaries[stage_a]["item_subtotal"]
        subtotal_b = stage_summaries[stage_b]["item_subtotal"]
        total_delta = round(subtotal_b - subtotal_a, 2)
        total_pct   = round((total_delta / subtotal_a * 100), 2) if subtotal_a > 0 else 0.0

        return {
            "stage_a":             stage_a,
            "stage_b":             stage_b,
            "item_comparisons":    comparisons,
            "subtotal_a":          subtotal_a,
            "subtotal_b":          subtotal_b,
            "subtotal_delta":      total_delta,
            "subtotal_delta_pct":  total_pct,
            "bait_switch_triggered": abs(total_pct) > 5.0,
            "verdict": (
                f"Item prices INCREASED by {total_pct}% from {stage_a} to {stage_b}. "
                f"This EXCEEDS the 5% threshold — BAIT AND SWITCH DETECTED."
                if total_pct > 5.0 else
                f"Item prices are consistent between {stage_a} and {stage_b} ({total_pct}% change). "
                f"No Bait and Switch detected for this comparison."
            )
        }

    # ── detect_fee_injections ─────────────────────────────────────────────
    elif tool_name == "detect_fee_injections":
        ref_stage  = tool_input.get("reference_stage", "product_page")
        comp_stage = tool_input.get("comparison_stage", "checkout")

        if ref_stage not in stage_summaries or comp_stage not in stage_summaries:
            return {"error": f"Stage not found: {ref_stage} or {comp_stage}"}

        ref_fees  = {
            f["name"]: f["amount"]
            for f in stages[ref_stage].get("fees_shown", [])
        }
        comp_fees = {
            f["name"]: f["amount"]
            for f in stages[comp_stage].get("fees_shown", [])
        }

        # Fees that are NEW in comparison stage
        injected = []
        for fee_name, amount in comp_fees.items():
            if fee_name not in ref_fees:
                injected.append({
                    "fee_name":       fee_name,
                    "amount":         amount,
                    "first_appeared": comp_stage,
                    "was_hidden_at":  ref_stage,
                })

        # Fees that increased significantly
        increased = []
        for fee_name in ref_fees:
            if fee_name in comp_fees:
                old_amt = ref_fees[fee_name]
                new_amt = comp_fees[fee_name]
                if old_amt > 0 and (new_amt - old_amt) / old_amt > 0.20:
                    increased.append({
                        "fee_name":     fee_name,
                        "old_amount":   old_amt,
                        "new_amount":   new_amt,
                        "increase_pct": round((new_amt - old_amt) / old_amt * 100, 2)
                    })

        item_subtotal      = stage_summaries[ref_stage]["item_subtotal"]
        injected_total     = sum(f["amount"] for f in injected)
        injected_pct       = round(
            (injected_total / item_subtotal * 100), 2
        ) if item_subtotal > 0 else 0.0

        return {
            "reference_stage":      ref_stage,
            "comparison_stage":     comp_stage,
            "fees_at_reference":    ref_fees,
            "fees_at_comparison":   comp_fees,
            "injected_fees":        injected,
            "increased_fees":       increased,
            "injected_count":       len(injected),
            "injected_total":       round(injected_total, 2),
            "injected_pct_of_subtotal": injected_pct,
            "item_subtotal":        item_subtotal,
            "drip_severity": (
                "high"   if injected_pct > 10.0 else
                "medium" if injected_pct > 5.0  else
                "low"    if injected_pct > 0    else
                "none"
            ),
            "drip_triggered": len(injected) > 0,
            "verdict": (
                f"{len(injected)} hidden fee(s) injected at {comp_stage} totaling "
                f"{injected_total:.2f} ({injected_pct}% of item subtotal). "
                f"Severity: {'HIGH' if injected_pct > 10 else 'MEDIUM' if injected_pct > 5 else 'LOW'}."
                if injected else
                f"No new fees injected between {ref_stage} and {comp_stage}. "
                f"All fees were disclosed early in the funnel."
            )
        }

    # ── calculate_total_progression ───────────────────────────────────────
    elif tool_name == "calculate_total_progression":
        return {
            "stages_analyzed":   analysis_context["stages_present"],
            "progression":       analysis_context["total_progression"],
            "first_stage":       analysis_context["first_stage"],
            "last_stage":        analysis_context["last_stage"],
            "total_increase":    analysis_context["total_increase_amount"],
            "total_increase_pct": analysis_context["total_increase_pct"],
            "item_price_delta":  analysis_context["item_price_delta"],
            "item_delta_pct":    analysis_context["item_price_delta_pct"],
            "fee_delta":         analysis_context["injected_fee_total"],
            "platform":          analysis_context["platform"],
        }

    # ── check_threshold_violations ────────────────────────────────────────
    elif tool_name == "check_threshold_violations":
        violations = []

        if analysis_context["bait_switch_triggered"]:
            violations.append({
                "pattern":   "DP07 - Bait and Switch",
                "threshold": "5% item price increase",
                "actual":    f"{analysis_context['item_price_delta_pct']}%",
                "exceeded":  True,
                "severity":  "high" if analysis_context["item_price_delta_pct"] > 15 else "medium"
            })

        drip_pct = analysis_context["injected_fee_pct"]
        if analysis_context["drip_triggered"]:
            violations.append({
                "pattern":   "DP08 - Drip Pricing",
                "threshold": "5% of item subtotal in hidden fees",
                "actual":    f"{drip_pct}% ({analysis_context['injected_fee_total']} hidden)",
                "exceeded":  drip_pct > 5.0,
                "severity":  analysis_context["drip_severity"]
            })

        return {
            "violations_found": len(violations),
            "violations":       violations,
            "bait_switch": {
                "threshold_pct":  5.0,
                "actual_pct":     analysis_context["item_price_delta_pct"],
                "triggered":      analysis_context["bait_switch_triggered"],
            },
            "drip_pricing": {
                "threshold_pct":  5.0,
                "actual_pct":     drip_pct,
                "injected_total": analysis_context["injected_fee_total"],
                "injected_fees":  analysis_context["injected_fee_names"],
                "triggered":      analysis_context["drip_triggered"],
                "severity":       analysis_context["drip_severity"],
            },
            "summary": (
                f"{len(violations)} threshold violation(s) detected. "
                + (f"Bait & Switch: item prices rose {analysis_context['item_price_delta_pct']}%. " if analysis_context["bait_switch_triggered"] else "")
                + (f"Drip Pricing: {drip_pct}% in hidden fees injected at checkout." if analysis_context["drip_triggered"] else "")
            )
        }

    # ── finalize_pricing_detections ───────────────────────────────────────
    elif tool_name == "finalize_pricing_detections":
        detections = tool_input.get("detections", [])
        for det in detections:
            if "risk_level" not in det:
                conf = det.get("confidence", 0)
                det["risk_level"] = (
                    "high"   if conf >= 0.80 else
                    "medium" if conf >= 0.55 else
                    "low"
                )
            if "prevention" not in det or not det["prevention"]:
                det["prevention"] = _default_prevention(det.get("pattern_id", ""))
        return {
            "status":     "finalized",
            "count":      len(detections),
            "detections": detections,
        }

    return {"error": f"Unknown tool: {tool_name}"}


# ── System Prompt ──────────────────────────────────────────────────────────

def _build_system_prompt(analysis_context: dict) -> str:
    ctx = analysis_context
    return f"""You are the Pricing Agent in Dark Guard AI, an autonomous system that detects
deceptive pricing practices across e-commerce purchase funnels.

YOUR JOB:
Analyze the provided purchase funnel price data and detect ONLY these 2 pricing dark patterns:

- DP07 - Bait and Switch: Item price itself increases >5% between product page and checkout
- DP08 - Drip Pricing: Hidden fees injected only at checkout, absent on product page

PRE-COMPUTED CONTEXT (use these as starting points):
  Platform:               {ctx['platform']}
  Stages analyzed:        {', '.join(ctx['stages_present'])}
  Item price delta:       {ctx['item_price_delta_pct']}% ({ctx['item_price_delta']} units)
  Bait & Switch flag:     {'⚠ YES — exceeds 5% threshold' if ctx['bait_switch_triggered'] else '✓ No — within threshold'}
  Injected fee total:     {ctx['injected_fee_total']} ({ctx['injected_fee_pct']}% of subtotal)
  Injected fee names:     {ctx['injected_fee_names'] if ctx['injected_fee_names'] else 'None detected'}
  Drip Pricing flag:      {'⚠ YES — ' + ctx['drip_severity'].upper() + ' severity' if ctx['drip_triggered'] else '✓ No new fees detected'}

YOUR ANALYSIS PROCESS — follow this exact sequence:
1. Call get_pricing_pattern_definition for DP07 and DP08
2. Call calculate_total_progression to see the full price journey
3. Call compare_stage_prices between product_page and checkout (for DP07)
4. Call detect_fee_injections between product_page and checkout (for DP08)
5. Call check_threshold_violations to confirm which thresholds are breached
6. Call finalize_pricing_detections with your confirmed findings

CONFIDENCE SCORING:
- 0.90–1.00 = Mathematical proof, threshold clearly exceeded, no ambiguity
- 0.70–0.89 = Strong numerical evidence, clear pattern
- 0.50–0.69 = Possible pattern, borderline threshold
- Below 0.50 = Do NOT report

EVIDENCE RULES:
- price_evidence must contain actual numbers from the data
- Include reference_price, final_price, difference, difference_pct
- For DP08, list every injected fee by name and amount
- Always call finalize_pricing_detections as your final action
"""


# ── Main Agent Runner ──────────────────────────────────────────────────────

def run_pricing_agent(input_file: str, verbose: bool = True) -> Dict:
    """
    Run the Pricing Agent on a JSON funnel input file.

    Args:
        input_file: Path to the .json pricing input file
        verbose:    Print step-by-step agent activity

    Returns:
        Dict with detections, funnel_summary, total_unexplained_increase
    """
    from rich.console import Console
    console = Console()

    def step(msg, detail=""):
        if verbose:
            console.print(f"  [bold blue]→[/bold blue] {msg}", end="")
            if detail:
                console.print(f" [dim]{detail}[/dim]", end="")
            console.print()

    step("Pricing Agent starting")
    step("Loading funnel data", input_file)

    # ── Load and compute context ───────────────────────────────────────────
    loader   = PricingLoader()
    raw_data = loader.load(input_file)
    ctx      = loader.compute_analysis_context(raw_data)

    step(
        "Funnel loaded",
        f"{len(ctx['stages_present'])} stages: {' → '.join(ctx['stages_present'])}"
    )
    step(
        "Pre-analysis",
        f"Item delta: {ctx['item_price_delta_pct']}% | "
        f"Hidden fees: {ctx['injected_fee_total']} | "
        f"Platform: {ctx['platform']}"
    )

    step("Applying deterministic pricing checks")
    final_result = _run_rule_based_pricing_analysis(ctx, raw_data)
    step(
        "Pricing checks complete",
        f"{len(final_result['detections'])} detection(s) confirmed"
    )
    return final_result

    # ── Initialize Gemini model ────────────────────────────────────────────
    chat = _create_pricing_chat(
        model_name=settings.pricing_agent_model,
        tools=[{"function_declarations": PRICING_AGENT_TOOLS}],
        system_instruction=_build_system_prompt(ctx),
    )
    final_result = {
        "detections":               [],
        "funnel_summary":           "",
        "total_unexplained_increase": 0.0,
        "analysis_context":         ctx,
    }

    initial_message = (
        f"Analyze this purchase funnel for pricing dark patterns.\n\n"
        f"=== FUNNEL DATA ===\n"
        f"{json.dumps(raw_data, indent=2)}\n"
        f"=== END FUNNEL DATA ===\n\n"
        f"Pre-computed context is in your system prompt. "
        f"Follow your analysis process: get definitions → calculate progression → "
        f"compare prices → detect fee injections → check thresholds → finalize."
    )

    response     = _send_pricing_chat_message(chat, initial_message)
    max_iter     = 20
    iteration    = 0

    # ── Agentic loop ───────────────────────────────────────────────────────
    while iteration < max_iter:
        iteration += 1

        has_fn_call = (
            response.candidates and
            response.candidates[0].content.parts and
            any(
                hasattr(p, "function_call") and p.function_call.name
                for p in response.candidates[0].content.parts
            )
        )

        if not has_fn_call:
            step("Agent finished without finalize — parsing text response")
            final_result.update(_parse_text_response(response.text))
            break

        fn_results = []

        for part in response.candidates[0].content.parts:
            if not (hasattr(part, "function_call") and part.function_call.name):
                continue

            fn_name  = part.function_call.name
            fn_input = dict(part.function_call.args)

            step(f"Agent calling tool", f"[{fn_name}]")

            # Execute the tool
            tool_result = execute_pricing_tool(fn_name, fn_input, ctx, raw_data)

            # ── finalize — capture and exit ────────────────────────────────
            if fn_name == "finalize_pricing_detections":
                detections = tool_result.get("detections", [])
                final_result.update({
                    "detections":               detections,
                    "funnel_summary":           fn_input.get("funnel_summary", ""),
                    "total_unexplained_increase": fn_input.get("total_unexplained_increase", 0.0),
                    "analysis_context":         ctx,
                })
                step(
                    "Agent finalized",
                    f"{len(detections)} detection(s) confirmed"
                )

                # Send result back then exit
                _send_pricing_chat_message(
                    chat,
                    _build_tool_response_message([{
                        "function_response": {
                            "name":     fn_name,
                            "response": tool_result
                        }
                    }])
                )
                return final_result   # ← EXIT

            fn_results.append({
                "function_response": {
                    "name":     fn_name,
                    "response": tool_result
                }
            })

        # Send all tool results back
        if fn_results:
            response = _send_pricing_chat_message(
                chat,
                _build_tool_response_message(fn_results),
            )

    return final_result


# ── Helpers ────────────────────────────────────────────────────────────────

def _default_prevention(pattern_id: str) -> str:
    defaults = {
        "DP07": (
            "Screenshot the product page price before adding to cart. "
            "Compare it against the checkout price. If the item price increased, "
            "abandon the purchase and report it. Search for the same product on "
            "competitor sites to verify the real price."
        ),
        "DP08": (
            "Always scroll to the very bottom of the checkout page before entering "
            "payment details. Add up all fees manually. If the total is significantly "
            "higher than the product page price, abandon the cart and compare with "
            "competitors who show the full price upfront."
        ),
    }
    return defaults.get(pattern_id, "Review all price details carefully before payment.")


def _parse_text_response(text: str) -> dict:
    """Fallback: parse JSON from text if agent didn't call finalize."""
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            return {
                "detections":   data.get("detections", []),
                "funnel_summary": data.get("funnel_summary", "Parsed from text"),
                "total_unexplained_increase": data.get("total_unexplained_increase", 0.0),
            }
    except Exception:
        pass
    return {
        "detections":   [],
        "funnel_summary": "Could not parse agent response",
        "total_unexplained_increase": 0.0,
    }
