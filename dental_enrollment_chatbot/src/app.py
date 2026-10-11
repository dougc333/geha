"""Streamlit UI for the GEHA dental enrollment state machine."""

from __future__ import annotations

import os
import uuid

import streamlit as st
from dotenv import load_dotenv

from enrollment_graph import DentalEnrollmentGraph


load_dotenv()
st.set_page_config(page_title="GEHA dental enrollment guide", page_icon="🦷", layout="centered")


@st.cache_resource
def build_graph() -> DentalEnrollmentGraph:
    mode = os.getenv("LLM_EXTRACT", "")  # "1"/"jev", "bedrock", or "compare" (Jev, checked by Bedrock)
    if mode in ("1", "jev"):
        from jev_router import JevExtractor
        # Jev already reads every free-text answer, so skip the old Jev fallback (no double calls).
        return DentalEnrollmentGraph(jev=lambda *_: None, extractor=JevExtractor())
    if mode == "bedrock":
        from llm_extract import BedrockExtractor
        return DentalEnrollmentGraph(extractor=BedrockExtractor())
    if mode == "compare":
        from dual_extract import DualExtractor
        from jev_router import JevExtractor
        from llm_extract import BedrockExtractor
        return DentalEnrollmentGraph(jev=lambda *_: None,
                                     extractor=DualExtractor(JevExtractor(), BedrockExtractor()))
    return DentalEnrollmentGraph()


bot = build_graph()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    prompt, _ = bot.reply("", st.session_state.thread_id)
    st.session_state.messages = [{"role": "assistant", "content": prompt}]
if "flow_complete" not in st.session_state:
    st.session_state.flow_complete = False

st.title("GEHA 2026 dental enrollment guide")
st.caption("A plan recommendation and premium estimate—not an official eligibility or enrollment decision.")

with st.sidebar:
    st.subheader("Enrollment state machine")
    with st.expander("Show LangGraph logic", expanded=False):
        st.code(bot.mermaid(), language="mermaid")
    st.markdown(
        "**TypeSafe Jev integration points**\n\n"
        "Jev classifies free-text answers—including state descriptions—into the choices for each "
        "conversation stage. Exact menu selections, state codes, and state names stay local. Rules still "
        "decide eligibility status, ZIP/rate code validation, plan recommendation, and premium."
    )
    if st.button("Start over", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        prompt, _ = bot.reply("", st.session_state.thread_id)
        st.session_state.messages = [{"role": "assistant", "content": prompt}]
        st.session_state.flow_complete = False
        st.rerun()

for item in st.session_state.messages:
    if item["role"] == "warning":  # reviewer notes, e.g. extractors disagreeing
        st.warning(item["content"], icon="⚠️")
        continue
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

if message := st.chat_input(
    "Session complete — click Start over" if st.session_state.flow_complete
    else "Type a number or answer in your own words",
    disabled=st.session_state.flow_complete,
):
    st.session_state.messages.append({"role": "user", "content": message})
    with st.chat_message("user"):
        st.markdown(message)
    response, state = bot.reply(message, st.session_state.thread_id)
    for warning in state.get("warnings") or []:
        st.session_state.messages.append({"role": "warning", "content": warning})
        st.warning(warning, icon="⚠️")
    st.session_state.flow_complete = bool(state.get("complete"))
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)
        if state.get("jev_diagnostic"):
            with st.expander("TypeSafe Jev routing response", expanded=False):
                st.json(state["jev_diagnostic"])
