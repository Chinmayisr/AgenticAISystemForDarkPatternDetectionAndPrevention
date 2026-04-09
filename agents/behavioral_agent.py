# agents/behavioral_agent.py

import json
import importlib
from typing import Dict, List
from config import get_settings
from agents.behavioral_pattern_definitions import BEHAVIORAL_PATTERN_DEFINITIONS
from utils.behavioral_analyzer import BehavioralAnalyzer

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
            "Missing Google GenAI client library. Install it with: pip install google-genai"
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


def _create_behavioral_chat(*, model_name: str, tools: List[dict], system_instruction: str):
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
            "that supports the Behavioral Agent API."
        )

    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


def _score_behavioral_confidence(severity: str, signal_count: int) -> float:
    if severity == "high":
        return 0.96 if signal_count >= 3 else 0.90
    if severity == "medium":
        return 0.84 if signal_count >= 2 else 0.76
    if severity == "low":
        return 0.66
    return 0.0


def _risk_from_confidence(confidence: float) -> str:
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _build_behavioral_summary(ctx: dict, detections: List[dict]) -> str:
    active = ", ".join(ctx.get("active_checks", [])) if ctx.get("active_checks") else "no active checks"
    parts = [f"Platform {ctx['platform']} behavioral session analyzed with {active}."]

    if detections:
        found = ", ".join(f"{d['pattern_id']} ({d['pattern_name']})" for d in detections)
        parts.append(f"Detected {len(detections)} behavioral dark pattern(s): {found}.")
    else:
        parts.append("No behavioral dark patterns crossed the configured thresholds.")

    return " ".join(parts)


def _run_rule_based_behavioral_analysis(ctx: dict) -> Dict:
    detections = []

    basket = ctx.get("basket_sneaking", {})
    if basket.get("triggered"):
        signals = []
        if basket.get("sneaked_count", 0):
            signals.append(f"{basket['sneaked_count']} unauthorized cart addition(s)")
        if basket.get("prechecked_paid_boxes"):
            signals.append(f"{len(basket['prechecked_paid_boxes'])} pre-checked paid box(es)")
        if basket.get("recurring_items"):
            signals.append("Recurring item inserted without clear consent")

        confidence = _score_behavioral_confidence(basket.get("severity", "none"), len(signals))
        affected_items = [item.get("item_name", "") for item in basket.get("sneaked_items", [])]
        affected_items.extend(cb.get("label", "") for cb in basket.get("prechecked_paid_boxes", []))
        detections.append({
            "pattern_id": "DP02",
            "pattern_name": "Basket Sneaking",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "behavioral_evidence": {
                "signals_found": signals,
                "key_metric": (
                    f"{basket.get('sneaked_count', 0)} sneaked item(s) totaling "
                    f"{basket.get('sneaked_total_value', 0):.2f}"
                ),
                "affected_items": [item for item in affected_items if item],
            },
            "explanation": (
                f"Items or paid add-ons were introduced without a clear matching add-to-cart action. "
                f"The session contains {basket.get('sneaked_count', 0)} sneaked item(s) and "
                f"{len(basket.get('prechecked_paid_boxes', []))} pre-selected paid option(s)."
            ),
            "prevention": _default_prevention("DP02"),
        })

    subscription = ctx.get("subscription_trap", {})
    if subscription.get("triggered"):
        signals = list(subscription.get("flags", []))
        confidence = _score_behavioral_confidence(subscription.get("severity", "none"), len(signals))
        detections.append({
            "pattern_id": "DP05",
            "pattern_name": "Subscription Trap",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "behavioral_evidence": {
                "signals_found": signals,
                "key_metric": (
                    f"{subscription.get('cancellation_steps', 0)} cancellation steps vs "
                    f"{subscription.get('signup_steps', 0)} signup steps "
                    f"({subscription.get('step_ratio', 0)}x harder)"
                ),
                "affected_items": ["subscription flow", "free trial", "cancellation path"],
            },
            "explanation": (
                f"Cancelling is materially harder than signing up, and the subscription flow also shows "
                f"additional friction such as low-prominence disclosure or interruption before cancellation completes."
            ),
            "prevention": _default_prevention("DP05"),
        })

    billing = ctx.get("saas_billing", {})
    if billing.get("triggered"):
        signals = list(billing.get("flags", []))
        confidence = _score_behavioral_confidence(billing.get("severity", "none"), len(signals))
        affected_items = [billing.get("plan_name", "billing settings")]
        affected_items.extend(charge.get("description", "") for charge in billing.get("unnotified_charges", []))
        detections.append({
            "pattern_id": "DP12",
            "pattern_name": "SaaS Billing",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "behavioral_evidence": {
                "signals_found": signals,
                "key_metric": (
                    f"{billing.get('downgrade_clicks', 0)} downgrade clicks vs "
                    f"{billing.get('upgrade_clicks', 0)} upgrade clicks "
                    f"({billing.get('upgrade_downgrade_ratio', 0)}x harder)"
                ),
                "affected_items": [item for item in affected_items if item],
            },
            "explanation": (
                f"Billing management is asymmetric or opaque. The session shows renewal/billing friction and "
                f"{billing.get('unnotified_total', 0):.2f} in unnotified charges."
            ),
            "prevention": _default_prevention("DP12"),
        })

    nagging = ctx.get("nagging", {})
    if nagging.get("triggered"):
        popups = nagging.get("nagging_popups", [])
        signals = [
            f"{popup.get('popup_id', 'popup')} appeared {popup.get('appearances', 0)} time(s)"
            for popup in popups[:5]
        ]
        if any(popup.get("cookie_consent_ignored") for popup in popups):
            signals.append("Cookie consent choice was ignored and the popup reappeared")
        confidence = _score_behavioral_confidence(nagging.get("overall_severity", "none"), len(signals))
        detections.append({
            "pattern_id": "DP10",
            "pattern_name": "Nagging",
            "confidence": confidence,
            "risk_level": _risk_from_confidence(confidence),
            "behavioral_evidence": {
                "signals_found": signals,
                "key_metric": (
                    f"{nagging.get('nagging_count', 0)} repeating popup(s), "
                    f"{nagging.get('high_severity_count', 0)} high severity"
                ),
                "affected_items": [popup.get("popup_id", "") for popup in popups if popup.get("popup_id")],
            },
            "explanation": (
                f"The same prompts reappeared after dismissal, creating repeated pressure on the user "
                f"instead of respecting the original choice."
            ),
            "prevention": _default_prevention("DP10"),
        })

    return {
        "detections": detections,
        "session_summary": _build_behavioral_summary(ctx, detections),
        "analysis_context": ctx,
    }

# ── Tool Definitions ───────────────────────────────────────────────────────

BEHAVIORAL_AGENT_TOOLS = [
    {
        "name": "get_behavioral_pattern_definition",
        "description": (
            "Retrieve the full definition, behavioral signals, and detection logic "
            "for a specific behavioral dark pattern. Call this before analyzing "
            "each pattern to understand exactly what to look for."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern_id": {
                    "type": "string",
                    "enum": ["DP02", "DP05", "DP10", "DP12"],
                    "description": (
                        "DP02=Basket Sneaking, DP05=Subscription Trap, "
                        "DP10=Nagging, DP12=SaaS Billing"
                    )
                }
            },
            "required": ["pattern_id"]
        }
    },
    {
        "name": "analyze_cart_events",
        "description": (
            "Analyze cart event sequence to find unauthorized item additions. "
            "Identifies items added without explicit user add-to-cart actions "
            "and pre-checked boxes for paid items. Use for Basket Sneaking (DP02)."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "analyze_subscription_flow",
        "description": (
            "Compare signup steps vs cancellation steps, check trial conversion "
            "behavior, and assess auto-renewal disclosure. "
            "Use for Subscription Trap (DP05)."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "analyze_billing_practices",
        "description": (
            "Check for unexpected charges, renewal reminder absence, "
            "upgrade vs downgrade asymmetry, and billing settings accessibility. "
            "Use for SaaS Billing (DP12)."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "analyze_popup_frequency",
        "description": (
            "Group popups by ID, count reappearances after dismissal, "
            "and identify cookie consent violations and push notification spam. "
            "Use for Nagging (DP10)."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "check_all_thresholds",
        "description": (
            "Run threshold checks across all 4 patterns simultaneously. "
            "Returns a summary of which patterns are triggered and at what severity. "
            "Call this after running individual analyses."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "finalize_behavioral_detections",
        "description": (
            "Submit your confirmed behavioral dark pattern detections. "
            "Call this ONCE after all analyses are complete."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "detections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pattern_id":   {"type": "string"},
                            "pattern_name": {"type": "string"},
                            "confidence":   {"type": "number"},
                            "risk_level": {
                                "type": "string",
                                "enum": ["high", "medium", "low"]
                            },
                            "behavioral_evidence": {
                                "type": "object",
                                "description": "The specific behavioral signals found",
                                "properties": {
                                    "signals_found":  {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of specific behavioral signals observed"
                                    },
                                    "key_metric":     {
                                        "type": "string",
                                        "description": "The single most damning metric (e.g. '8 cancellation steps vs 2 signup steps')"
                                    },
                                    "affected_items": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Specific items, fees, or popups involved"
                                    }
                                }
                            },
                            "explanation":  {"type": "string"},
                            "prevention":   {"type": "string"}
                        },
                        "required": [
                            "pattern_id", "pattern_name",
                            "confidence", "behavioral_evidence", "explanation"
                        ]
                    }
                },
                "session_summary": {
                    "type": "string",
                    "description": "Overall summary of what was found in this session"
                }
            },
            "required": ["detections", "session_summary"]
        }
    }
]

# ── Tool Executor ──────────────────────────────────────────────────────────

def execute_behavioral_tool(
    tool_name: str,
    tool_input: dict,
    ctx: dict
) -> dict:

    if tool_name == "get_behavioral_pattern_definition":
        pid  = tool_input.get("pattern_id")
        defn = BEHAVIORAL_PATTERN_DEFINITIONS.get(pid, {})
        return {
            "pattern_id":          pid,
            "name":                defn.get("name", ""),
            "description":         defn.get("description", ""),
            "behavioral_signals":  defn.get("behavioral_signals", []),
            "detection_logic":     defn.get("detection_logic", ""),
            "severity_rules":      defn.get("severity_rules", {}),
        }

    elif tool_name == "analyze_cart_events":
        bs = ctx["basket_sneaking"]
        if not bs["has_data"]:
            return {"status": "no_cart_data", "message": "No cart events in input"}
        return {
            "total_events":          bs["total_cart_events"],
            "sneaked_items":         bs["sneaked_items"],
            "sneaked_count":         bs["sneaked_count"],
            "sneaked_total_value":   bs["sneaked_total_value"],
            "recurring_sneaked":     bs["recurring_items"],
            "prechecked_paid_boxes": bs["prechecked_paid_boxes"],
            "triggered":             bs["triggered"],
            "severity":              bs["severity"],
            "verdict": (
                f"{bs['sneaked_count']} item(s) sneaked into cart without user action, "
                f"totaling {bs['sneaked_total_value']}. "
                f"Pre-checked boxes: {len(bs['prechecked_paid_boxes'])}."
                if bs["triggered"] else
                "No unauthorized cart additions detected."
            )
        }

    elif tool_name == "analyze_subscription_flow":
        sub = ctx["subscription_trap"]
        if not sub["has_data"]:
            return {"status": "no_subscription_data", "message": "No subscription flow in input"}
        return {
            "signup_steps":              sub["signup_steps"],
            "cancellation_steps":        sub["cancellation_steps"],
            "step_ratio":                sub["step_ratio"],
            "step_ratio_exceeds_2x":     sub["step_ratio_exceeds_2x"],
            "auto_renewal_prominence":   sub["auto_renewal_prominence"],
            "trial_reminder_sent":       sub["trial_reminder_sent"],
            "trial_auto_converts":       sub["trial_auto_converts"],
            "retention_popups":          sub["retention_popups"],
            "mandatory_survey":          sub["mandatory_survey"],
            "cancel_path":               sub["cancel_path"],
            "flags":                     sub["flags"],
            "triggered":                 sub["triggered"],
            "severity":                  sub["severity"],
            "verdict": (
                f"Subscription Trap detected. {sub['step_ratio']}x harder to cancel "
                f"({sub['cancellation_steps']} steps) than to sign up ({sub['signup_steps']} steps). "
                f"{sub['flag_count']} violation flag(s)."
                if sub["triggered"] else
                "Subscription flow appears fair. Cancellation is not significantly harder than signup."
            )
        }

    elif tool_name == "analyze_billing_practices":
        billing = ctx["saas_billing"]
        if not billing["has_data"]:
            return {"status": "no_billing_data", "message": "No billing data in input"}
        return {
            "plan_name":                    billing["plan_name"],
            "amount_per_cycle":             billing["amount_per_cycle"],
            "pre_renewal_reminder":         billing["pre_renewal_reminder"],
            "billing_clicks_required":      billing["billing_clicks_required"],
            "upgrade_clicks":               billing["upgrade_clicks"],
            "downgrade_clicks":             billing["downgrade_clicks"],
            "upgrade_downgrade_ratio":      billing["upgrade_downgrade_ratio"],
            "ratio_exceeds_3x":             billing["ratio_exceeds_3x"],
            "downgrade_requires_support":   billing["downgrade_requires_support"],
            "charges_visible_on_dashboard": billing["charges_visible_on_dashboard"],
            "unnotified_charges":           billing["unnotified_charges"],
            "unnotified_total":             billing["unnotified_total"],
            "flags":                        billing["flags"],
            "triggered":                    billing["triggered"],
            "severity":                     billing["severity"],
            "verdict": (
                f"SaaS Billing violations found. {billing['flag_count']} flag(s): "
                + "; ".join(billing["flags"][:2])
                if billing["triggered"] else
                "Billing practices appear fair."
            )
        }

    elif tool_name == "analyze_popup_frequency":
        nagging = ctx["nagging"]
        if not nagging["has_data"]:
            return {"status": "no_popup_data", "message": "No popup events in input"}
        return {
            "total_popup_events":  nagging["total_popup_events"],
            "unique_popups":       nagging["unique_popups"],
            "nagging_popups":      nagging["nagging_popups"],
            "nagging_count":       nagging["nagging_count"],
            "high_severity_count": nagging["high_severity_count"],
            "triggered":           nagging["triggered"],
            "overall_severity":    nagging["overall_severity"],
            "verdict": (
                f"{nagging['nagging_count']} nagging popup(s) detected. "
                f"{nagging['high_severity_count']} at HIGH severity."
                if nagging["triggered"] else
                "No nagging behavior detected."
            )
        }

    elif tool_name == "check_all_thresholds":
        results = {}
        for key, label in [
            ("basket_sneaking",   "DP02"),
            ("subscription_trap", "DP05"),
            ("saas_billing",      "DP12"),
            ("nagging",           "DP10"),
        ]:
            section = ctx.get(key, {})
            results[label] = {
                "has_data":  section.get("has_data", False),
                "triggered": section.get("triggered", False),
                "severity":  section.get("severity", section.get("overall_severity", "none")),
            }
        triggered = [k for k, v in results.items() if v["triggered"]]
        return {
            "threshold_results":   results,
            "patterns_triggered":  triggered,
            "triggered_count":     len(triggered),
            "summary": (
                f"{len(triggered)} pattern(s) triggered: {', '.join(triggered)}"
                if triggered else
                "No patterns triggered by threshold checks."
            )
        }

    elif tool_name == "finalize_behavioral_detections":
        detections = tool_input.get("detections", [])
        for det in detections:
            if "risk_level" not in det:
                conf = det.get("confidence", 0)
                det["risk_level"] = (
                    "high"   if conf >= 0.80 else
                    "medium" if conf >= 0.55 else
                    "low"
                )
            if not det.get("prevention"):
                det["prevention"] = _default_prevention(det.get("pattern_id", ""))
        return {
            "status":     "finalized",
            "count":      len(detections),
            "detections": detections,
        }

    return {"error": f"Unknown tool: {tool_name}"}


# ── System Prompt ──────────────────────────────────────────────────────────

def _build_system_prompt(ctx: dict) -> str:
    active = ctx.get("active_checks", [])
    bs     = ctx["basket_sneaking"]
    sub    = ctx["subscription_trap"]
    bill   = ctx["saas_billing"]
    nag    = ctx["nagging"]

    return f"""You are the Behavioral Agent in Dark Guard AI, an autonomous system that detects
manipulative behavioral design patterns on websites and apps.

YOUR JOB:
Analyze the provided behavioral session data and detect ONLY these 4 patterns:
  • DP02 - Basket Sneaking:    Unauthorized items added to cart
  • DP05 - Subscription Trap: Easy to subscribe, very hard to cancel
  • DP12 - SaaS Billing:      Opaque or unfair billing practices
  • DP10 - Nagging:           Repeated popups after user dismissal

DATA AVAILABLE IN THIS SESSION: {', '.join(active) if active else 'none'}

PRE-COMPUTED FLAGS (use as starting points — verify with tools):
  Basket Sneaking:
    → Sneaked items found:    {bs.get('sneaked_count', 'N/A')} item(s)
    → Pre-checked paid boxes: {len(bs.get('prechecked_paid_boxes', []))}
    → Triggered:              {'⚠ YES' if bs.get('triggered') else '✓ No'}

  Subscription Trap:
    → Step ratio (cancel/signup): {sub.get('step_ratio', 'N/A')}x
    → Trial reminder sent:        {sub.get('trial_reminder_sent', 'N/A')}
    → Flags raised:               {sub.get('flag_count', 0)}
    → Triggered:                  {'⚠ YES' if sub.get('triggered') else '✓ No'}

  SaaS Billing:
    → Pre-renewal reminder:    {bill.get('pre_renewal_reminder', 'N/A')}
    → Unnotified charges:      {bill.get('unnotified_total', 'N/A')}
    → Upgrade/downgrade ratio: {bill.get('upgrade_downgrade_ratio', 'N/A')}x
    → Triggered:               {'⚠ YES' if bill.get('triggered') else '✓ No'}

  Nagging:
    → Nagging popups found:  {nag.get('nagging_count', 'N/A')}
    → High severity count:   {nag.get('high_severity_count', 'N/A')}
    → Triggered:             {'⚠ YES' if nag.get('triggered') else '✓ No'}

YOUR ANALYSIS PROCESS:
1. Call get_behavioral_pattern_definition for each of the 4 patterns
2. For each pattern with data, call its specific analysis tool:
   - analyze_cart_events         (for DP02)
   - analyze_subscription_flow   (for DP05)
   - analyze_billing_practices   (for DP12)
   - analyze_popup_frequency     (for DP10)
3. Call check_all_thresholds to confirm which are triggered
4. Call finalize_behavioral_detections with confirmed findings

CONFIDENCE SCORING:
- 0.90-1.00 = Multiple clear violations, no ambiguity
- 0.70-0.89 = Strong behavioral signals, clear pattern
- 0.50-0.69 = Moderate signals, possible pattern
- Below 0.50 = Do NOT report

Always call finalize_behavioral_detections as your last action.
"""


# ── Main Agent Runner ──────────────────────────────────────────────────────

def run_behavioral_agent(input_file: str, verbose: bool = True) -> Dict:
    from rich.console import Console
    console = Console()

    def step(msg, detail=""):
        if verbose:
            console.print(f"  [bold blue]→[/bold blue] {msg}", end="")
            if detail:
                console.print(f" [dim]{detail}[/dim]", end="")
            console.print()

    step("Behavioral Agent starting")
    step("Loading behavioral data", input_file)

    analyzer = BehavioralAnalyzer()
    raw_data = analyzer.load(input_file)
    ctx      = analyzer.compute_context(raw_data)

    step("Session loaded", f"Platform: {ctx['platform']} | Active checks: {', '.join(ctx['active_checks'])}")

    step("Applying deterministic behavioral checks")
    final_result = _run_rule_based_behavioral_analysis(ctx)
    step(
        "Behavioral checks complete",
        f"{len(final_result['detections'])} detection(s) confirmed"
    )
    return final_result

    chat = _create_behavioral_chat(
        model_name=settings.nlp_agent_model,
        tools=[{"function_declarations": BEHAVIORAL_AGENT_TOOLS}],
        system_instruction=_build_system_prompt(ctx),
    )
    final_result = {
        "detections":      [],
        "session_summary": "",
        "analysis_context": ctx,
    }

    initial_message = (
        f"Analyze this behavioral session data for dark patterns.\n\n"
        f"=== SESSION DATA ===\n"
        f"{json.dumps(raw_data, indent=2)}\n"
        f"=== END SESSION DATA ===\n\n"
        f"Active data sections: {', '.join(ctx['active_checks'])}. "
        f"Follow your process: get definitions → run specific analyses → "
        f"check thresholds → finalize."
    )

    response  = chat.send_message(initial_message)
    max_iter  = 25
    iteration = 0

    while iteration < max_iter:
        iteration += 1

        has_fn = (
            response.candidates and
            response.candidates[0].content.parts and
            any(
                hasattr(p, "function_call") and p.function_call.name
                for p in response.candidates[0].content.parts
            )
        )

        if not has_fn:
            step("Agent finished without finalize — parsing response")
            final_result.update(_parse_text_response(response.text))
            break

        fn_results = []

        for part in response.candidates[0].content.parts:
            if not (hasattr(part, "function_call") and part.function_call.name):
                continue

            fn_name  = part.function_call.name
            fn_input = dict(part.function_call.args)

            step("Agent calling tool", f"[{fn_name}]")

            tool_result = execute_behavioral_tool(fn_name, fn_input, ctx)

            if fn_name == "finalize_behavioral_detections":
                final_result.update({
                    "detections":      tool_result.get("detections", []),
                    "session_summary": fn_input.get("session_summary", ""),
                    "analysis_context": ctx,
                })
                step("Agent finalized", f"{len(final_result['detections'])} detection(s)")

                chat.send_message(
                    _build_tool_response_message([{
                        "function_response": {
                            "name":     fn_name,
                            "response": tool_result
                        }
                    }])
                )
                return final_result

            fn_results.append({
                "function_response": {
                    "name":     fn_name,
                    "response": tool_result
                }
            })

        if fn_results:
            response = chat.send_message(_build_tool_response_message(fn_results))

    return final_result


# ── Helpers ────────────────────────────────────────────────────────────────

def _default_prevention(pattern_id: str) -> str:
    defaults = {
        "DP02": (
            "Before clicking Pay, scroll through your entire cart and remove "
            "any items you did not add. Uncheck all pre-selected boxes. "
            "Compare your cart total with what you intended to buy."
        ),
        "DP05": (
            "Before subscribing, search for '[service name] how to cancel' to know "
            "what you're getting into. Set a calendar reminder 5 days before your "
            "trial ends. Screenshot all subscription terms at signup."
        ),
        "DP12": (
            "Set your own calendar reminder 7 days before your renewal date. "
            "Use a virtual card with the exact subscription amount to prevent "
            "unexpected charges. Check your billing history monthly."
        ),
        "DP10": (
            "Install uBlock Origin or a similar content blocker. "
            "Use your browser's built-in popup blocker settings. "
            "For cookie banners that reappear, clear site cookies and use "
            "a privacy-focused browser extension."
        ),
    }
    return defaults.get(pattern_id, "Proceed carefully and document all interactions.")


def _parse_text_response(text: str) -> dict:
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            return {
                "detections":      data.get("detections", []),
                "session_summary": data.get("session_summary", "Parsed from text"),
            }
    except Exception:
        pass
    return {"detections": [], "session_summary": "Could not parse response"}
