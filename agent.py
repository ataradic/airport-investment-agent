"""Conversational agent: Gemini with automatic function calling over tools.py.

The LLM understands the question, picks tools and explains results. It never computes scores.
Set GEMINI_API_KEY, and optionally GEMINI_MODEL (verify the model name is valid for your account).
"""
import functools
import os

from google import genai
from google.genai import types

import tools

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_PROMPT = """You are an Airport Investment Intelligence Agent helping analysts screen US airports for
modernization investment (terminal expansion, capacity upgrades).

Rules:
1. Every number you state MUST come from a tool result. Never use memorised figures. Call tools for each question.
2. Separate FACTS (from tools), ASSUMPTIONS (from the 'assumptions' field) and CONCLUSIONS (your reasoning).
3. Always surface the tool 'warnings'. If data is placeholder, say so clearly.
4. 'Unmet demand' is only a proxy index. Never present it as a measured quantity.
5. Say what you cannot assess (costs, returns, regulation) instead of guessing.
6. Mappings: 'LA' -> LAX, 'Santa Ana' -> SNA, 'Anchorage' -> ANC, 'San Francisco' -> SFO,
   'New England' -> region 'new england'.
7. Reply in the user's language. Be concise and explain the reasoning behind rankings using score contributions.
8. If the question is unrelated to airports or aviation investment, politely decline and explain your scope.
9. Answer the metric that was asked about. Mention the total score only if the user asks for it or for a ranking.
10. Scores are RELATIVE rankings inside a small dataset. Say "ranked first by screening score", not "strong candidate" or
    "severe pressure". If raw growth is negative, say so explicitly. If the tool flags a difference as small, say they are roughly equal.
11. For "why" questions, explain only using the components returned by tools and say that real causes cannot be determined from this data.
12. Never add facts about specific airports from your own knowledge (runways, noise rules, history), including in the
    'cannot be assessed' section. That section lists only generic missing information: costs, returns, regulation, physical constraints.
13. On-time/delay data is not available in this dataset; say so if asked. 'peak' = highest monthly load factor in the latest year;
    'reach' = average flight distance in miles. If asked for long-haul %, explain that only proxies exist (see tool assumptions).
14. Use plain text only. No LaTeX, no $ signs. Write formulas like: load factor = passengers / seats.
"""

_CLIENT = None  # module-level reference: if the client is garbage-collected, the SDK closes its HTTP connection

TOOL_LOG = []  # filled on every tool call so the UI can show what the agent did


def _logged(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        TOOL_LOG.append({"tool": fn.__name__, "args": kwargs or list(args), "result": result})
        return result
    return wrapper


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def create_chat():
    """Create a new chat session that keeps conversation history for follow-up questions."""
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_logged(t) for t in tools.TOOLS],
        temperature=0.2,
    )
    return client.chats.create(model=MODEL_NAME, config=config)


def ask(chat, question: str):
    """Send a question. Returns (answer_text, tool_calls_made)."""
    TOOL_LOG.clear()
    try:
        response = chat.send_message(question)
        return (response.text or "The model returned an empty answer. Please try again."), list(TOOL_LOG)
    except Exception as exc:  # network, quota, bad model name, etc.
        text = str(exc)
        if "429" in text or "RESOURCE_EXHAUSTED" in text:
            return ("The AI service quota is exhausted. The deterministic tools still work "
                    "(see 'Tools used'). Try again later or enable billing."), list(TOOL_LOG)
        return f"Sorry, the AI service failed: {exc}", list(TOOL_LOG)