"""Streamlit chat UI. Run with: streamlit run app.py"""
import json

import streamlit as st

import agent
import data

st.set_page_config(page_title="Airport Investment Intelligence Agent", page_icon="✈️", layout="wide")
st.title("✈️ Airport Investment Intelligence Agent")

try:
    meta = data.get_meta()
except data.DataUnavailable as exc:
    st.error(f"Data could not be loaded: {exc}")
    st.stop()
st.info(f"Data: BTS T-100 (data.transportation.gov), {meta['base_year']} vs {meta['latest_year']}, "
        f"fetched {meta['fetched_at'][:10]} ({meta['quality']}). No delay data; long-haul % is approximated by proxies.")
st.caption("Scores are computed deterministically in code; the AI only interprets questions and explains results. "
           "'Unmet demand' is an indirect proxy, not a measured value.")

if "chat" not in st.session_state:
    try:
        st.session_state.chat = agent.create_chat()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("calls"):
            with st.expander("Tools used"):
                st.code(json.dumps(m["calls"], indent=2, default=str), language="json")

if question := st.chat_input("e.g. Which airports in New England are strong candidates for terminal expansion?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            answer, calls = agent.ask(st.session_state.chat, question)
        st.markdown(answer)
        if calls:
            with st.expander("Tools used"):
                st.code(json.dumps(calls, indent=2, default=str), language="json")
    st.session_state.messages.append({"role": "assistant", "content": answer, "calls": calls})