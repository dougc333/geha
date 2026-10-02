"""Streamlit chat interface for the GEHA 2026 dental + medical enrollment state machine.

    cd /Users/dc/geha/e2e_RAG/src && streamlit run benefits_chat_app.py

The sidebar shows the slot state the state machine is tracking, so you can watch each
answer fill a slot and see which question comes next.
"""

from __future__ import annotations

import uuid

import streamlit as st

from benefits_bot import BenefitsBot

SLOTS = [("line", "Coverage"), ("status", "Employed or retired"), ("enrollment", "Enrollment type"),
         ("zip", "ZIP"), ("rate_code", "Dental rate code"), ("dental_plan", "Dental plan"),
         ("medical_plan", "Medical plan")]
EXAMPLES = ["Dental and medical, I'm retired, me and my wife", "Medical only, active employee, self only, compare",
            "Does Elevate Plus cover an MRI?", "Do you cover braces?"]


@st.cache_resource(show_spinner="Reading the GEHA PDFs…")
def load_bot() -> BenefitsBot:
    return BenefitsBot()


def send(text: str) -> None:
    st.session_state.messages.append(("user", text))
    st.session_state.messages.append(("assistant", load_bot().reply(text, st.session_state.thread)))


def start_over() -> None:
    st.session_state.thread = uuid.uuid4().hex
    st.session_state.messages = [("assistant", load_bot().reply("hi", st.session_state.thread))]


st.set_page_config(page_title="GEHA 2026 benefits quote", page_icon="🦷", layout="centered")
st.title("GEHA 2026 benefits quote")
st.caption("Dental (FEDVIP) and medical (FEHB). Every premium and benefit comes from a table in GEHA's 2026 PDFs.")

if "thread" not in st.session_state:
    start_over()

with st.sidebar:
    st.subheader("Slot state")
    slots = load_bot().state(st.session_state.thread)
    for key, label in SLOTS:
        value = slots.get(key)
        st.markdown(f"**{label}:** {value if value is not None else '—'}")
    st.button("Start over", on_click=start_over, use_container_width=True)
    st.divider()
    st.caption("Try:")
    for example in EXAMPLES:
        st.button(example, on_click=send, args=(example,), use_container_width=True)

for role, text in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(text.replace("\n", "  \n").replace("$", "\\$"))

if prompt := st.chat_input("Type your answer or a benefits question"):
    send(prompt)
    st.rerun()
