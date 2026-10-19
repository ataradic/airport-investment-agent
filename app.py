"""Streamlit chat UI. Run with: streamlit run app.py"""
import json

import streamlit as st

import agent
import data

PLACEHOLDER_QUESTION = "e.g. Which airports in New England are strong candidates for terminal expansion?"


def render_header() -> None:
    st.set_page_config(page_title="Airport Investment Intelligence Agent", page_icon="✈️", layout="wide")
    st.title("✈️ Airport Investment Intelligence Agent")


def render_data_banner() -> None:
    """Show where the data comes from, or stop the app if it cannot be loaded."""
    try:
        meta = data.get_meta()
    except data.DataUnavailable as exc:
        st.error(f"Data could not be loaded: {exc}")
        st.stop()
    st.info(f"Data: BTS T-100 (data.transportation.gov), {meta['base_year']} vs {meta['latest_year']}, "
            f"fetched {meta['fetched_at'][:10]} ({meta['quality']}). No delay data; long-haul % is approximated by proxies.")
    st.caption("Scores are computed deterministically in code; the AI only interprets questions and explains results. "
               "'Unmet demand' is an indirect proxy, not a measured value.")


def init_session() -> None:
    """Create the chat session and message history once per browser session."""
    if "chat" in st.session_state:
        return
    try:
        st.session_state.chat = agent.create_chat()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.messages = []


def render_tool_calls(calls: list) -> None:
    if calls:
        with st.expander("Tools used"):
            st.code(json.dumps(calls, indent=2, default=str), language="json")


def render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_tool_calls(message.get("calls"))


def answer_question(question: str) -> None:
    """Show the question, get the agent's answer, show it and store both in the history."""
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            answer, calls = agent.ask(st.session_state.chat, question)
        st.markdown(answer)
        render_tool_calls(calls)
    st.session_state.messages.append({"role": "assistant", "content": answer, "calls": calls})


def main() -> None:
    render_header()
    render_data_banner()
    init_session()
    render_history()
    question = st.chat_input(PLACEHOLDER_QUESTION)
    if question:
        answer_question(question)


main()
