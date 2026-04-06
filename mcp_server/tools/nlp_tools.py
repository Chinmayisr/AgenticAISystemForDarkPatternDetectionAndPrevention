# mcp_server/tools/nlp_tools.py

import re
from typing import Any
from config import DARK_PATTERNS, TEXT_PATTERNS


async def classify_text(tool_input: dict) -> dict:
    """
    Fast rule-based pre-classification before LLM analysis.
    Returns initial pattern scores based on keyword matching.
    This supplements (not replaces) the LLM agent's analysis.
    """
    text = tool_input.get("text", "").lower()
    context = tool_input.get("context", "")
    scores = {}

    # DP01 — False Urgency signals
    urgency_patterns = [
        r"\bonly \d+ left\b", r"\blimited stock\b", r"\bselling (fast|out)\b",
        r"\b\d+:\d+:\d+\b",   # countdown timer
        r"\bhurry\b", r"\bact now\b", r"\bexpires? (soon|today|in)\b",
        r"\b\d+ (people|others) (viewing|looking)\b"
    ]
    dp01_score = sum(1 for p in urgency_patterns if re.search(p, text))
    if dp01_score > 0:
        scores["DP01"] = min(0.4 + dp01_score * 0.15, 0.95)

    # DP03 — Confirm Shaming
    shaming_patterns = [
        r"no thanks.{0,20}(hate|don't want|refuse|miss)",
        r"i don't want (free|savings|discount|deals)",
        r"no,? i (prefer|like) (paying more|missing out)",
    ]
    dp03_score = sum(1 for p in shaming_patterns if re.search(p, text))
    if dp03_score > 0:
        scores["DP03"] = min(0.5 + dp03_score * 0.2, 0.95)

    # DP05 — Subscription Trap
    sub_patterns = [
        r"auto.?renew", r"cancel anytime\*", r"cancel.{0,20}before",
        r"billed annually", r"subscription continues"
    ]
    dp05_score = sum(1 for p in sub_patterns if re.search(p, text))
    if dp05_score > 0:
        scores["DP05"] = min(0.45 + dp05_score * 0.15, 0.95)

    # DP08 — Drip Pricing (fee keywords)
    fee_patterns = [
        r"(service|convenience|processing|platform|booking) fee",
        r"additional charges?", r"taxes? (not )?included",
        r"\+\s*\$\d+", r"handling fee"
    ]
    dp08_score = sum(1 for p in fee_patterns if re.search(p, text))
    if dp08_score > 0:
        scores["DP08"] = min(0.5 + dp08_score * 0.15, 0.95)

    # DP11 — Trick Question (double negatives)
    trick_patterns = [
        r"(uncheck|deselect).{0,30}(not|don't|no)",
        r"(opt.out).{0,30}(not|unless)",
        r"do not.{0,30}(uncheck|deselect|remove)"
    ]
    dp11_score = sum(1 for p in trick_patterns if re.search(p, text))
    if dp11_score > 0:
        scores["DP11"] = min(0.55 + dp11_score * 0.2, 0.95)

    return {
        "tool": "classify_text_pattern",
        "input_text": text[:100],
        "rule_based_scores": scores,
        "suspected_patterns": list(scores.keys()),
        "note": "These are initial scores. LLM agent will refine."
    }