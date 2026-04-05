"""
AI Agent — uses Gemini for reasoning and calls MCP tools dynamically.

Flow
----
1. On startup, fetch the tool catalogue from the MCP server (GET /tools).
2. Accept a user query.
3. Ask Gemini to decide: answer directly OR call a tool (structured JSON).
4. If tool_call → POST /execute on the MCP server, feed result back to Gemini.
5. Return the final natural-language response.

Run
---
    # Terminal 1 — start the MCP server
    python mcp_server.py

    # Terminal 2 — start the agent
    python agent.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils import setup_logging

load_dotenv()

logger = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────────

MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8000")
GEMINI_MODEL = "gemini-2.5-flash"
MAX_TOOL_ROUNDS = 3
MCP_TIMEOUT = 15

# ── MCP client helpers ─────────────────────────────────────────────────


def fetch_tool_catalog() -> list[dict[str, Any]]:
    """GET /tools from the MCP server and return the tool list."""
    resp = requests.get(f"{MCP_BASE_URL}/tools", timeout=MCP_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"MCP /tools failed: {body.get('error')}")
    return body["result"]


def call_mcp_tool(
    tool_name: str, parameters: dict[str, Any], *, retries: int = 2
) -> dict[str, Any]:
    """POST /execute on the MCP server with retry on transient failures."""
    payload = {"tool_name": tool_name, "parameters": parameters}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(
                "MCP call [attempt %d]: %s(%s)", attempt, tool_name, parameters
            )
            resp = requests.post(
                f"{MCP_BASE_URL}/execute",
                json=payload,
                timeout=MCP_TIMEOUT,
            )
            resp.raise_for_status()
            body = resp.json()
            logger.info("MCP result: success=%s", body.get("success"))
            return body
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "MCP call attempt %d failed: %s", attempt, exc
            )
            if attempt < retries:
                time.sleep(1)

    return {"success": False, "error": f"MCP unreachable after {retries} attempts: {last_error}"}


# ── prompt builder ─────────────────────────────────────────────────────


def _build_system_prompt(tools: list[dict[str, Any]]) -> str:
    """Build the system prompt dynamically from the MCP tool catalogue."""
    tool_descriptions = []
    for t in tools:
        params = ", ".join(
            f"{p['name']}: {p['type']}"
            + ("" if p["required"] else f" = {p['default']}")
            for p in t["parameters"]
        )
        tool_descriptions.append(
            f"  - {t['name']}({params}): {t['description']}"
        )
    tool_block = "\n".join(tool_descriptions)

    return f"""\
You are a smart AI agent with access to external tools via an MCP server.

AVAILABLE TOOLS:
{tool_block}

DECISION RULES:
- If the user's question can be answered with your own knowledge, respond directly.
- If the question requires real-time data (weather, currency rates, etc.), call
  the appropriate tool.
- You may call multiple tools in sequence if needed (one per response).

RESPONSE FORMAT — you MUST reply with valid JSON only, no markdown, no extra text.

When you need to call a tool:
{{
  "action": "tool_call",
  "tool_name": "<name>",
  "parameters": {{ ... }}
}}

When you have a final answer (either from your knowledge or after receiving
tool results):
{{
  "action": "respond",
  "message": "<your natural-language answer>"
}}

IMPORTANT:
- Always output raw JSON. Never wrap it in ```json``` blocks.
- After receiving a tool result, ALWAYS respond with {{"action": "respond", ...}}.
- Keep answers concise and practical.
- If the user is asking about travel, assume departure from India unless stated.
- Include budget in INR when relevant.
"""


# ── agent core ─────────────────────────────────────────────────────────


class TravelAgent:
    """ReAct-style agent: Gemini reasons → calls MCP tools → responds."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._tools = fetch_tool_catalog()
        self._system_prompt = _build_system_prompt(self._tools)
        self._history: list[types.Content] = []
        logger.info(
            "Agent initialised with %d tool(s): %s",
            len(self._tools),
            [t["name"] for t in self._tools],
        )

    def chat(self, user_message: str) -> str:
        """Process a user message through the reason → act → respond loop."""
        self._history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        for round_num in range(1, MAX_TOOL_ROUNDS + 1):
            logger.info("─── Agent round %d ───", round_num)
            raw = self._call_gemini()
            decision = self._parse_decision(raw)

            if decision["action"] == "respond":
                final = decision.get("message", raw)
                self._history.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=final)])
                )
                return final

            if decision["action"] == "tool_call":
                tool_name = decision["tool_name"]
                params = decision.get("parameters", {})
                logger.info("Tool call decided: %s(%s)", tool_name, params)

                mcp_result = call_mcp_tool(tool_name, params)

                tool_result_text = (
                    f"Tool '{tool_name}' returned:\n"
                    f"{json.dumps(mcp_result, indent=2)}"
                )
                self._history.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=raw)])
                )
                self._history.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=tool_result_text)])
                )

        fallback = "I wasn't able to complete your request after multiple attempts."
        self._history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=fallback)])
        )
        return fallback

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()
        logger.info("Conversation history cleared.")

    def _call_gemini(self) -> str:
        """Send the current history to Gemini and return the raw text."""
        response = self._client.models.generate_content(
            model=GEMINI_MODEL,
            contents=self._history,
            config=types.GenerateContentConfig(
                system_instruction=self._system_prompt,
                temperature=0.4,
                top_p=0.9,
                max_output_tokens=2048,
            ),
        )
        return response.text.strip()

    @staticmethod
    def _parse_decision(raw: str) -> dict[str, Any]:
        """Parse Gemini's JSON response into an action dict."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            decision = json.loads(cleaned)
            if "action" in decision:
                return decision
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON, treating as direct response.")

        return {"action": "respond", "message": raw}


# ── CLI loop ───────────────────────────────────────────────────────────


def main() -> None:
    setup_logging(logging.DEBUG)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    try:
        requests.get(f"{MCP_BASE_URL}/", timeout=5)
    except requests.ConnectionError:
        print(f"Error: MCP server not reachable at {MCP_BASE_URL}")
        print("Start it first:  python mcp_server.py")
        sys.exit(1)

    agent = TravelAgent(api_key)

    print("\n╔══════════════════════════════════════════════════╗")
    print("║      🤖  Travel Agent  (MCP + Gemini)           ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Type your question. Commands:                  ║")
    print("║    reset  — clear conversation                  ║")
    print("║    tools  — list available MCP tools             ║")
    print("║    exit   — quit                                ║")
    print("╚══════════════════════════════════════════════════╝\n")

    while True:
        try:
            user_input = input("You ➤ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("🔄 Conversation cleared.\n")
            continue
        if user_input.lower() == "tools":
            tools = fetch_tool_catalog()
            print("\n📦 Available MCP tools:")
            for t in tools:
                params = ", ".join(p["name"] for p in t["parameters"])
                print(f"   • {t['name']}({params}) — {t['description']}")
            print()
            continue

        try:
            response = agent.chat(user_input)
            print(f"\n🤖 Agent: {response}\n")
        except Exception as exc:
            logger.error("Agent error: %s", exc, exc_info=True)
            print(f"\n❌ Error: {exc}\n")


if __name__ == "__main__":
    main()
