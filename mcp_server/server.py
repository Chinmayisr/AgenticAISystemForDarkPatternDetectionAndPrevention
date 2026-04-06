# mcp_server/server.py

import asyncio
import json
import websockets
from typing import Any
from config import get_settings
from mcp_server.tools.nlp_tools import classify_text
from mcp_server.tools.visual_tools import analyze_image
from mcp_server.tools.pricing_tools import compare_prices
from mcp_server.tools.behavioral_tools import check_behavioral_event
from storage.session_store import SessionStore
from storage.detection_log import DetectionLog
from utils.logger import get_logger

logger = get_logger(__name__)
session_store = SessionStore()
detection_log = DetectionLog()


# ── Tool Registry ────────────────────────────────────────────────────────────
# This maps tool names (what agents call) to actual Python functions.
# Every tool an agent can call must be registered here.

TOOL_REGISTRY = {
    "classify_text_pattern":      classify_text,
    "analyze_image_for_patterns": analyze_image,
    "compare_prices":             compare_prices,
    "check_behavioral_pattern":   check_behavioral_event,
}

# ── Tool Schemas (what agents see when they decide which tool to call) ────────
TOOL_SCHEMAS = [
    {
        "name": "classify_text_pattern",
        "description": "Classify text for dark patterns. Returns labels and confidence scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text":    {"type": "string"},
                "context": {"type": "string"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "analyze_image_for_patterns",
        "description": "Analyze base64 image for visual dark patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_base64":       {"type": "string"},
                "image_description":  {"type": "string"}
            },
            "required": ["image_base64"]
        }
    },
    {
        "name": "compare_prices",
        "description": "Store and compare prices across checkout funnel stages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "stage":      {"type": "string",
                               "enum": ["product_page", "cart", "checkout", "payment"]},
                "price_data": {"type": "object"}
            },
            "required": ["session_id", "stage", "price_data"]
        }
    },
    {
        "name": "check_behavioral_pattern",
        "description": "Check cart and popup events for behavioral dark patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id":  {"type": "string"},
                "event_type":  {"type": "string",
                                "enum": ["cart_change", "popup_appeared"]},
                "event_data":  {"type": "object"}
            },
            "required": ["session_id", "event_type", "event_data"]
        }
    },
]


# ── MCP Message Handler ───────────────────────────────────────────────────────
async def handle_mcp_message(message: dict, session_id: str) -> dict:
    """
    Processes an incoming MCP protocol message and routes it to the right handler.
    MCP message types: initialize | tools/list | tools/call | resources/read
    """
    msg_type = message.get("method", "")

    if msg_type == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "dark-guard-mcp", "version": "1.0.0"}
            }
        }

    elif msg_type == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"tools": TOOL_SCHEMAS}
        }

    elif msg_type == "tools/call":
        tool_name  = message["params"]["name"]
        tool_input = message["params"].get("arguments", {})
        tool_input["session_id"] = session_id

        if tool_name in TOOL_REGISTRY:
            try:
                result = await TOOL_REGISTRY[tool_name](tool_input)
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                }
            except Exception as e:
                logger.error(f"Tool {tool_name} error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32000, "message": str(e)}
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            }

    elif msg_type == "resources/read":
        resource_uri = message["params"].get("uri", "")
        if resource_uri == "session://current":
            data = session_store.get_session(session_id)
        else:
            data = {"error": "Unknown resource"}
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"contents": [{"uri": resource_uri, "text": json.dumps(data)}]}
        }

    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "error": {"code": -32601, "message": f"Unknown method: {msg_type}"}
    }


# ── WebSocket Server ──────────────────────────────────────────────────────────
async def websocket_handler(websocket):
    """Handle a single WebSocket connection from the browser extension or agents."""
    settings = get_settings()
    session_id = session_store.new_session()
    logger.info(f"New connection. Session: {session_id}")

    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                response = await handle_mcp_message(message, session_id)
                await websocket.send(json.dumps(response))
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"}
                }))
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed. Session: {session_id}")


async def start_server():
    settings = get_settings()
    async with websockets.serve(websocket_handler, settings.mcp_host, settings.mcp_port):
        logger.info(f"✅ MCP Server running at ws://{settings.mcp_host}:{settings.mcp_port}")
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(start_server())