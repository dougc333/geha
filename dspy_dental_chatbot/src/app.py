"""Streamlit UI for DSPy dental enrollment and policy Q&A."""

from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load tracing and model configuration before importing the shared graph.
load_dotenv()

from corpus_retriever import ExistingDentalCorpusRetriever  # noqa: E402
from dspy_router import DspyExtractor  # noqa: E402
from policy_qa import (  # noqa: E402
    DentalPolicyIndex,
    DentalPolicyQA,
    PolicyChunk,
    expand_policy_query,
)
from policy_personas import evaluate_persona_result, load_personas, typing_frames  # noqa: E402
from safety_guard import (  # noqa: E402
    GuardedAnswer,
    GuardedPolicyQA,
    JevInputGuard,
    guard_lm_from_env,
    jev_available,
)
from shared_graph import DentalEnrollmentGraph  # noqa: E402


st.set_page_config(page_title="DSPy dental assistant", page_icon="🦷", layout="centered")

ROOT = Path(__file__).resolve().parents[2]
POLICY_PDF = ROOT / "crawl_dir/raw/dental/fedvip/2026-geha-dental-benefits-guide.pdf"
POLICY_PERSONAS = load_personas(
    Path(__file__).resolve().parents[1] / "data/policy_qa_personas.json"
)


@st.cache_resource
def build_graph() -> DentalEnrollmentGraph:
    return DentalEnrollmentGraph(jev=lambda *_: None, extractor=DspyExtractor())


def build_policy_qa() -> DentalPolicyQA:
    # DspyExtractor configures the shared DSPy LM before this is called.
    return DentalPolicyQA(DentalPolicyIndex.from_pdf(POLICY_PDF))


def build_guarded_policy_qa(qa: DentalPolicyQA) -> GuardedPolicyQA:
    # Jev classifies the question when TYPESAFE_API_KEY is set; DSPy otherwise.
    # The output guard always uses DSPy because it must read the evidence.
    input_guard = JevInputGuard() if jev_available() else None
    return GuardedPolicyQA(qa, input_guard=input_guard, guard_lm=guard_lm_from_env())


@st.cache_resource
def build_existing_corpus(
    include_plan_brochure: bool,
    adapter_version: str,
) -> ExistingDentalCorpusRetriever:
    del adapter_version  # Cache key used when the adapter interface changes.
    return ExistingDentalCorpusRetriever(include_plan_brochure=include_plan_brochure)


def retrieve_docling_chunks(corpus, query: str, top_k: int, mode: str) -> list[PolicyChunk]:
    """Adapt the stable corpus.search API for DSPy answer generation."""
    return corpus.search_policy_chunks(query, mode=mode, top_k=top_k)


def answer_policy_question(
    qa: GuardedPolicyQA,
    question: str,
    conversation: str,
    retriever_name: str,
) -> GuardedAnswer:
    code_query = bool(re.search(r"\bD\d{4}\b", question, flags=re.IGNORECASE))
    top_k = 6 if code_query else 4
    if retriever_name == "Direct PDF BM25":
        retrieve = None
    else:
        mode = retriever_name.removeprefix("Docling ").lower()
        corpus = build_existing_corpus(code_query, "policy-chunks-v2")
        retrieve = lambda query, top_k: retrieve_docling_chunks(
            corpus, query, top_k=top_k, mode=mode
        )
    return qa.ask(
        question,
        conversation=conversation,
        top_k=top_k,
        retrieve=retrieve,
        # Independent questions must not compete with unrelated terms from
        # prior turns. Conversation still goes to answer generation; a future
        # follow-up rewriter can create a separate standalone retrieval query.
        retrieval_query=question,
    )


st.title("DSPy + GEHA 2026 dental assistant")
st.caption("Complete an enrollment workflow or ask grounded questions about the dental benefits guide.")

try:
    bot = build_graph()
    policy_qa = build_policy_qa()
    guarded_policy_qa = build_guarded_policy_qa(policy_qa)
except Exception as error:
    st.error(f"DSPy is not configured: {error}")
    st.code(
        "DSPY_MODEL=openai/gpt-4o-mini\n"
        "DSPY_API_KEY=...\n"
        "streamlit run src/app.py --server.port 8506",
        language="bash",
    )
    st.stop()

with st.sidebar:
    st.subheader("DSPy dental assistant")
    st.write(f"Model: `{os.getenv('DSPY_MODEL', 'not configured')}`")
    st.markdown(
        "Enrollment uses a deterministic policy graph. Policy Q&A retrieves locally from only "
        "the 2026 dental benefits guide, then DSPy synthesizes a cited answer."
    )

enrollment_tab, policy_tab, comparison_tab = st.tabs(
    ["Enrollment chat", "Dental Policy Q&A", "Retrieval comparison"]
)

with enrollment_tab:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
        prompt, _ = bot.reply("", st.session_state.thread_id)
        st.session_state.messages = [{"role": "assistant", "content": prompt}]
    if "flow_complete" not in st.session_state:
        st.session_state.flow_complete = False

    with st.expander("Show LangGraph logic", expanded=False):
        st.code(bot.mermaid(), language="mermaid")
    if st.button("Start enrollment over", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        prompt, _ = bot.reply("", st.session_state.thread_id)
        st.session_state.messages = [{"role": "assistant", "content": prompt}]
        st.session_state.flow_complete = False
        st.rerun()

    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    answer = st.chat_input(
        "Type a number or answer in your own words",
        disabled=st.session_state.flow_complete,
        key="enrollment_input",
    )
    if answer:
        st.session_state.messages.append({"role": "user", "content": answer})
        with st.chat_message("user"):
            st.markdown(answer)
        with st.chat_message("assistant"):
            with st.spinner("DSPy is interpreting the answer..."):
                response, state = bot.reply(answer, st.session_state.thread_id)
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.flow_complete = bool(state.get("complete"))
        st.rerun()

with policy_tab:
    st.info(
        "Answers use the 2026 GEHA Dental Benefits Guide. CDT-code questions also search "
        "the separate 2026 dental plan brochure. "
        "Open the retrieved evidence under each answer to verify it."
    )
    if "policy_messages" not in st.session_state:
        st.session_state.policy_messages = []
    answer_retriever = st.selectbox(
        "Evidence retriever",
        options=[
            "Docling auto",
            "Docling hybrid",
            "Docling vector",
            "Docling BM25",
            "Direct PDF BM25",
        ],
        help=(
            "Docling modes reuse the existing page-aware corpus. Retrieved evidence is then "
            "sent to the configured DSPy language model for answer generation."
        ),
    )
    with st.expander("Persona testing", expanded=False):
        selected_persona_id = st.selectbox(
            "Test persona",
            options=[persona["id"] for persona in POLICY_PERSONAS],
            format_func=lambda persona_id: next(
                persona["name"] for persona in POLICY_PERSONAS if persona["id"] == persona_id
            ),
        )
        selected_persona = next(
            persona for persona in POLICY_PERSONAS if persona["id"] == selected_persona_id
        )
        st.caption(selected_persona["description"])
        typing_delay_ms = st.slider(
            "Typing speed (milliseconds per character)",
            min_value=5,
            max_value=80,
            value=25,
            step=5,
        )
        run_persona = st.button("Run persona", type="primary", use_container_width=True)
    if st.button("Clear policy conversation", use_container_width=True):
        st.session_state.policy_messages = []
        st.rerun()

    for item in st.session_state.policy_messages:
        with st.chat_message(item["role"]):
            if item.get("persona"):
                st.caption(f"Persona: {item['persona']}")
            st.markdown(item["content"])
            if item.get("sources"):
                with st.expander("Retrieved evidence"):
                    for source in item["sources"]:
                        st.markdown(
                            f"**{source['document_id']} · {source['plan_year']} · "
                            f"Page {source['page']} · {source['section']} · "
                            f"score {source['score']:.2f}**"
                        )
                        st.markdown(source["text"])
            if evaluation := item.get("persona_evaluation"):
                if evaluation["passed"]:
                    st.success(
                        "Persona eval passed · source groups "
                        + " + ".join(
                            "/".join(str(page) for page in group)
                            for group in evaluation["expected_page_groups"]
                        )
                    )
                else:
                    st.error(
                        "Persona eval failed · "
                        f"pages {evaluation['retrieved_pages']} · "
                        f"missing page groups={evaluation['missing_page_groups']} · "
                        f"missing citation groups={evaluation['missing_citation_groups']} · "
                        f"missing facts={evaluation['missing_facts']}"
                    )

    typed_question = st.chat_input("Ask about dental benefits or coverage", key="policy_input")
    persona = selected_persona if run_persona else None
    question = persona["query"] if persona else typed_question
    if question:
        prior_turns = st.session_state.policy_messages[-6:]
        conversation = "\n".join(
            f"{item['role']}: {item['content']}" for item in prior_turns
        )
        with st.chat_message("user"):
            if persona:
                st.caption(f"Persona: {persona['name']} · typing…")
                typing_placeholder = st.empty()
                for frame in typing_frames(question):
                    typing_placeholder.markdown(frame)
                    time.sleep(typing_delay_ms / 1000)
            else:
                st.markdown(question)
        st.session_state.policy_messages.append(
            {
                "role": "user",
                "content": question,
                "persona": persona["name"] if persona else None,
            }
        )
        with st.chat_message("assistant"):
            with st.spinner("Retrieving policy evidence and composing a cited answer..."):
                guarded = answer_policy_question(
                    guarded_policy_qa,
                    question,
                    conversation,
                    answer_retriever,
                )
            response, chunks = guarded.answer, guarded.chunks
            st.markdown(response)
            with st.expander("Safety checks"):
                for verdict in guarded.verdicts:
                    st.markdown(f"**{verdict.stage}** · `{verdict.category}` · {verdict.reason}")
            with st.expander("Retrieved evidence"):
                for chunk in chunks:
                    st.markdown(
                        f"**{chunk.document_id} · {chunk.plan_year} · Page {chunk.page} · "
                        f"{chunk.section} · score {chunk.score:.2f}**"
                    )
                    st.markdown(chunk.text)
        persona_evaluation = (
            evaluate_persona_result(persona, response, chunks) if persona else None
        )
        st.session_state.policy_messages.append(
            {
                "role": "assistant",
                "content": response,
                "retriever": answer_retriever,
                "persona_evaluation": persona_evaluation,
                "blocked": guarded.blocked,
                "guard_verdicts": [
                    {"stage": v.stage, "category": v.category, "reason": v.reason}
                    for v in guarded.verdicts
                ],
                "sources": [
                    {
                        "page": chunk.page,
                        "score": chunk.score,
                        "text": chunk.text,
                        "document_id": chunk.document_id,
                        "plan_year": chunk.plan_year,
                        "section": chunk.section,
                    }
                    for chunk in chunks
                ],
            }
        )
        st.rerun()

with comparison_tab:
    st.subheader("PDF text vs. existing Docling hybrid RAG")
    st.caption(
        "The left side uses the current pypdf page chunks and BM25. The right side reuses "
        "agentic_search_corpus: Docling page Markdown plus BM25, BGE vectors, or hybrid rank fusion."
    )
    comparison_query = st.text_input(
        "Question",
        value="is my Costco glasses covered",
        key="comparison_query",
    )
    control_left, control_right = st.columns(2)
    with control_left:
        corpus_mode = st.selectbox(
            "Existing RAG retrieval mode",
            options=["bm25", "vector", "hybrid"],
            index=1,
            help="Vector works best for the Costco/glasses semantic query; compare BM25 and hybrid explicitly.",
        )
    with control_right:
        include_brochure = st.checkbox(
            "Include the separate 56-page plan brochure",
            value=False,
            help="Off keeps both retrievers scoped to the same benefits-guide source.",
        )

    if st.button("Compare retrieval", type="primary", use_container_width=True):
        with st.spinner("Running both retrieval paths..."):
            started = time.perf_counter()
            pdf_hits = policy_qa.index.search(comparison_query, top_k=4)
            pdf_ms = (time.perf_counter() - started) * 1000

            corpus = build_existing_corpus(include_brochure, "policy-chunks-v2")
            started = time.perf_counter()
            corpus_hits = corpus.search(comparison_query, mode=corpus_mode, top_k=4)
            corpus_ms = (time.perf_counter() - started) * 1000

        st.session_state.retrieval_comparison = {
            "query": comparison_query,
            "mode": corpus_mode,
            "include_brochure": include_brochure,
            "pdf_ms": pdf_ms,
            "pdf_hits": pdf_hits,
            "corpus_ms": corpus_ms,
            "corpus_hits": corpus_hits,
        }

    comparison = st.session_state.get("retrieval_comparison")
    if comparison:
        left, right = st.columns(2)
        with left:
            st.markdown("### Current PDF + BM25")
            st.metric("Retrieval latency", f"{comparison['pdf_ms']:.1f} ms")
            for rank, hit in enumerate(comparison["pdf_hits"], start=1):
                with st.expander(f"#{rank} · benefits guide p. {hit.page} · score {hit.score:.2f}"):
                    st.text(hit.text)
        with right:
            st.markdown(f"### Docling + {comparison['mode'].upper()}")
            st.metric("Retrieval latency", f"{comparison['corpus_ms']:.1f} ms")
            for hit in comparison["corpus_hits"]:
                label = f"#{hit.rank} · {hit.document} · p. {hit.page}"
                with st.expander(label):
                    st.caption(hit.chunk_id)
                    st.markdown(hit.text)
