"""Local operator console. Demo personas are not authentication."""
import json
import os
import threading
import uuid
from pathlib import Path
import streamlit as st
from langgraph.checkpoint.sqlite import SqliteSaver
from demo import ROOT, load_inputs, workflow, resume

st.set_page_config(page_title='GEHA case review',page_icon='📋',layout='wide')
DB=Path(os.environ.get('GEHA_DEMO_DB',ROOT/'data/checkpoints.sqlite'))
BASE=Path(os.environ.get('GEHA_DEMO_BASE',ROOT.parent))

@st.cache_resource
def operation_lock(): return threading.RLock()

def saved_cases():
    if not DB.exists(): return []
    found={}
    with SqliteSaver.from_conn_string(str(DB)) as saver:
        for c in saver.list(None):
            tid=c.config['configurable']['thread_id']
            found.setdefault(tid,c.checkpoint.get('ts',''))
    return sorted(found,key=lambda t:found[t],reverse=True)

st.title('GEHA case review')
st.caption('Synthetic claims • Local review workspace • No claim decisions or payments')
st.warning('Demo operator console: all saved cases are visible locally. Personas are not secure authentication. Synthetic data only.')

try: 
    claims,trails,refs,example=load_inputs(BASE)
except (OSError,ValueError,KeyError) as exc:
    st.error(f'Cannot load demo inputs: {exc}'); st.stop()

with st.sidebar:
    st.header('Start a case')
    available=sorted(k for k,c in claims.items() if c['member_id']==claims[example]['member_id'])
    with st.form('start_case'):
        claim=st.selectbox('Synthetic claim',available,index=available.index(example))
        actor=st.selectbox('Demo persona',['member','outsider'])
        start=st.form_submit_button('Start new review',type='primary')
    st.caption('Thread IDs are automatic. Refreshing the page does not create a new case.')
    if start:
        tid=str(uuid.uuid4())
        with operation_lock(),workflow(DB,BASE) as g:
            g.invoke({'claim_id':claim,'actor':actor},{'configurable':{'thread_id':tid}})
        st.session_state['case_select']=tid
    with operation_lock(): cases=saved_cases()
    st.header('Saved cases')
    if not cases:
        st.info('Start a case to review its explanation.'); st.stop()
    if st.session_state.get('case_select') not in cases: st.session_state['case_select']=cases[0]
    tid=st.selectbox('Reopen a case',cases,key='case_select',format_func=lambda t:f'Case {t[:8]}')
    st.button('Refresh saved state')
cfg={'configurable':{'thread_id':tid}}

with operation_lock(),workflow(DB,BASE) as g:
    snap=g.get_state(cfg)
    history=list(reversed(list(g.get_state_history(cfg))))

s=snap.values
st.caption(f'Thread: {tid} — saved automatically in SQLite')
left,right=st.columns([2,1])

with left:
    st.subheader(s.get('claim_id','Case'))
    if not s.get('authorized'): st.error(s.get('answer','Access denied.'))
    elif snap.next==('review',):
        st.info('Waiting for human review. Approve the explanation—not the claim.')
        st.markdown(s['draft'])
        with st.form(f'review_{tid}'):
            text=st.text_area('Explanation to release',value=s['draft'],height=230)
            action=st.radio('Reviewer decision',['approve','reject'],horizontal=True)
            reason=st.text_input('Reason (required)')
            submitted=st.form_submit_button('Submit review',type='primary')
        if submitted:
            if not reason.strip(): st.error('Enter a review reason.')
            elif action=='approve' and not text.strip(): st.error('An approved explanation cannot be empty.')
            else:
                try:
                    with operation_lock(),workflow(DB,BASE) as g: resume(g,tid,action,reason,edited_text=text)
                    st.rerun()
                except ValueError as exc: st.error(str(exc))
    elif s.get('review'):
        st.success('Review completed' if s['review']['action']=='approve' else 'Explanation rejected')
        st.write(s.get('answer',''))
        st.caption('Reviewer reason: '+s['review']['reason'])
    else: st.info('No pending review. Inspect the checkpoint history below.')
with right:
    st.subheader('Recorded facts')
    if s.get('facts'): st.json(s['facts'])
    else: st.caption('No claim details were retrieved.')
    st.caption('General guidance is not a plan-specific coverage determination. No LLM is used.')
with st.expander('Checkpoint history'):
    for h in history:
        st.write(f"Step {h.metadata.get('step')} · {h.created_at}")
        st.caption('Next: '+(', '.join(h.next) or 'finished'))
        st.json(h.values,expanded=False)
st.download_button('Download case history',json.dumps([
    {'created_at':h.created_at,'step':h.metadata.get('step'),'next':h.next,'state':h.values}
    for h in history],indent=2),file_name=f'case-{tid}.json',mime='application/json')
