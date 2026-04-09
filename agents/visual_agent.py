# agents/visual_agent.py

import importlib
import json
import re
import time
from typing import Dict, List
from config import get_settings
from agents.visual_pattern_definitions import VISUAL_PATTERN_DEFINITIONS
from utils.image_processor import ImageProcessor

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


from collections.abc import Iterable, Mapping


def _get_content_types():
    if GOOGLE_GENAI_PACKAGE == "generativeai":
        try:
            module = importlib.import_module("google.generativeai.types")
        except ImportError:
            module = importlib.import_module("google.generativeai")
        return getattr(module, "content_types")

    if GOOGLE_GENAI_PACKAGE == "genai":
        try:
            module = importlib.import_module("google.genai.types")
        except ImportError:
            module = importlib.import_module("google.genai")
        if hasattr(module, "content_types"):
            return getattr(module, "content_types")
        return getattr(module, "types").content_types

    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


def _normalize_data(value):
    try:
        from google.protobuf.json_format import MessageToDict
        from google.protobuf.message import Message
    except ImportError:
        Message = None
        MessageToDict = None

    if Message is not None and isinstance(value, Message):
        try:
            return MessageToDict(value, preserving_proto_field_name=True)
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {k: _normalize_data(v) for k, v in value.items()}

    if isinstance(value, (str, bytes, bytearray)):
        return value

    if isinstance(value, Iterable):
        return [_normalize_data(v) for v in value]

    return value


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


def _extract_retry_delay_seconds(exc) -> int | None:
    message = str(exc)
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", message, re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    return None


def _send_chat_message(chat, content):
    try:
        return chat.send_message(content)
    except Exception as exc:
        if _is_quota_error(exc):
            raise RuntimeError(
                "Gemini quota exhausted. Please retry later or check your Google Cloud quota."
            ) from exc
        raise


def _generate_visual_response(prompt: str, pil_image, *, max_retries: int = 1) -> str:
    attempts = 0
    while True:
        try:
            if GOOGLE_GENAI_PACKAGE == "genai":
                response = client.models.generate_content(
                    model=settings.visual_agent_model,
                    contents=[prompt, pil_image],
                )
            elif GOOGLE_GENAI_PACKAGE == "generativeai":
                model = genai.GenerativeModel(settings.visual_agent_model)
                response = model.generate_content([prompt, pil_image])
            else:
                raise RuntimeError(
                    "No supported Google GenAI API surface found. "
                    "Install google-genai or use a supported google.generativeai version."
                )

            return getattr(response, "text", None) or str(response)
        except Exception as exc:
            attempts += 1
            if _is_quota_error(exc):
                retry_delay = _extract_retry_delay_seconds(exc)
                if retry_delay is not None and attempts <= max_retries:
                    time.sleep(retry_delay)
                    continue
                raise RuntimeError(
                    "Gemini quota exhausted for the Visual Agent. "
                    "Please retry after the rate-limit window or use a lower-traffic model."
                ) from exc
            if _is_service_unavailable_error(exc):
                if attempts <= max_retries:
                    time.sleep(3)
                    continue
                raise RuntimeError(
                    "Gemini is temporarily unavailable for the Visual Agent. "
                    "Please retry in a little while."
                ) from exc
            raise


def _finalize_visual_result(parsed: dict) -> dict:
    detections = _normalize_data(parsed.get("detections", []))
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
        "detections": detections,
        "image_description": parsed.get("image_description", ""),
        "summary": parsed.get("summary", "Parsed from response"),
    }


def _create_visual_model(**kwargs):
    if GOOGLE_GENAI_PACKAGE == "generativeai":
        return genai.GenerativeModel(**kwargs)
    if GOOGLE_GENAI_PACKAGE == "genai":
        if hasattr(client, "GenerativeModel"):
            return client.GenerativeModel(**kwargs)
        if hasattr(genai, "GenerativeModel"):
            return genai.GenerativeModel(**kwargs)
        raise RuntimeError(
            "The installed google.genai package does not expose GenerativeModel. "
            "Install google-generativeai or upgrade google-genai to a newer version "
            "that supports the Visual Agent API."
        )
    raise RuntimeError(
        "No supported Google GenAI API surface found. "
        "Install google-genai or use a supported google.generativeai version."
    )


# ── Visual Agent Tools ─────────────────────────────────────────────────────
# These are described to Gemini as function declarations.
# Gemini decides when to call each one during its analysis loop.

VISUAL_AGENT_TOOLS = [
    {
        "name": "get_visual_pattern_definition",
        "description": (
            "Get the full definition, visual signals, and examples for a specific "
            "visual dark pattern. Call this to understand exactly what to look for "
            "before analyzing the image for that pattern."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern_id": {
                    "type":        "string",
                    "enum":        ["DP06", "DP09", "DP13"],
                    "description": "The dark pattern ID to look up"
                }
            },
            "required": ["pattern_id"]
        }
    },
    {
        "name": "analyze_image_region",
        "description": (
            "Analyze a specific region or element type in the image for dark pattern signals. "
            "Use this to focus on specific parts: buttons, checkboxes, ads, download buttons, "
            "dialogs, banners, labels, etc. "
            "Call this multiple times to examine different regions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "region_type": {
                    "type":        "string",
                    "enum":        [
                        "buttons_and_ctas",
                        "checkboxes_and_forms",
                        "advertisements_and_banners",
                        "download_elements",
                        "popups_and_modals",
                        "labels_and_text",
                        "navigation_and_layout",
                        "full_page_overview"
                    ],
                    "description": "Which region or element type to focus analysis on"
                },
                "pattern_to_check": {
                    "type":        "string",
                    "enum":        ["DP06", "DP09", "DP13", "all"],
                    "description": "Which dark pattern to look for in this region"
                }
            },
            "required": ["region_type", "pattern_to_check"]
        }
    },
    {
        "name": "finalize_visual_detections",
        "description": (
            "Submit your final list of detected visual dark patterns. "
            "Call this ONCE after you have analyzed all relevant regions. "
            "Only include patterns you have clear visual evidence for."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "detections": {
                    "type":        "array",
                    "description": "List of confirmed dark pattern detections",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pattern_id": {
                                "type":        "string",
                                "description": "e.g. DP06"
                            },
                            "pattern_name": {
                                "type":        "string",
                                "description": "e.g. Interface Interference"
                            },
                            "confidence": {
                                "type":        "number",
                                "description": "0.0 to 1.0"
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["high", "medium", "low"]
                            },
                            "visual_evidence": {
                                "type":        "array",
                                "description": "List of specific visual elements you observed",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "element":     {"type": "string",
                                                        "description": "What UI element (button, checkbox, banner, etc.)"},
                                        "observation": {"type": "string",
                                                        "description": "Exactly what you see that is deceptive"},
                                        "location":    {"type": "string",
                                                        "description": "Where in the image (top-left, center, bottom, etc.)"}
                                    }
                                }
                            },
                            "explanation": {
                                "type":        "string",
                                "description": "Why this constitutes a dark pattern"
                            },
                            "prevention": {
                                "type":        "string",
                                "description": "What the user should do to protect themselves"
                            }
                        },
                        "required": [
                            "pattern_id", "pattern_name", "confidence",
                            "visual_evidence", "explanation"
                        ]
                    }
                },
                "image_description": {
                    "type":        "string",
                    "description": "Brief description of what the screenshot shows overall"
                },
                "summary": {
                    "type":        "string",
                    "description": "One sentence: how many patterns found and what types"
                }
            },
            "required": ["detections", "summary"]
        }
    }
]


# ── Tool Executor ──────────────────────────────────────────────────────────

def execute_visual_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Execute a visual agent tool call.
    Note: analyze_image_region is handled specially — it triggers
    a second Gemini call with the image to do focused analysis.
    """

    if tool_name == "get_visual_pattern_definition":
        pid  = tool_input.get("pattern_id")
        defn = VISUAL_PATTERN_DEFINITIONS.get(pid, {})
        return {
            "pattern_id":          pid,
            "name":                defn.get("name", ""),
            "description":         defn.get("description", ""),
            "visual_signals":      defn.get("visual_signals", []),
            "what_to_look_for":    defn.get("what_to_look_for", []),
            "examples_description": defn.get("examples_description", []),
        }

    elif tool_name == "analyze_image_region":
        # Actual image analysis is done inside the agent loop
        # This just returns a routing result — the main loop handles it
        return {
            "status":   "image_analysis_requested",
            "region":   tool_input.get("region_type"),
            "pattern":  tool_input.get("pattern_to_check"),
        }

    elif tool_name == "finalize_visual_detections":
        # Terminal tool — signals end of loop
        detections = _normalize_data(tool_input.get("detections", []))
        for det in detections:
            if "risk_level" not in det:
                conf = det.get("confidence", 0)
                det["risk_level"] = (
                    "high"   if conf >= 0.80 else
                    "medium" if conf >= 0.55 else
                    "low"
                )
            if "prevention" not in det:
                det["prevention"] = _default_prevention(det.get("pattern_id", ""))
        return {
            "status":     "finalized",
            "count":      len(detections),
            "detections": detections,
        }

    return {"error": f"Unknown tool: {tool_name}"}


# ── System Prompt ──────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    pattern_list = "\n".join(
        f"  • {pid}: {defn['name']} — {defn['description'][:130]}..."
        for pid, defn in VISUAL_PATTERN_DEFINITIONS.items()
    )
    return f"""You are the Visual Agent in Dark Guard AI, an autonomous system that detects 
deceptive design patterns in website screenshots to protect users.

YOUR JOB:
Analyze the provided screenshot and detect ONLY these 3 visual dark patterns:

{pattern_list}

YOUR ANALYSIS PROCESS — follow this exact sequence:
1. Call get_visual_pattern_definition for each of the 3 patterns to understand signals
2. Call analyze_image_region focusing on different element types:
   - Start with full_page_overview to understand the overall layout
   - Then buttons_and_ctas (for Interface Interference)
   - Then checkboxes_and_forms (for Interface Interference)
   - Then advertisements_and_banners (for Disguised Ads)
   - Then download_elements (for Rogue/Malicious)
   - Then popups_and_modals (for all three)
3. Assess what you actually observed in the image
4. Call finalize_visual_detections ONCE with confirmed findings

CONFIDENCE SCORING:
- 0.85–1.00 = Unmistakably clear visual evidence, textbook example
- 0.65–0.84 = Strong visual signals, highly likely dark pattern
- 0.45–0.64 = Possible, worth flagging for user awareness  
- Below 0.45 = Do NOT report — too ambiguous

EVIDENCE RULES:
- visual_evidence must describe EXACTLY what you SEE in the image
- Describe element type, its visual characteristics, and location
- Do not infer — only report what is visually present
- A clean screenshot with 0 detections is a valid result

IMPORTANT:
- Always call finalize_visual_detections as your last action
- Be specific about WHERE in the image the dark pattern appears
- Include color, size, contrast, and position in your observations
"""


# ── Focused Region Analysis ────────────────────────────────────────────────

def _analyze_region_with_gemini(
    image_data: dict,
    region_type: str,
    pattern_to_check: str,
    model
) -> str:
    """
    Run a focused Gemini vision call on a specific region/element type.
    Returns a text description of what the model observes.
    """

    region_prompts = {
        "full_page_overview": (
            "Describe the overall layout of this screenshot. What type of page is it "
            "(e-commerce product page, checkout, download site, news site, etc.)? "
            "What are the main sections? Are there any obviously suspicious elements?"
        ),
        "buttons_and_ctas": (
            "Focus ONLY on buttons and call-to-action elements. "
            "Describe: their labels, colors, sizes, and visual prominence. "
            "Are positive actions (buy, accept, subscribe) styled differently from "
            "negative actions (decline, cancel, no thanks)? "
            "Is there a color hierarchy that favors one choice over another? "
            "Are any buttons hidden, tiny, or low-contrast?"
        ),
        "checkboxes_and_forms": (
            "Focus ONLY on checkboxes, radio buttons, and form elements. "
            "Describe each checkbox: its label text, whether it appears checked or unchecked, "
            "whether it appears pre-selected by default, and whether its label is clear. "
            "Are any checkboxes hard to see or understand?"
        ),
        "advertisements_and_banners": (
            "Focus ONLY on advertisement areas, banners, and 'recommended' sections. "
            "Are any ads labeled? How visible is the 'Sponsored' or 'Ad' label — "
            "describe its font size, color, and contrast. "
            "Do any ads look identical to organic content? "
            "Are there sections labeled 'Recommended', 'Top Picks', or 'You May Also Like' "
            "that might be paid placements without disclosure?"
        ),
        "download_elements": (
            "Focus ONLY on download buttons, play buttons, and action triggers. "
            "How many download buttons are visible? Describe each one's color, size, label. "
            "Do any buttons look like native OS/browser dialogs? "
            "Are there any fake system alerts, virus warnings, or prize notifications? "
            "Do any 'Play' buttons look like they belong to embedded ads rather than real videos?"
        ),
        "popups_and_modals": (
            "Focus ONLY on any overlays, modals, popups, cookie banners, or notification prompts. "
            "Describe: how prominent they are, how easy or hard it is to dismiss them, "
            "whether the close/X button is visible and large enough, "
            "whether accept is much more prominent than reject, "
            "and whether the popup could be mistaken for a real system notification."
        ),
        "labels_and_text": (
            "Focus ONLY on small print, labels, and disclosure text. "
            "Is there any text that is unusually small or low-contrast? "
            "Are there asterisks (*) referring to important conditions in tiny text? "
            "Is any important information hidden through formatting?"
        ),
        "navigation_and_layout": (
            "Focus ONLY on the navigation and overall layout. "
            "Are there any elements that seem out of place or designed to confuse? "
            "Is the visual hierarchy manipulative — does it draw attention away from "
            "important information or choices?"
        ),
    }

    pattern_context = {
        "DP06": "You are specifically looking for Interface Interference — deceptive UI design.",
        "DP09": "You are specifically looking for Disguised Ads — ads that look like organic content.",
        "DP13": "You are specifically looking for Rogue/Malicious patterns — fake dialogs and deceptive downloads.",
        "all":  "Look for any of the three dark patterns: Interface Interference, Disguised Ads, or Rogue/Malicious.",
    }

    focus_prompt   = region_prompts.get(region_type, "Describe what you see in this region.")
    pattern_prompt = pattern_context.get(pattern_to_check, "")

    full_prompt = (
        f"Analyzing screenshot region: {region_type.replace('_', ' ').upper()}\n"
        f"{pattern_prompt}\n\n"
        f"{focus_prompt}\n\n"
        f"Be specific and descriptive. Describe exact colors, sizes, positions, and text you observe."
    )

    import PIL.Image
    import io

    pil_image = PIL.Image.open(io.BytesIO(image_data["bytes"]))
    try:
        response = model.generate_content([full_prompt, pil_image])
        return response.text
    except Exception as exc:
        if _is_quota_error(exc):
            raise RuntimeError(
                "Gemini quota exhausted while analyzing the image region. "
                "Please retry later or reduce the number of API calls."
            ) from exc
        raise


# ── Main Agent Runner ──────────────────────────────────────────────────────

def run_visual_agent(image_path: str, verbose: bool = True) -> Dict:
    """
    Run the Visual Agent on a screenshot image.

    Args:
        image_path: Path to the screenshot file (.png, .jpg, etc.)
        verbose:    Print step-by-step agent activity

    Returns:
        Dict with detections list, image_description, and summary
    """
    from rich.console import Console
    console = Console()

    def step(msg, detail=""):
        if verbose:
            console.print(f"  [bold blue]→[/bold blue] {msg}", end="")
            if detail:
                console.print(f" [dim]{detail}[/dim]", end="")
            console.print()

    step("Visual Agent starting")
    step("Loading image", image_path)

    # ── Load and preprocess image ──────────────────────────────────────────
    processor  = ImageProcessor()
    image_data = processor.load_and_prepare(image_path)
    info       = image_data["info"]
    step("Image loaded", f"{info['width']}×{info['height']}px | {info['size_kb']}KB")

    import PIL.Image
    import io

    pil_image = PIL.Image.open(io.BytesIO(image_data["bytes"]))
    step("Running single-pass visual analysis")

    prompt = (
        f"{_build_system_prompt()}\n\n"
        "Analyze this website screenshot for visual dark patterns and return ONLY valid JSON.\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "detections": [\n'
        "    {\n"
        '      "pattern_id": "DP06|DP09|DP13",\n'
        '      "pattern_name": "string",\n'
        '      "confidence": 0.0,\n'
        '      "risk_level": "high|medium|low",\n'
        '      "visual_evidence": [\n'
        '        {"element": "string", "observation": "string", "location": "string"}\n'
        "      ],\n"
        '      "explanation": "string",\n'
        '      "prevention": "string"\n'
        "    }\n"
        "  ],\n"
        '  "image_description": "string",\n'
        '  "summary": "string"\n'
        "}\n\n"
        "Rules:\n"
        "- Detect ONLY DP06, DP09, and DP13.\n"
        "- If there is no clear evidence, return an empty detections array.\n"
        "- Base claims only on visible elements in the screenshot.\n"
        "- Keep visual_evidence concrete and location-specific.\n"
        "- Output JSON only, with no markdown fences."
    )

    try:
        response_text = _generate_visual_response(prompt, pil_image)
    except RuntimeError as exc:
        step("Quota error", "Visual analysis request failed")
        return {
            "detections":        [],
            "image_description": "",
            "summary":           "Visual agent failed due to API quota or service error.",
            "error":             str(exc)
        }

    step("Analysis complete", "Parsing model response")
    return _finalize_visual_result(_parse_gemini_response(response_text))


# ── Helpers ────────────────────────────────────────────────────────────────

def _default_prevention(pattern_id: str) -> str:
    defaults = {
        "DP09": (
            "Look for 'Sponsored', 'Ad', or 'Promoted' labels before clicking any "
            "'recommended' content. Install uBlock Origin. Assume any 'Top Picks' "
            "or 'Recommended for you' section may be paid advertising."
        ),
        "DP06": (
            "Before submitting any form, manually uncheck all pre-checked checkboxes. "
            "Look for the least prominent button — it's often the one you actually want. "
            "Read all labels twice before clicking Accept or Confirm."
        ),
        "DP13": (
            "Do NOT click any button on this page. Close the tab immediately. "
            "If you clicked something, run a malware scan. "
            "Real software never requires you to click a webpage button to install updates."
        ),
    }
    return defaults.get(pattern_id, "Proceed with extreme caution on this page.")


def _parse_gemini_response(text: str) -> dict:
    """Fallback parser if agent ends without calling finalize."""
    try:
        # Try to find JSON in the response
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            return {
                "detections":        data.get("detections", []),
                "image_description": data.get("image_description", ""),
                "summary":           data.get("summary", "Parsed from response")
            }
    except Exception:
        pass
    return {
        "detections":        [],
        "image_description": "Could not parse",
        "summary":           "Agent did not call finalize_detections"
    }
