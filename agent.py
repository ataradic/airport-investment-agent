"""Conversational agent: Gemini with automatic function calling over tools.py.

The LLM understands the question, picks tools and explains results. It never computes scores.
Environment: GEMINI_API_KEY (required), GEMINI_MODEL (optional; verify the name is valid for your account).
"""
import functools
import os

from google import genai
from google.genai import types

import tools
from prompts import SYSTEM_PROMPT

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
TEMPERATURE = 0.2

_CLIENT = None  # module-level reference: if the client is garbage-collected, the SDK closes its HTTP connection
TOOL_LOG = []   # filled on every tool call so the UI can show what the agent did


def _with_logging(tool):
    """Wrap a tool so every call is recorded in TOOL_LOG (name, arguments, result)."""
    @functools.wraps(tool)
    def wrapper(*args, **kwargs):
        result = tool(*args, **kwargs)
        TOOL_LOG.append({"tool": tool.__name__, "args": kwargs or list(args), "result": result})
        return result
    return wrapper


def _get_client():
    """Create the Gemini client once and keep a reference to it."""
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def _build_config():
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_with_logging(tool) for tool in tools.TOOLS],
        temperature=TEMPERATURE,
    )


def create_chat():
    """Start a chat session that keeps the conversation history for follow-up questions."""
    return _get_client().chats.create(model=MODEL_NAME, config=_build_config())


def _friendly_error(exc: Exception) -> str:
    """Readable message for the most common API failures."""
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return ("The AI service quota is exhausted. The deterministic tools still work "
                "(see 'Tools used'). Try again later or enable billing.")
    return f"Sorry, the AI service failed: {exc}"


def ask(chat, question: str):
    """Send a question. Returns (answer_text, tool_calls_made)."""
    TOOL_LOG.clear()
    try:
        response = chat.send_message(question)
        answer = response.text or "The model returned an empty answer. Please try again."
    except Exception as exc:  # network, quota, bad model name, etc.
        answer = _friendly_error(exc)
    return answer, list(TOOL_LOG)
