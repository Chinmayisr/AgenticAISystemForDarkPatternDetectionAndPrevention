# agents/nlp_agent.py

import json
import re
import asyncio
import importlib
from typing import List, Dict, Optional
from config import get_settings

settings = get_settings()

client = None
GOOGLE_GENAI_PACKAGE = None

try:
    genai_module = importlib.import_module("google.genai")
    client = genai_module.Client(api_key=settings.google_api_key)
    GOOGLE_GENAI_PACKAGE = "genai"
except ImportError:
    genai_module = None

if client is None:
    try:
        google_generativeai = importlib.import_module("google.generativeai")
        google_generativeai.configure(api_key=settings.google_api_key)
        client = google_generativeai
        GOOGLE_GENAI_PACKAGE = "generativeai"
    except ImportError as exc:
        raise ImportError(
            "Missing Google GenAI client library. Install it with: pip install google-genai"
        ) from exc

from .pattern_definitions import PATTERN_DEFINITIONS
from utils.text_extractor import TextExtractor


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


def _is_service_unavailable_error(exc):
    message = str(exc).lower()
    return (
        "503 unavailable" in message or
        "status': 'unavailable'" in message or
        "currently experiencing high demand" in message
    )


def _is_permission_denied_error(exc):
    message = str(exc).lower()
    return (
        "403 permission_denied" in message or
        "permission denied" in message or
        "project has been denied access" in message
    )


def _extract_retry_delay_seconds(exc) -> int | None:
    message = str(exc)
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    return None

NLP_AGENT_TOOLS = [
    {
        "name": "scan_text_for_pattern",
        "description": (
            "Scan a piece of text for a specific dark pattern. "
            "Call this once per pattern you want to check. "
            "Returns: found (bool), confidence (0-1), evidence (list of matching phrases)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text chunk to analyze"
                },
                "pattern_id": {
                    "type": "string",
                    "enum":  ["DP01", "DP03", "DP04", "DP09", "DP11"],
                    "description": "Which dark pattern to check for"
                }
            },
            "required": ["text", "pattern_id"]
        }
    },
    {
        "name": "get_pattern_definition",
        "description": (
            "Retrieve the full definition, signals, and examples for a dark pattern. "
            "Call this if you need more context about what a pattern looks like "
            "before making a classification decision."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern_id": {
                    "type": "string",
                    "enum":  ["DP01", "DP03", "DP04", "DP09", "DP11"]
                }
            },
            "required": ["pattern_id"]
        }
    },
    {
        "name": "extract_high_risk_lines",
        "description": (
            "Extract lines from the text that are most likely to contain dark patterns. "
            "Call this first to get a focused set of lines before deep analysis. "
            "Returns a list of suspicious text lines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Full webpage text to scan for suspicious lines"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "finalize_detections",
        "description": (
            "Submit your final list of detected dark patterns. "
            "Call this ONCE at the end after all pattern checks are complete. "
            "This ends the analysis loop and produces the final report."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "detections": {
                    "type": "array",
                    "description": "List of confirmed dark pattern detections",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pattern_id":   {"type": "string"},
                            "pattern_name": {"type": "string"},
                            "confidence":   {"type": "number", "minimum": 0, "maximum": 1},
                            "risk_level":   {"type": "string", "enum": ["high", "medium", "low"]},
                            "evidence":     {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Exact quotes from the text that are the dark pattern"
                            },
                            "explanation":  {"type": "string",
                                             "description": "Why this is a dark pattern"},
                            "prevention":   {"type": "string",
                                             "description": "What the user should do about this"}
                        },
                        "required": ["pattern_id", "pattern_name", "confidence", "evidence"]
                    }
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence summary of what was found"
                }
            },
            "required": ["detections"]
        }
    }
]


# ── Tool Executor ──────────────────────────────────────────────────────────
# When the agent calls a tool, this function runs the actual logic.

def execute_nlp_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute an NLP agent tool and return the result."""

    if tool_name == "extract_high_risk_lines":
        extractor = TextExtractor()
        lines = extractor.extract_high_risk_lines(tool_input["text"])
        return {
            "high_risk_lines": lines,
            "count":           len(lines),
            "note":            "These lines most likely contain dark patterns. Analyze them carefully."
        }

    elif tool_name == "get_pattern_definition":
        pid  = tool_input["pattern_id"]
        defn = PATTERN_DEFINITIONS.get(pid, {})
        return {
            "pattern_id":   pid,
            "name":         defn.get("name", ""),
            "description":  defn.get("description", ""),
            "signals":      defn.get("signals", []),
            "examples":     defn.get("examples", []),
        }

    elif tool_name == "scan_text_for_pattern":
        return _rule_based_scan(tool_input["text"], tool_input["pattern_id"])

    elif tool_name == "finalize_detections":
        # This is the terminal tool — signals end of agent loop
        return {
            "status":     "finalized",
            "count":      len(tool_input.get("detections", [])),
            "detections": tool_input.get("detections", [])
        }

    return {"error": f"Unknown tool: {tool_name}"}


def _rule_based_scan(text: str, pattern_id: str) -> dict:
    """
    Fast rule-based pre-scan for a specific pattern.
    Returns initial signals that the LLM then confirms or refutes.
    """
    text_lower = text.lower()
    found_evidence = []
    base_score     = 0.0

    if pattern_id == "DP01":   # False Urgency
        rules = [
            (r'\bonly\s+\d+\s*(left|remaining|in stock)\b',        0.85, "Fake scarcity"),
            (r'\b\d+\s+people?\s+(are\s+)?(viewing|watching)\b',   0.80, "Fake social proof"),
            (r'\b(deal|sale|offer)\s+ends?\s+in\b',                 0.75, "Fake deadline"),
            (r'\d{1,2}:\d{2}:\d{2}',                               0.70, "Countdown timer"),
            (r'\b(hurry|act now|last chance|selling fast)\b',       0.72, "Urgency language"),
            (r'\b(flash sale|lightning deal|limited time)\b',       0.70, "Urgency label"),
            (r'\b(almost gone|nearly sold out|going fast)\b',       0.78, "Scarcity language"),
        ]
        for pattern, score, label in rules:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Find the actual line containing this match for evidence
                for line in text.splitlines():
                    if re.search(pattern, line, re.IGNORECASE):
                        found_evidence.append(line.strip())
                base_score = max(base_score, score)

    elif pattern_id == "DP03":   # Confirm Shaming
        rules = [
            (r"no[,\s]+thanks?[,\s]+i\s+(hate|don'?t\s+want|prefer\s+not)",  0.92, "Shame on decline"),
            (r"no[,\s]+i\s+don'?t\s+want\s+(free|discount|savings?)",         0.90, "Shame on free offer"),
            (r"(skip|decline|no)\b.{0,40}(hate|don'?t\s+want|refuse|miss)",   0.85, "Shame language on CTA"),
            (r"i\s+prefer\s+paying\s+more",                                   0.95, "Extreme shame"),
            (r"no[,\s]+i\s+(don'?t|do\s+not)\s+(need|want)\s+(protection|coverage|deal)", 0.88, "Shame on protection"),
        ]
        for pattern, score, label in rules:
            for line in text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    found_evidence.append(line.strip())
                    base_score = max(base_score, score)

    elif pattern_id == "DP04":   # Forced Action
        rules = [
            (r'\bshare\s+with\s+\d+\s+friends?\b',                          0.90, "Forced social sharing"),
            (r'\b(must|required|mandatory)\s+(create|sign\s+up|register)\b', 0.85, "Forced registration"),
            (r'\bdownload\s+(our|the)\s+app\b',                              0.75, "Forced app download"),
            (r'\benter\s+your\s+(phone|mobile|number)\s+to\b',              0.80, "Forced phone number"),
            (r'\b(create|sign\s+up|register)\s+to\s+(continue|proceed|checkout)\b', 0.82, "Forced account"),
            (r'\bto\s+unlock\s+(this|the)\s+(price|offer|deal)\b',          0.88, "Forced unlock action"),
        ]
        for pattern, score, label in rules:
            for line in text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    found_evidence.append(line.strip())
                    base_score = max(base_score, score)

    elif pattern_id == "DP11":   # Trick Question
        rules = [
            (r'(uncheck|deselect)\b.{0,50}\bnot\b',                           0.88, "Confusing double negative"),
            (r'\bnot\b.{0,30}\bnot\b.{0,30}(receive|send|share)',             0.92, "Triple negative confusion"),
            (r'(check|tick)\b.{0,50}(prevent|stop)\b.{0,30}not',              0.85, "Confusing prevent-not"),
            (r'(uncheck|deselect)\b.{0,30}(wish|want)\b.{0,20}not',           0.90, "Uncheck-not confusion"),
            (r'do not.{0,30}(uncheck|deselect)',                               0.85, "Do not uncheck confusion"),
        ]
        for pattern, score, label in rules:
            for line in text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    found_evidence.append(line.strip())
                    base_score = max(base_score, score)

    elif pattern_id == "DP09":   # Disguised Ads
        rules = [
            (r'\[sponsored\]',                            0.70, "Labeled but potentially hidden sponsored tag"),
            (r'(top\s+picks?|recommended\s+for\s+you).{0,100}paid', 0.88, "Organic-looking paid section"),
            (r'(all|every)\s+(item|link|product)s?\s+(is|are)\s+paid', 0.95, "Explicit paid placement disclosure"),
            (r'(?:editorial|organic).{0,50}(?:paid|sponsored)',        0.90, "Ad in organic context"),
        ]
        for pattern, score, label in rules:
            for line in text.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    found_evidence.append(line.strip())
                    base_score = max(base_score, score)

    # Deduplicate evidence
    found_evidence = list(dict.fromkeys(found_evidence))[:5]

    return {
        "pattern_id":     pattern_id,
        "rule_based_hit": len(found_evidence) > 0,
        "base_confidence": round(base_score, 2),
        "evidence_lines":  found_evidence,
        "note":            "LLM should confirm/refine this. Rules give initial signals only."
    }


# ── System Prompt ──────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    pattern_list = "\n".join(
        f"  • {pid}: {defn['name']} — {defn['description'][:120]}..."
        for pid, defn in PATTERN_DEFINITIONS.items()
    )
    return f"""You are the NLP Agent in Dark Guard AI, an autonomous system that detects 
deceptive design patterns on websites to protect users.

YOUR JOB:
Analyze the provided webpage text and detect ONLY these 5 dark patterns:

{pattern_list}

YOUR ANALYSIS PROCESS — follow this exact sequence:
1. Call extract_high_risk_lines first to get focused suspicious text
2. For each suspected pattern, call get_pattern_definition to load its signals
3. Call scan_text_for_pattern for each of the 5 patterns  
4. Review ALL evidence carefully — only report patterns with genuine evidence
5. Call finalize_detections ONCE with your complete findings

CONFIDENCE SCORING RULES:
- 0.85–1.00 = Clear, textbook example of the pattern, unmistakable
- 0.65–0.84 = Strong signals, highly likely but minor ambiguity
- 0.45–0.64 = Possible pattern, needs user awareness
- Below 0.45 = Do NOT report — too ambiguous

EVIDENCE RULES:
- Evidence must be EXACT quotes from the input text
- Each detection needs at least 1 piece of direct textual evidence
- Do not infer patterns that aren't grounded in specific text

IMPORTANT:
- A page with zero dark patterns is perfectly valid — report 0 if that's the truth
- Do not hallucinate patterns — every detection must have textual proof
- Be strict: borderline cases should NOT be reported
- Always call finalize_detections as your last action
"""


# ── Main Agent Runner ──────────────────────────────────────────────────────

async def run_nlp_agent(text: str, verbose: bool = True) -> Dict:
    """
    Run the NLP agent on webpage text.

    Args:
        text:    Full webpage text content to analyze
        verbose: If True, print step-by-step agent activity

    Returns:
        Dict with detections list and summary
    """
    from utils.output_formatter import print_agent_step, console

    if verbose:
        print_agent_step("NLP Agent starting analysis")
        print_agent_step("Preparing text", f"({len(text)} characters)")

    prompt = (
        f"{_build_system_prompt()}\n\n"
        f"Analyze the following webpage text for dark patterns.\n\n"
        f"=== WEBPAGE TEXT START ===\n"
        f"{text}\n"
        f"=== WEBPAGE TEXT END ===\n\n"
        f"Output ONLY valid JSON with 'detections' (list of detected patterns) and 'summary' (one-sentence summary). "
        f"Do not include any other text."
    )

    attempts = 0
    while True:
        try:
            if GOOGLE_GENAI_PACKAGE == "genai":
                response = client.models.generate_content(
                    model=settings.nlp_agent_model,
                    contents=prompt,
                )
                final_text = getattr(response, "text", None) or str(response)
            elif GOOGLE_GENAI_PACKAGE == "generativeai":
                model = client.GenerativeModel(settings.nlp_agent_model)
                response = model.generate_content(prompt)
                final_text = getattr(response, "text", None) or str(response)
            else:
                raise RuntimeError(
                    "No supported Google GenAI API surface found. "
                    "Install google-genai or use a supported google.generativeai version."
                )
            break
        except Exception as exc:
            attempts += 1
            if _is_quota_error(exc):
                retry_delay = _extract_retry_delay_seconds(exc)
                if retry_delay is not None and attempts <= 1:
                    await asyncio.sleep(retry_delay)
                    continue
                raise RuntimeError(
                    "Gemini quota exhausted for the NLP Agent. "
                    "Please retry after the rate-limit window or use a lower-traffic model."
                ) from exc
            if _is_service_unavailable_error(exc):
                if attempts <= 1:
                    await asyncio.sleep(3)
                    continue
                raise RuntimeError(
                    "Gemini is temporarily unavailable for the NLP Agent. "
                    "Please retry in a little while."
                ) from exc
            if _is_permission_denied_error(exc):
                raise RuntimeError(
                    "Gemini access was denied for the NLP Agent. "
                    "Please verify that your API key is valid and that the linked Google project has Gemini API access enabled."
                ) from exc
            raise

    final_result = _parse_fallback_response(final_text)
    return final_result


def _default_prevention(pattern_id: str) -> str:
    """Default prevention advice if the agent didn't provide one."""
    defaults = {
        "DP01": "Ignore countdown timers. Open the product in an incognito tab — if the timer resets, it's fake. Take your time.",
        "DP03": "The 'decline' button is equally valid. Rephrase it mentally: 'No thanks, I'll skip this offer' is a completely normal choice.",
        "DP04": "Look for a 'Guest Checkout' or 'Continue without account' option. Use a temporary email if signup is truly required.",
        "DP09": "Look for 'Sponsored' or 'Ad' labels. Install an ad blocker (uBlock Origin). Assume any 'Recommended' section may be paid.",
        "DP11": "Read the checkbox label twice. Cover negative words and reread. When in doubt, leave pre-checked boxes unchecked.",
    }
    return defaults.get(pattern_id, "Proceed with caution and review this section carefully.")


def _parse_fallback_response(text: str) -> dict:
    """Parse agent response if it ended without calling finalize_detections."""
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            return {
                "detections": data.get("detections", []),
                "summary":    data.get("summary", "Parsed from agent response")
            }
    except Exception:
        pass
    return {"detections": [], "summary": "Could not parse agent response"}
