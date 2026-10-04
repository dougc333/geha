"""Streamlit UI for the GEHA dental enrollment state machine."""

from __future__ import annotations

import uuid

import streamlit as st
from dotenv import load_dotenv

from enrollment_graph import DentalEnrollmentGraph


load_dotenv()
st.set_page_config(page_title="GEHA dental enrollment guide", page_icon="🦷", layout="centered")


@st.cache_resource
def build_graph() -> DentalEnrollmentGraph:
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
        "Jev is used only when deterministic parsing cannot understand natural-language answers for "
        "member category, enrollment opportunity, or dental needs. Rules still decide eligibility status, "
        "plan recommendation, rate code, and premium."
    )
    if st.button("Start over", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        prompt, _ = bot.reply("", st.session_state.thread_id)
        st.session_state.messages = [{"role": "assistant", "content": prompt}]
        st.session_state.flow_complete = False
        st.rerun()

for item in st.session_state.messages:
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
    st.session_state.flow_complete = bool(state.get("complete"))
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)
        if state.get("jev_diagnostic"):
            with st.expander("TypeSafe Jev routing response", expanded=False):
                st.json(state["jev_diagnostic"])
