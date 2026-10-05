"""Streamlit UI for dental corpus retrieval and corrective answers."""
import json
import os
import re
import threading
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from corpus_search import CorpusSearch, ROOT
from answer_workflows import OPTIONS, MULTI, answer_question

load_dotenv(ROOT / '.env', override=False)
st.set_page_config(page_title='Dental corpus search', page_icon='🦷', layout='wide')

@st.cache_resource
def resources():
    return CorpusSearch(mode='bm25'), threading.Lock()

def snippet(text, query):
    clean = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    clean = re.sub(r'\s+', ' ', clean).strip()
    terms = re.findall(r'[a-z0-9]+', query.lower())
    terms = [t for t in terms if len(t) > 3 or re.fullmatch(r'd\d+', t)]
    positions = [clean.lower().find(t) for t in terms if t in clean.lower()]
    start = max(0, min(positions) - 100) if positions else 0
    return ('…' if start else '') + clean[start:start + 450] + ('…' if start + 450 < len(clean) else '')

def render(message):
    with st.chat_message(message['role']):
        st.markdown(message['content'])
        if 'seconds' in message:
            st.caption(f"{message['mode']} · {message['seconds']:.2f}s · {message['workflow']}")
        for rank, result in enumerate(message.get('results', []), 1):
            with st.container(border=True):
                st.markdown(f"**{rank}. {result['title']}**")
                st.caption(f"{result['document']} · PDF page {result['page']}")
                st.write(result['snippet'])
                with st.expander('Read full page', expanded=False):
                    st.markdown(result['text'])
        if message.get('trace'):
            with st.expander('Agent search trace', expanded=False):
                st.code('\n'.join(message['trace']), language='text')
        if message.get('complete') is False:
            st.warning('Evidence is incomplete. Review missing requirements: ' + '; '.join(message.get('missing', [])))
        if 'grounded' in message:
            if message['grounded']:
                st.caption('The agent marked this response grounded. Review its source evidence below.')
            else:
                st.warning('The response did not pass the grounding check within the retry limit.')
        if message.get('evidence'):
            with st.expander('Source evidence', expanded=False):
                for item in message['evidence']:
                    st.markdown(item)
                    st.divider()

st.title('GEHA 2026 dental corpus search')
st.caption('Search the dental benefits guide and plan brochure, with source-page citations.')
search, lock = resources()
with st.sidebar:
    st.header('Search settings')
    workflow = st.radio('Agent mode', OPTIONS)
    st.caption(f'{len(search.docs)} pages across two documents. Both modes use vector retrieval and OpenAI.')
    st.caption('Single-turn: one retrieval and answer. Multiturn: at most two retrieval rounds total (one follow-up); not cross-message conversation memory.')
    if not os.getenv('OPENAI_API_KEY'):
        st.warning('Set OPENAI_API_KEY in the environment or project .env to generate answers.')
    if st.button('Clear conversation'):
        st.session_state.messages = []
        st.rerun()
    with st.expander('Corpus sources'):
        st.write('2026 GEHA dental benefits guide')
        st.write('2026 GEHA dental plan brochure')
        st.caption('Page numbers refer to source PDF pages, which can differ from printed page numbers.')

if 'messages' not in st.session_state:
    st.session_state.messages = []
for message in st.session_state.messages:
    render(message)

questions = [json.loads(line)['query'] for line in (ROOT / 'evals/queries.jsonl').read_text().splitlines() if line.strip()]
with st.expander('Try an example question', expanded=not st.session_state.messages):
    example = st.selectbox('Benchmark questions', questions)
    run_example = st.button('Ask selected question')
typed = st.chat_input('Ask about dental benefits or enrollment rules')
question = typed or (example if run_example else None)
if question:
    mode = 'vector'
    user = {'role': 'user', 'content': question}
    st.session_state.messages.append(user)
    render(user)
    started = time.perf_counter()
    try:
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError('OPENAI_API_KEY is missing. Configure the key and restart.')
        with st.spinner('Searching and checking completeness…' if workflow == MULTI else 'Searching and answering…'):
            # Serialize shared model access; selected modes never mutate shared search state.
            with lock:
                answer = answer_question(search, question, workflow)
        answer.update(seconds=time.perf_counter() - started, mode=mode, workflow=workflow)
    except Exception as exc:
        answer = {'role': 'assistant', 'content': f'Search failed ({type(exc).__name__}). Check the configuration and retry.'}
        # Avoid displaying exception bodies that may contain credentials or request headers.
        if isinstance(exc, ValueError) and 'OPENAI_API_KEY is missing' in str(exc):
            answer['content'] = str(exc)
    st.session_state.messages.append(answer)
    render(answer)
